"""The hand-off to Spec Kit: the entry rules of the wrapped commands and the carrying of a pending
clarification answer upstream (task T089; FR-004, FR-041, FR-042, FR-067, research D-13).

``enter`` is the single gate call every wrap makes before the core command runs. It synchronises the
aliases first, then decides, in code, whether the core command may proceed. Refusals are collected
and reported together; nothing here writes a stage document.

``resolve`` is the other half of a clarification: the AI Specification holds the answer as a pending
item (FR-067) until it has a source in an approved earlier stage.
"""

from __future__ import annotations

import re
from typing import Any

from . import aliases, staleness
from .blocks import Doc
from .content import blocks_of
from .gates import PENDING, Sections, check_stage
from .package import DOC_FILES, Package
from .records import prior_stage_refusals
from .results import Refusal, refuse
from .staleness import Cause
from .trace import _TAG, parse_document

ENTER_COMMANDS = ("specify", "clarify", "plan", "tasks", "analyze", "checklist", "implement")

# The kind of item an answer becomes in each stage it may be carried to, and the section it belongs in.
CARRY = {
    "requirements": ("REQ", "Desired Outcome"),
    "functional": ("FR", "Functional Requirements"),
    "technical": ("DEC", "Technical Decisions"),
}
_TRACES = re.compile(r"\(traces:\s*(?P<ids>[^)]*)\)")


def missing_refusal(stage: str, fix: str) -> Refusal:
    code = {
        "ai-spec": "ai-spec-missing",
        "plan": "plan-missing",
        "tasks": "tasks-missing",
        "verification": "verification-missing",
    }[stage]
    return Refusal(code, f"{DOC_FILES[stage]} does not exist", fix)


def ai_spec_refusals(pkg: Package) -> list[Refusal]:
    """Why Plan and Tasks may not start at all: the AI Specification must exist and its document-wide
    checks (artefacts and diagrams) must pass (FR-004). Items without a source or pending a clarification
    are per-item ``blocked`` entries instead (D-35)."""
    if not pkg.exists("ai-spec"):
        return [missing_refusal("ai-spec", "Create it with /speckit-eil-ai-spec once Technical is approved")]
    result = check_stage(pkg, "ai-spec", write=False)
    rest = [c for c in result.unmet() if c.id in ("AIS-G04", "AIS-G05")]
    if not rest:
        return []
    listing = "".join(f"\n  {c.id}: {c.reason}" for c in rest)
    return [
        Refusal(
            "ai-spec-not-traceable",
            f"the AI Specification does not pass its source-traceability check:{listing}",
            "Give each item an approved source, or remove it; or record a named override of the criterion",
        )
    ]


def _never_approved(pkg: Package) -> list[Refusal]:
    """``stage-not-approved`` only for a stage that has never been approved; one that needs re-review is
    handled item by item."""
    return [
        r
        for r in prior_stage_refusals(pkg, "plan")
        if pkg.state(_stage_named(r.message)).state != "needs-re-review"
    ]


def _stage_named(message: str) -> str:
    return message.split(" ", 1)[0]


def _sourceless(pkg: Package) -> dict[str, list[Cause]]:
    """AI Specification items with no approved source, by id, and the work that traces to them."""
    if not pkg.exists("ai-spec"):
        return {}
    out: dict[str, list[Cause]] = {}
    for finding in check_stage(pkg, "ai-spec", write=False).findings:
        if finding.code == "ai-spec-not-traceable":
            out.setdefault(finding.where, []).append(
                Cause(finding.message, "Give it an approved source, or remove it")
            )
    return out


def _dependants(pkg: Package, roots: dict[str, list[Cause]]) -> dict[str, list[Cause]]:
    edges = {}
    for stage in pkg.existing_stages():
        for b in blocks_of(pkg.doc(stage)):
            if b.numbered:
                edges.setdefault(b.key, list(b.traces))
    out = {k: list(v) for k, v in roots.items()}
    changed = True
    while changed:
        changed = False
        for key, traces in edges.items():
            for source in traces:
                if source in out:
                    cause = Cause(
                        f"{source} is blocked ({out[source][0]})",
                        f"Clear {source} first: {out[source][0].fix}",
                    )
                    if str(cause) not in out.setdefault(key, []):
                        out[key].append(cause)
                        changed = True
    return out


def _scope(pkg: Package) -> tuple[dict[str, list[Cause]], dict[str, list[Cause]]]:
    blocked, rederive = staleness.scoped_work(pkg)
    for key, causes in _dependants(pkg, _sourceless(pkg)).items():
        blocked.setdefault(key, [])
        blocked[key] += [c for c in causes if str(c) not in blocked[key]]
        rederive.pop(key, None)
    return dict(sorted(blocked.items())), rederive


def _task_blocks(pkg: Package) -> list[Any]:
    return [b for b in blocks_of(pkg.doc("tasks")) if b.kind == "task"] if pkg.exists("tasks") else []


def _work_refusals(
    pkg: Package, task: str | None, blocked: dict[str, list[Cause]], rederive: dict[str, list[Cause]]
) -> list[Refusal]:
    tasks = _task_blocks(pkg)
    if task is not None:
        if task not in {t.key for t in tasks}:
            return [
                Refusal("unknown-item", f"{task} is not a task in tasks.md", "Name a task id from tasks.md")
            ]
        if task in blocked:
            causes = blocked[task]
            fixes = "; ".join(dict.fromkeys(c.fix for c in causes if c.fix))
            return [Refusal("work-blocked", f"{task} is blocked: " + "; ".join(causes), fixes)]
        if task in rederive:
            return [
                Refusal(
                    "work-blocked",
                    f"{task} must be re-derived first: " + "; ".join(rederive[task]),
                    f"Re-derive {task}",
                )
            ]
        return []
    open_tasks = [t.key for t in tasks if not staleness.is_ticked(t)]
    if open_tasks and all(t in blocked or t in rederive for t in open_tasks):
        return [
            Refusal(
                "work-blocked",
                "every open task is blocked: "
                + ", ".join(f"{t} ({(blocked.get(t) or rederive[t])[0]})" for t in open_tasks[:6]),
                "; ".join(dict.fromkeys(c.fix for t in open_tasks for c in blocked.get(t, []) if c.fix)),
            )
        ]
    return []


def _derived_refusals(pkg: Package) -> list[Refusal]:
    """Under the small-story profile, implementation waits until the combined derived list is answered:
    the profile overrides plan and task entry only, never implementation (FR-022)."""
    from . import reviews
    from .profile import active

    if active(pkg) is None:
        return []
    pending = reviews.build_list(pkg, reviews.DERIVED_LIST, "inferred").entries
    if not pending:
        return []
    listing = ", ".join(e.key for e in pending[:10])
    return [
        Refusal(
            "unreviewed-ai-content",
            f"{len(pending)} entr{'y' if len(pending) == 1 else 'ies'} of the derived list (AI Specification, plan and tasks) "
            f"are not answered: {listing}",
            "Present it once and record the reply: eil review list --stage derived --kind inferred",
        )
    ]


def enter(
    pkg: Package,
    command: str,
    mode: str = aliases.SYMLINK,
    strict: bool = False,
    task: str | None = None,
) -> dict[str, Any]:
    """Synchronise the aliases, then apply the entry rule of ``command``; refuse, or describe what was done.

    ``plan``, ``tasks`` and ``implement`` are work-scoped (D-35): only a stage never approved, or nothing
    that may proceed, refuses the command; ``blocked`` names the items that may not be relied on and
    ``rederive`` those that need deriving again."""
    before, after = aliases.refresh(pkg, mode)
    faults = [s for s in before if s.fault]
    refusals: list[Refusal] = []
    blocked: dict[str, list[Cause]] = {}
    rederive: dict[str, list[Cause]] = {}
    if command == "specify":
        refusals.append(
            Refusal(
                "already-governed",
                f"{pkg.root.name} is already a governed story",
                f"Continue it with the command for its current stage ({pkg.current_stage() or 'complete'})",
            )
        )
    elif command == "clarify":
        if not pkg.exists("ai-spec"):
            refusals.append(
                missing_refusal(
                    "ai-spec", "Clarify needs an AI Specification: run /speckit-eil-ai-spec first"
                )
            )
    elif command in ("plan", "tasks", "implement"):
        if command in ("plan", "tasks"):
            refusals.extend(_never_approved(pkg))
        refusals.extend(ai_spec_refusals(pkg))
        if command in ("tasks", "implement") and not pkg.exists("plan"):
            refusals.append(missing_refusal("plan", "Run /speckit-plan first"))
        if command == "implement" and not pkg.exists("tasks"):
            refusals.append(missing_refusal("tasks", "Run /speckit-tasks first"))
        if command == "implement":
            refusals.extend(_derived_refusals(pkg))
        if not refusals:
            blocked, rederive = _scope(pkg)
            if command == "implement":
                refusals.extend(_work_refusals(pkg, task, blocked, rederive))
    if task is not None and command != "implement":
        refusals.append(Refusal("unknown-item", "--task applies only to implement", "Drop --task"))
    unresolved = [s for s in after if s.fault]
    if (strict and faults) or (command == "implement" and unresolved):
        shown = unresolved or faults
        refusals.append(
            Refusal(
                "alias-fault-strict",
                "alias fault(s): " + ", ".join(f"{s.name} ({s.fault})" for s in shown),
                "Run eil sync; a fault it cannot repair needs a person",
            )
        )
    if refusals:
        raise refuse(*refusals)
    text = f"May proceed with {command}"
    held = (
        [t.key for t in _task_blocks(pkg) if t.key in blocked and not staleness.is_ticked(t)]
        if command == "implement" and task is None
        else []
    )
    if held:
        text += " except " + ", ".join(held)
    text += "."
    if rederive:
        text += " To re-derive: " + ", ".join(rederive) + "."
    if faults:
        text += f" Repaired: {', '.join(f'{s.name} ({s.fault})' for s in faults)}."
    overrides_used: list[str] = []
    if command in ("plan", "tasks"):
        from .profile import override as profile_override

        held = profile_override(pkg)
        if held is not None and f"enter {command}" in held.get("scope", []):
            overrides_used.append(str(held["id"]))
            text += f" Under the small-story profile's override {held['id']} (unreviewed-ai-content, by {held['by']})."
    return {
        "ok": True,
        "command": command,
        "overrides_used": overrides_used,
        "alias_faults": [s.to_json() for s in faults],
        "aliases": [s.to_json() for s in after],
        "blocked": staleness.rows(blocked),
        "rederive": list(rederive),
        "text": text,
    }


# ---- resolve


def _next_number(pkg: Package, kind: str) -> int:
    highest = 0
    for stage in pkg.existing_stages():
        try:
            parsed = parse_document(pkg.doc(stage))
        except UnicodeDecodeError:
            continue
        highest = max([highest, *(i.number for i in parsed.items if i.kind == kind)])
    return highest + 1


def _insert_into_section(text: str, heading: str, block: str) -> str | None:
    doc = Doc(text)
    section = Sections(doc).find(heading)
    if section is None:
        return None
    lines = text.split("\n")
    end = len(lines)
    later = [s for s in Sections(doc).sections if s.line > section.line and s.level <= section.level]
    if later:
        end = min(s.line for s in later) - 1
    last = end
    while last > section.line and not lines[last - 1].strip():
        last -= 1
    return "\n".join([*lines[:last], "", block, *lines[last:]])


def _add_trace(line: str, new_id: str) -> str:
    found = _TRACES.search(line)
    if found:
        ids = [i.strip() for i in found["ids"].split(",") if i.strip()]
        if new_id in ids:
            return line
        return line[: found.start()] + f"(traces: {', '.join([*ids, new_id])})" + line[found.end() :]
    tag = re.search(rf"\s*\[{PENDING}\]", line)
    clause = f" (traces: {new_id})"
    return line[: tag.start()] + clause + line[tag.start() :] if tag else line.rstrip() + clause


def resolve(pkg: Package, item_id: str, stage: str) -> dict[str, Any]:
    """Carry a pending answer to ``stage``, or clear its mark once the answer has an approved source."""
    if stage not in CARRY:
        raise refuse(
            Refusal(
                "stage-not-eligible",
                f"{stage!r} cannot take a carried answer",
                f"Carry it to the earliest stage it affects: {', '.join(CARRY)}",
            )
        )
    if not pkg.exists("ai-spec"):
        raise refuse(missing_refusal("ai-spec", "There is nothing pending without an AI Specification"))
    spec_text = pkg.read("ai-spec")
    parsed = parse_document(Doc(spec_text))
    item = next((i for i in parsed.items if i.id == item_id and i.kind == "AIS"), None)
    if item is None or PENDING not in item.tags:
        raise refuse(
            Refusal(
                "unknown-item",
                f"{item_id} is not a pending clarification in the AI Specification",
                "Use the id of an AIS item tagged [pending-clarification]",
            )
        )
    if not pkg.exists(stage):
        raise refuse(
            Refusal(
                "stage-not-eligible", f"{stage} has no document yet", f"Start it with: eil stage-init {stage}"
            )
        )

    kind, heading = CARRY[stage]
    target = parse_document(pkg.doc(stage))
    defined_here = {i.id for i in target.items}
    carried = next((ref for ref in item.traces if ref.startswith(f"{kind}-") and ref in defined_here), None)
    created = False
    if carried is None:
        carried = f"{kind}-{_next_number(pkg, kind):03d}"
        answer = _TAG.sub("", item.title).strip()
        block = f"**{carried}**: Carried from {item.id}: {answer} [ai-draft]"
        updated = _insert_into_section(pkg.read(stage), heading, block)
        if updated is None:
            raise refuse(
                Refusal(
                    "stage-not-eligible",
                    f"{stage} has no '{heading}' section to carry {item.id} into",
                    f"Add the section, or write the decision into {stage} by hand and trace {item.id} to it",
                )
            )
        pkg.doc_path(stage).write_bytes(updated.encode("utf-8"))
        created = True
        lines = spec_text.split("\n")
        index = item.line - 1
        lines[index] = _add_trace(lines[index], carried)
        spec_text = "\n".join(lines)
        pkg.doc_path("ai-spec").write_bytes(spec_text.encode("utf-8"))

    cleared = False
    if not created and pkg.state(stage).state == "approved":
        lines = spec_text.split("\n")
        index = item.line - 1
        lines[index] = re.sub(rf"\s*\[{PENDING}\]", "", lines[index])
        pkg.doc_path("ai-spec").write_bytes("\n".join(lines).encode("utf-8"))
        cleared = True

    state = pkg.state(stage).state
    if cleared:
        text = f"{item_id} now has an approved source ({carried} in {stage}); the pending mark is cleared."
    elif created:
        text = (
            f"Carried {item_id} to {carried} in {stage} (now {state}). Write the decision there, "
            f"remove [ai-draft], approve {stage}, then run resolve again to clear the pending mark."
        )
    else:
        text = f"{carried} in {stage} is {state}; approve {stage} with the decision written, then run resolve again."
    return {
        "ok": True,
        "id": item_id,
        "carried_to": carried,
        "stage": stage,
        "stage_state": state,
        "created": created,
        "cleared": cleared,
        "text": text,
    }


__all__ = ["ENTER_COMMANDS", "ai_spec_refusals", "enter", "missing_refusal", "resolve"]

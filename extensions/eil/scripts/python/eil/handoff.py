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

from . import aliases
from .blocks import Doc
from .gates import PENDING, Sections, check_stage
from .package import DOC_FILES, Package
from .records import prior_stage_refusals
from .results import Refusal, refuse
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
    """Why Plan and Tasks may not start: the AI Specification must exist and pass its gate (FR-004)."""
    if not pkg.exists("ai-spec"):
        return [missing_refusal("ai-spec", "Create it with /speckit-eil-ai-spec once Technical is approved")]
    result = check_stage(pkg, "ai-spec", write=False)
    refusals: list[Refusal] = []
    pending = [c for c in result.unmet() if c.id == "AIS-G03"]
    rest = [c for c in result.unmet() if c.id != "AIS-G03"]
    if pending:
        refusals.append(
            Refusal(
                "pending-clarification",
                pending[0].reason,
                "Carry each answer to the earliest stage it affects with /speckit-eil-resolve, or record a named override of AIS-G03",
            )
        )
    if rest:
        listing = "".join(f"\n  {c.id}: {c.reason}" for c in rest)
        refusals.append(
            Refusal(
                "ai-spec-not-traceable",
                f"the AI Specification does not pass its source-traceability check:{listing}",
                "Give each item an approved source, or remove it; or record a named override of the criterion",
            )
        )
    return refusals


def enter(
    pkg: Package,
    command: str,
    mode: str = aliases.SYMLINK,
    strict: bool = False,
) -> dict[str, Any]:
    """Synchronise the aliases, then apply the entry rule of ``command``; refuse, or describe what was done."""
    before, after = aliases.refresh(pkg, mode)
    faults = [s for s in before if s.fault]
    refusals: list[Refusal] = []
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
            refusals.extend(prior_stage_refusals(pkg, "plan"))
        refusals.extend(ai_spec_refusals(pkg))
        if command in ("tasks", "implement") and not pkg.exists("plan"):
            refusals.append(missing_refusal("plan", "Run /speckit-plan first"))
        if command == "implement" and not pkg.exists("tasks"):
            refusals.append(missing_refusal("tasks", "Run /speckit-tasks first"))
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
    return {
        "ok": True,
        "command": command,
        "alias_faults": [s.to_json() for s in faults],
        "aliases": [s.to_json() for s in after],
        "text": f"May proceed with {command}."
        + (f" Repaired: {', '.join(f'{s.name} ({s.fault})' for s in faults)}." if faults else ""),
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

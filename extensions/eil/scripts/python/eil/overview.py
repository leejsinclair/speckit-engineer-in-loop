"""The generated overview ``s00-README.md`` and the ``status`` report (tasks T042, T054, T055;
FR-054 to FR-056, research D-14).

Both come from one derived model, ``collect``: nothing is stored, and the stage documents are
always the authority. The overview is rewritten from that model and contains only record values
and fixed labels, never text copied from a document's prose (FR-055); an artefact's own title is
the one label taken verbatim, and never its diagram. ``status`` reports the same facts as JSON and
writes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import aliases, blockstatus, comprehension, staleness
from .artifacts import artifact_state, scan_document
from .gates import CRITERIA_BY_STAGE, INTEGRITY_CODES, check_stage
from .package import APPROVABLE, DOC_FILES, OVERVIEW, STAGES, Package, StageState, reached_of
from .records import challenge_severity
from .results import Finding
from .trace import ParseResult, parse_document, story_findings

# A record file that is missing or cannot be read makes approvals unverifiable (D-48, FR-011).
RECORD_INTEGRITY_CODES = frozenset({"approval-record-missing", "malformed-record-file"})
NOTICE = "<!-- eil:generated — edit the stage documents, not this file -->"
_TITLE = re.compile(r"^- Title:\s*(?P<v>.*)$", re.MULTILINE)
_OWNER = re.compile(r"^- Owner:\s*(?P<v>.*)$", re.MULTILINE)

START_COMMANDS = {
    "requirements": "/speckit-eil-1-requirements",
    "functional": "/speckit-eil-2-functional",
    "technical": "/speckit-eil-3-technical",
    "ai-spec": "/speckit-eil-4-ai-spec",
    "plan": "/speckit-eil-5-plan",
    "tasks": "/speckit-eil-6-tasks",
    "verification": "/speckit-eil-7-verify",
    "completion": "/speckit-eil-8-complete",
}
IMPLEMENT_COMMAND = "/speckit-implement"
APPROVE_COMMAND = "/speckit-eil-approve"
CHALLENGE_COMMAND = "/speckit-eil-challenge"
# What ``/speckit-eil-next`` may run without a person: drafting and checking. Everything else stops.
AUTOMATIC_KINDS = ("draft", "check")
_OPEN_TASK = re.compile(r"^\s*[-*]\s+\[ \]\s+T\d+", re.MULTILINE)
_OUTCOME_LABELS = (
    ("understood", "understood"),
    ("coached", "coached"),
    ("revealed", "revealed"),
    ("skipped", "skipped"),
    ("not_applicable", "not applicable"),
    ("own_decision", "own-decision"),
)


def read_story(pkg: Package) -> tuple[str | None, str | None]:
    """``(title, owner)`` as last recorded in the overview."""
    try:
        text = pkg.overview_path.read_text(encoding="utf-8")
    except OSError:
        return None, None
    title, owner = _TITLE.search(text), _OWNER.search(text)
    return (title["v"].strip() or None if title else None), (owner["v"].strip() or None if owner else None)


# ---- the derived model


@dataclass
class Model:
    states: dict[str, StageState]
    current: str | None
    artifacts: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    accepted_risks: list[dict[str, str]] = field(default_factory=list)
    open_challenges: list[str] = field(default_factory=list)
    low_challenges: dict[str, list[str]] = field(default_factory=dict)
    pending_clarifications: list[str] = field(default_factory=list)
    overrides: list[dict[str, str]] = field(default_factory=list)
    issues: list[Finding] = field(default_factory=list)
    abbreviated: list[dict[str, str]] = field(default_factory=list)
    comprehension: dict[str, dict[str, Any]] = field(default_factory=dict)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    blocked_work: list[dict[str, Any]] = field(default_factory=list)
    rederive: list[str] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
    recent_changes: list[dict[str, Any]] = field(default_factory=list)
    unsettled: dict[str, list[str]] = field(default_factory=dict)
    touched_artifacts: dict[str, str] = field(default_factory=dict)
    untouched_artifacts: list[str] = field(default_factory=list)
    deferred_challenges: list[dict[str, str]] = field(default_factory=list)
    needs_review: dict[str, int] = field(default_factory=dict)
    profile: dict[str, Any] | None = None

    @property
    def overall(self) -> str:
        return "complete" if self.current is None else self.states[self.current].state


def _collect_completion(pkg: Package, model: Model) -> None:
    from . import verification
    from .records import deferred_challenges

    model.deferred_challenges = deferred_challenges(pkg)
    if not pkg.exists("verification"):
        return
    try:
        model.touched_artifacts = staleness.touched_artifacts(pkg)
        model.untouched_artifacts = [
            a for a in verification.approved_artifact_ids(pkg) if a not in model.touched_artifacts
        ]
    except UnicodeDecodeError:
        return


def collect(pkg: Package) -> Model:
    states = pkg.states()
    model = Model(states, pkg.current_stage())
    parsed_by_stage: dict[str, ParseResult] = {}
    issues: list[Finding] = []
    blocking: list[tuple[bool, str]] = []
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            issues.extend(states[stage].findings)
            continue
        parsed = parse_document(doc)
        parsed_by_stage[stage] = parsed
        model.needs_review[stage] = blockstatus.counts(pkg, stage)["needs_review"]
        scan = scan_document(doc, stage, parsed, root=pkg.root)
        issues.extend(f for f in [*doc.findings, *parsed.findings] if f.code in INTEGRITY_CODES)
        issues.extend(f for f in states[stage].findings if f.code in RECORD_INTEGRITY_CODES)
        rule_findings = check_stage(pkg, stage, write=False).findings if stage in CRITERIA_BY_STAGE else []
        for artifact in scan.artifacts:
            model.artifacts.append(
                {
                    "id": artifact.id,
                    "kind": artifact.kind or "unknown",
                    "depicts": artifact.depicts or "",
                    "stage": stage,
                    "form": artifact.form or "none",
                    "state": artifact_state(
                        artifact, [*scan.findings, *rule_findings], states[stage].approval
                    ),
                    "title": artifact.title,
                }
            )
        for item in parsed.items:
            if item.kind == "OQ":
                status = item.status or "open"
                if status == "open":
                    model.open_questions.append(item.id)
                elif status == "accepted":
                    model.accepted_risks.append(
                        {"id": item.id, "by": item.accepted_by or "unknown", "stage": stage}
                    )
            elif item.kind == "AIS" and "pending-clarification" in item.tags:
                model.pending_clarifications.append(item.id)
        for record in doc.records():
            body = record.obj or {}
            if record.kind == "challenge" and body.get("status", "open") != "closed" and body.get("id"):
                rating = challenge_severity(body)
                if rating == "low":
                    model.low_challenges.setdefault(stage, []).append(str(body["id"]))
                else:
                    blocking.append((rating != "high", str(body["id"])))
            elif record.kind == "override" and body.get("id"):
                model.overrides.append(
                    {
                        "id": str(body["id"]),
                        "stage": str(body.get("stage", stage)),
                        "criterion": str(body.get("criterion", "")),
                        "by": str(body.get("by", "")),
                    }
                )
            elif record.kind == "abbreviation":
                model.abbreviated.append({"stage": stage, "by": str(body.get("by", "unknown"))})
        if stage in ("functional", "technical"):
            record_obj = pkg.record(stage, "comprehension")
            model.comprehension[stage] = comprehension.summarise(record_obj, states[stage].fingerprint or "")
    from . import profile as profiles

    model.profile = profiles.recorded(pkg)
    held = profiles.override(pkg)
    if held is not None:
        model.overrides.append(
            {
                "id": str(held["id"]),
                "stage": "story",
                "criterion": f"{held['criterion']} ({', '.join(held['scope'])})",
                "by": str(held["by"]),
            }
        )
    loaded = pkg.record_file()
    if loaded.error is not None:
        issues.append(Finding("malformed-record-file", "eil-record.json", loaded.error))
    seen: set[tuple[str, str]] = set()
    for finding in [*issues, *[f for f in story_findings(parsed_by_stage) if f.code in INTEGRITY_CODES]]:
        if (finding.code, finding.where) not in seen:
            seen.add((finding.code, finding.where))
            model.issues.append(finding)
    model.open_challenges = [cid for _, cid in sorted(set(blocking))]
    model.low_challenges = {stage: sorted(set(ids)) for stage, ids in model.low_challenges.items()}
    model.aliases = _aliases(pkg)
    if any(pkg.exists(stage) for stage in staleness.DERIVED):
        try:
            blocked, again = staleness.scoped_work(pkg)
        except UnicodeDecodeError:
            blocked, again = {}, {}
        model.blocked_work = staleness.rows(blocked)
        model.rederive = list(again)
    _collect_backwards(pkg, model)
    _collect_completion(pkg, model)
    return model


def _collect_backwards(pkg: Package, model: Model) -> None:
    from . import changelog, corrections, reviews

    try:
        model.corrections = [
            {"id": c.get("id"), "item": c.get("item"), "owner": stage, "found_in": c.get("found_in")}
            for stage, c in corrections.open_all(pkg)
        ]
        model.recent_changes = changelog.recent(pkg)
        for stage in pkg.existing_stages():
            keys = [e.key for e in reviews.build_list(pkg, stage, "unsettled-challenges").entries]
            if keys:
                model.unsettled[stage] = keys
    except (OSError, UnicodeDecodeError):
        pass


def _aliases(pkg: Package) -> list[dict[str, Any]]:
    """Every alias that exists or should, with its derived fault (FR-051)."""
    return [state.to_json() for state in aliases.classify(pkg)]


# ---- rendering


def _join(values: list[str], empty: str = "none") -> str:
    return ", ".join(values) if values else empty


def _document_rows(pkg: Package, model: Model) -> str:
    """One row per document. The count of blocks needing review stands in for the ``[ai-draft]`` cue,
    which is no longer written into a document (D-50, R-26): `eil show` marks the blocks themselves."""
    rows = [
        "| Document | State | Blocks needing review |",
        "|---|---|---|",
        f"| [{OVERVIEW}]({OVERVIEW}) | generated | |",
    ]
    for stage in STAGES:
        name = DOC_FILES[stage]
        label = f"[{name}]({name})" if pkg.exists(stage) else name
        pending = model.needs_review.get(stage)
        rows.append(f"| {label} | {model.states[stage].state} | {pending if pending is not None else ''} |")
    return "\n".join(rows)


def _story_notes(pkg: Package) -> str:
    """Lines under Story from the story-level records: how the story was started (D-47) and its profile
    (D-52), shown with the override it carries."""
    start = pkg.story_record().get("start") or {}
    lines = []
    from . import profile as profiles

    found = profiles.recorded(pkg)
    if found is not None:
        line = f"- Small-story profile: authorised by {found.get('by')} on {str(found.get('at', ''))[:10]}: {found.get('reason')}"
        held = found.get("override") or {}
        if held:
            line += f". Override {held.get('id')} of unreviewed-ai-content for plan and task entry"
        withdrawn = found.get("withdrawn")
        if withdrawn:
            line += f" (withdrawn by {withdrawn.get('by')} on {str(withdrawn.get('at', ''))[:10]}: {withdrawn.get('reason')})"
        lines.append(line)
    if start.get("branch_confirmed_by"):
        lines.append(
            f"- Started on branch {start.get('branch')}, confirmed by {start['branch_confirmed_by']}"
            + (
                f' ("{start["reply"]}" to "{start["question"]}")'
                if start.get("reply") and start.get("question")
                else ""
            )
        )
    elif start.get("branch"):
        lines.append(f"- Started on branch {start['branch']}")
    return "".join(f"{line}\n" for line in lines)


def _artefact_rows(model: Model) -> str:
    if not model.artifacts:
        return "none"
    rows = ["| Artefact | Kind | Stage | State | Link |", "|---|---|---|---|---|"]
    for a in model.artifacts:
        kind = f"image of {a['depicts']} (not structurally checked)" if a["kind"] == "image" else a["kind"]
        rows.append(
            f"| {a['id']} | {kind} | {a['stage']} | {a['state']} | [{a['title']}]({DOC_FILES[a['stage']]}) |"
        )
    return "\n".join(rows)


def _comprehension_text(approval: dict[str, Any]) -> str:
    found = approval.get("comprehension")
    if not isinstance(found, dict):
        return ""
    parts = [f"{label} {found[key]}" for key, label in _OUTCOME_LABELS if found.get(key)]
    return " · ".join(parts)


def _reached_text(approval: dict[str, Any]) -> str:
    reached = reached_of(approval)
    if reached == "first":
        return "first approval"
    if reached == "re-signed-without-comparison":
        return "re-signed without comparison"
    rests_on = approval.get("rests_on") or []
    label = "carried forward" if reached == "carried-forward" else "reviewed"
    return f"{label}, resting on {', '.join(rests_on)}" if rests_on else label


def _approval_rows(model: Model) -> str:
    rows = []
    for stage in STAGES:
        state = model.states[stage]
        if state.state == "approved" and state.approval:
            a = state.approval
            fingerprint = str(a.get("fingerprint", ""))
            short = fingerprint.split(":", 1)[-1][:12]
            rows.append(
                f"| {stage} | {a.get('by', '')} | {a.get('at', '')} | {short} | {_comprehension_text(a)} | {_reached_text(a)} |"
            )
    if not rows:
        return "none"
    return "\n".join(
        [
            "| Stage | Approved by | At | Fingerprint | Comprehension | Reached |",
            "|---|---|---|---|---|---|",
            *rows,
        ]
    )


def _outstanding(model: Model) -> str:
    overrides = [f"{o['id']} ({o['stage']} {o['criterion']} by {o['by']})" for o in model.overrides]
    issues = [f"{f.code} at {f.where}" for f in model.issues]
    blocked = [f"{r['id']} ({r['because'][0]})" for r in model.blocked_work]
    fixing = [f"{c['id']} ({c['item']} in {c['owner']})" for c in model.corrections]
    unsettled = [f"{k} ({stage})" for stage, keys in model.unsettled.items() for k in keys]
    recent = [f"{r.get('at', '')} {r.get('item', '')}: {r.get('summary', '')}" for r in model.recent_changes]
    return "\n".join(
        [
            *([f"- Open corrections: {'; '.join(fixing)}"] if fixing else []),
            *([f"- Unsettled challenges: {'; '.join(unsettled)}"] if unsettled else []),
            *([f"- Recent changes: {'; '.join(recent)}"] if recent else []),
            *([f"- Blocked work: {'; '.join(blocked)}"] if blocked else []),
            f"- Open questions: {_join(model.open_questions)}",
            f"- Open challenges: {_join(model.open_challenges)}",
            *(
                [
                    f"- Low challenges (outstanding, not blocking): {_join(sorted(c for v in model.low_challenges.values() for c in v))}"
                ]
                if model.low_challenges
                else []
            ),
            f"- Pending clarifications: {_join(model.pending_clarifications)}",
            f"- Overrides: {_join(overrides)}",
            f"- Issues: {'; '.join(issues) if issues else 'none'}",
        ]
    )


def _accepted_risks(model: Model) -> str:
    if not model.accepted_risks:
        return "none"
    return "\n".join(f"- {r['id']} (accepted by {r['by']}, {r['stage']})" for r in model.accepted_risks)


def _abbreviated(model: Model) -> str:
    if not model.abbreviated:
        return "none"
    return "\n".join(f"- {a['stage']} (authorised by {a['by']})" for a in model.abbreviated)


def _mirrors(model: Model) -> str:
    mirrors = [a for a in model.aliases if a["form"] == "mirror"]
    if not mirrors:
        return "none"
    return "\n".join(f"- {a['name']} (mirror of {a['target']})" for a in mirrors)


def render(pkg: Package, template: str, title: str, owner: str) -> str:
    model = collect(pkg)
    values = {
        "title": title,
        "owner": owner,
        "story_notes": _story_notes(pkg),
        "current_stage": model.current or "complete",
        "overall_status": model.overall,
        "documents": _document_rows(pkg, model),
        "artefacts": _artefact_rows(model),
        "approvals": _approval_rows(model),
        "outstanding": _outstanding(model),
        "accepted_risks": _accepted_risks(model),
        "abbreviated": _abbreviated(model),
        "mirrors": _mirrors(model),
    }
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text.rstrip("\n") + "\n"


def _rendered(pkg: Package, template: str, title: str | None, owner: str | None) -> str:
    known_title, known_owner = read_story(pkg)
    return render(
        pkg, template, title or known_title or "Untitled story", owner or known_owner or "unassigned"
    )


def write(pkg: Package, template: str, title: str | None = None, owner: str | None = None) -> bool:
    """Rewrite ``s00`` from the records. Returns whether the file changed."""
    text = _rendered(pkg, template, title, owner)
    path = pkg.overview_path
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_bytes(text.encode("utf-8"))
    return True


def drifted(pkg: Package, template: str) -> bool:
    """True if ``s00`` differs from what the records give (hand-edited, or simply out of date)."""
    try:
        current = pkg.overview_path.read_text(encoding="utf-8")
    except OSError:
        return True
    return current != _rendered(pkg, template, None, None)


# ---- status


def _open_tasks(pkg: Package) -> int:
    try:
        return len(_OPEN_TASK.findall(pkg.doc_path("tasks").read_text(encoding="utf-8")))
    except OSError:
        return 0


def _action(
    kind: str,
    stage: str | None,
    command: str | None,
    message: str,
    purpose: str = "awareness",
    question: str | None = None,
) -> dict[str, Any]:
    out = {"kind": kind, "stage": stage, "command": command, "message": message, "purpose": purpose}
    if question:
        out["question"] = question  # the helper's own question; the prompt asks it and nothing more (D-59)
    return out


def next_action(pkg: Package, model: Model) -> dict[str, Any]:
    """The single next step as data: ``kind`` is ``draft`` or ``check`` (work the AI may do alone),
    ``human`` (a person must decide; nothing runs automatically) or ``done``."""
    stage = model.current
    if stage is None:
        completion = model.states["completion"]
        if completion.state == "approved" and completion.approval:
            a = completion.approval
            return _action(
                "done",
                None,
                None,
                f"Story complete; approved by {a.get('by')} on {str(a.get('at', ''))[:10]}.",
            )
        return _action("done", None, None, "All stages are complete.")
    state = model.states[stage]
    command = START_COMMANDS[stage]
    if model.open_challenges and state.state in ("draft", "in-review", "needs-re-review"):
        return _action(
            "human",
            stage,
            CHALLENGE_COMMAND,
            f"Answer challenge {model.open_challenges[0]}, then approve {stage}.",
            "decision",
        )
    if model.unsettled:
        first = next(iter(model.unsettled))
        return _action(
            "human",
            first,
            "/speckit-eil-accept",
            f"Review the challenges set aside in {first} whose target changed since "
            f"({', '.join(model.unsettled[first])}): eil review list --stage {first} --kind unsettled-challenges.",
            "decision",
        )
    if state.state == "not-started":
        if stage == "verification" and _open_tasks(pkg):
            return _action(
                "draft",
                stage,
                IMPLEMENT_COMMAND,
                f"Implement the open tasks: run {IMPLEMENT_COMMAND}, then start verification.",
            )
        return _action("draft", stage, command, f"Start {stage}: run {command}.")
    if state.state == "needs-re-review":
        return _action(
            "human",
            stage,
            APPROVE_COMMAND,
            f"Re-review {stage} ({state.reason}): run /speckit-eil-accept to list what changed, answer it "
            f"in one reply and confirm; or approve it again with {APPROVE_COMMAND}.",
            "validation",
        )
    if state.state == "in-review":
        from .records import APPROVAL_QUESTIONS

        return _action(
            "human",
            stage,
            APPROVE_COMMAND,
            f"Approve {stage} with {APPROVE_COMMAND}.",
            "approval",
            question=APPROVAL_QUESTIONS.get(stage),
        )
    if stage in CRITERIA_BY_STAGE:
        unmet = check_stage(pkg, stage, write=False).unmet()
        if unmet and all(c.kind == "judgment" and c.reason == "no judgment supplied" for c in unmet):
            return _action(
                "check",
                stage,
                command,
                f"Have the AI judge {stage}: {len(unmet)} judgment criteria have no verdict "
                f"(run eil check --stage {stage} --judgments FILE).",
            )
        if unmet:
            ids = ", ".join(c.id for c in unmet[:6]) + (
                f" and {len(unmet) - 6} more" if len(unmet) > 6 else ""
            )
            return _action(
                "draft",
                stage,
                command,
                f"Meet the gate for {stage}: {len(unmet)} criteria are not met ({ids}). Run eil check for the reasons.",
            )
    return _action("draft", stage, command, f"Continue {stage}, then run eil check --stage {stage}.")


def status(pkg: Package, template: str | None = None) -> dict[str, Any]:
    """The derived state of the story. Reads everything, writes nothing (determinism 9)."""
    model = collect(pkg)
    action = next_action(pkg, model)
    title, owner = read_story(pkg)
    project = pkg.project_root
    try:
        feature_dir = str(pkg.root.resolve().relative_to(project)) if project else str(pkg.root)
    except ValueError:
        feature_dir = str(pkg.root)
    stages: dict[str, Any] = {}
    reached = pkg.affected_items()
    for stage in STAGES:
        state = model.states[stage]
        entry: dict[str, Any] = {"state": state.state, "abbreviated": state.abbreviated}
        if state.reason:
            entry["reason"] = state.reason
        if state.note:
            entry["note"] = state.note
        if reached.get(stage):
            entry["affected_items"] = reached[stage]
        if state.state == "approved" and state.approval:
            entry["approval"] = {k: state.approval.get(k) for k in ("by", "at", "fingerprint")}
            entry["approval"]["reached"] = reached_of(state.approval)
            if state.approval.get("rests_on"):
                entry["approval"]["rests_on"] = state.approval["rests_on"]
        if model.low_challenges.get(stage):
            entry["outstanding_low"] = model.low_challenges[stage]
        if pkg.exists(stage):
            entry["blocks"] = blockstatus.counts(pkg, stage)
        stages[stage] = entry
    if template is None:
        overview_report: dict[str, Any] = {"current": None}
    elif drifted(pkg, template):
        overview_report = {
            "current": False,
            "message": f"{OVERVIEW} was hand-edited or is out of date; the stage documents win. Run eil sync to regenerate it.",
        }
    else:
        overview_report = {"current": True}
    return {
        "governed": True,
        "feature_dir": feature_dir,
        "title": title,
        "owner": owner,
        "current_stage": model.current,
        "stages": stages,
        "outstanding": {
            "open_questions": model.open_questions,
            "open_challenges": model.open_challenges,
            "low_challenges": sorted(c for ids in model.low_challenges.values() for c in ids),
            "pending_clarifications": model.pending_clarifications,
            "accepted_risks": [r["id"] for r in model.accepted_risks],
            "overrides": [o["id"] for o in model.overrides],
            "deferred_challenges": model.deferred_challenges,
        },
        "diagram_currency": {"touched": model.touched_artifacts, "untouched": model.untouched_artifacts},
        "comprehension": model.comprehension,
        "artifacts": [{k: a[k] for k in ("id", "kind", "stage", "form", "state")} for a in model.artifacts],
        "aliases": model.aliases,
        "overview": overview_report,
        "issues": [f.to_json() for f in model.issues],
        "blocked_work": model.blocked_work,
        "rederive": model.rederive,
        "corrections": model.corrections,
        "recent_changes": model.recent_changes,
        "profile": model.profile,
        "next": action["message"],
        "next_action": action,
    }


__all__ = [
    "APPROVABLE",
    "AUTOMATIC_KINDS",
    "collect",
    "drifted",
    "next_action",
    "read_story",
    "render",
    "status",
    "write",
]

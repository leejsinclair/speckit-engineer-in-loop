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

from . import aliases, comprehension
from .artifacts import artifact_state, scan_document
from .gates import CRITERIA_BY_STAGE, INTEGRITY_CODES, check_stage
from .package import APPROVABLE, DOC_FILES, OVERVIEW, STAGES, Package, StageState
from .results import Finding
from .trace import ParseResult, parse_document, story_findings

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
    pending_clarifications: list[str] = field(default_factory=list)
    overrides: list[dict[str, str]] = field(default_factory=list)
    issues: list[Finding] = field(default_factory=list)
    abbreviated: list[dict[str, str]] = field(default_factory=list)
    comprehension: dict[str, dict[str, Any]] = field(default_factory=dict)
    aliases: list[dict[str, Any]] = field(default_factory=list)

    @property
    def overall(self) -> str:
        return "complete" if self.current is None else self.states[self.current].state


def collect(pkg: Package) -> Model:
    states = pkg.states()
    model = Model(states, pkg.current_stage())
    parsed_by_stage: dict[str, ParseResult] = {}
    issues: list[Finding] = []
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            issues.extend(states[stage].findings)
            continue
        parsed = parse_document(doc)
        parsed_by_stage[stage] = parsed
        scan = scan_document(doc, stage, parsed, root=pkg.root)
        issues.extend(f for f in [*doc.findings, *parsed.findings] if f.code in INTEGRITY_CODES)
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
                model.open_challenges.append(str(body["id"]))
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
            record_obj = doc.read_region("comprehension").obj
            model.comprehension[stage] = comprehension.summarise(record_obj, states[stage].fingerprint or "")
    seen: set[tuple[str, str]] = set()
    for finding in [*issues, *[f for f in story_findings(parsed_by_stage) if f.code in INTEGRITY_CODES]]:
        if (finding.code, finding.where) not in seen:
            seen.add((finding.code, finding.where))
            model.issues.append(finding)
    model.open_challenges = sorted(set(model.open_challenges))
    model.aliases = _aliases(pkg)
    return model


def _aliases(pkg: Package) -> list[dict[str, Any]]:
    """Every alias that exists or should, with its derived fault (FR-051)."""
    return [state.to_json() for state in aliases.classify(pkg)]


# ---- rendering


def _join(values: list[str], empty: str = "none") -> str:
    return ", ".join(values) if values else empty


def _document_rows(pkg: Package, model: Model) -> str:
    rows = ["| Document | State |", "|---|---|", f"| [{OVERVIEW}]({OVERVIEW}) | generated |"]
    for stage in STAGES:
        name = DOC_FILES[stage]
        label = f"[{name}]({name})" if pkg.exists(stage) else name
        rows.append(f"| {label} | {model.states[stage].state} |")
    return "\n".join(rows)


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


def _approval_rows(model: Model) -> str:
    rows = []
    for stage in STAGES:
        state = model.states[stage]
        if state.state == "approved" and state.approval:
            a = state.approval
            fingerprint = str(a.get("fingerprint", ""))
            short = fingerprint.split(":", 1)[-1][:12]
            rows.append(
                f"| {stage} | {a.get('by', '')} | {a.get('at', '')} | {short} | {_comprehension_text(a)} |"
            )
    if not rows:
        return "none"
    return "\n".join(
        ["| Stage | Approved by | At | Fingerprint | Comprehension |", "|---|---|---|---|---|", *rows]
    )


def _outstanding(model: Model) -> str:
    overrides = [f"{o['id']} ({o['stage']} {o['criterion']} by {o['by']})" for o in model.overrides]
    issues = [f"{f.code} at {f.where}" for f in model.issues]
    return "\n".join(
        [
            f"- Open questions: {_join(model.open_questions)}",
            f"- Open challenges: {_join(model.open_challenges)}",
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


def _action(kind: str, stage: str | None, command: str | None, message: str) -> dict[str, Any]:
    return {"kind": kind, "stage": stage, "command": command, "message": message}


def next_action(pkg: Package, model: Model) -> dict[str, Any]:
    """The single next step as data: ``kind`` is ``draft`` or ``check`` (work the AI may do alone),
    ``human`` (a person must decide; nothing runs automatically) or ``done``."""
    stage = model.current
    if stage is None:
        return _action("done", None, None, "All stages are complete.")
    state = model.states[stage]
    command = START_COMMANDS[stage]
    if model.open_challenges and state.state in ("draft", "in-review", "needs-re-review"):
        return _action(
            "human",
            stage,
            CHALLENGE_COMMAND,
            f"Answer challenge {model.open_challenges[0]}, then approve {stage}.",
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
            f"Re-review {stage} ({state.reason}). If every change is already a recorded decision, "
            f"/speckit-eil-amend can re-sign it from those ids; otherwise walk through each change "
            f"with /speckit-eil-review-changes; or approve it again with {APPROVE_COMMAND}.",
        )
    if state.state == "in-review":
        return _action("human", stage, APPROVE_COMMAND, f"Approve {stage} with {APPROVE_COMMAND}.")
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
            "pending_clarifications": model.pending_clarifications,
            "accepted_risks": [r["id"] for r in model.accepted_risks],
            "overrides": [o["id"] for o in model.overrides],
        },
        "comprehension": model.comprehension,
        "artifacts": [{k: a[k] for k in ("id", "kind", "stage", "form", "state")} for a in model.artifacts],
        "aliases": model.aliases,
        "overview": overview_report,
        "issues": [f.to_json() for f in model.issues],
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

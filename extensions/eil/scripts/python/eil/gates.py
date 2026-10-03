"""Quality gates: criteria as data, and their evaluation (tasks T039, T041; FR-009, FR-010).

Each stage has a table of criteria. A criterion is *structural* or *traceability* (decided by code
and never by the AI), or *judgment* (the AI's assessment, labelled as such, which only a human's
approval closes). A judgment criterion has a structural precondition first: the sections it is about
must exist, so the AI cannot say "met" about text that is not there.

The AI's verdicts arrive through ``check --judgments`` and are stored, labelled, in the document's
assessment region together with the fingerprint they were made against. A verdict is honoured only
while that fingerprint is current, so an edit after the AI's assessment invalidates it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import comprehension, staleness, verification
from .artifacts import DIAGRAM_KINDS, ArtifactScan, orphan_findings, scan_document
from .blocks import Doc, RegionError, ensure_region
from .clock import utc_now
from .diagrams import (
    Diagram,
    component_problems,
    element_names,
    normalise_name,
    sequence_problems,
    store_problems,
    zoom_problems,
)
from .fingerprint import fingerprint_text, fingerprint_text_001
from .identity import is_ai_actor
from .package import DOC_FILES, STAGES, Package
from .results import Finding
from .trace import (
    _ITEM_PREFIX,
    ADMINISTRATIVE_SECTIONS,
    DECISION_FIELDS,
    ParseResult,
    coverage_gaps,
    decision_fields,
    evidence_fields,
    is_ai_decided,
    item_hash,
    parse_document,
    section_fingerprints,
    story_findings,
)

STRUCTURAL, TRACEABILITY, JUDGMENT = "structural", "traceability", "judgment"
AI_PREFIX = "AI assessment: "
ASSESSMENT_LISTS = ("ambiguity", "missing", "contradictions", "unsupported_assumptions", "untestable")
STRUCTURE_TAG = "structure: "

# Findings that mean the document itself is malformed, whatever a criterion says.
INTEGRITY_CODES = frozenset(
    {
        "malformed-region",
        "malformed-record",
        "malformed-fence",
        "malformed-item",
        "duplicate-id",
        "dangling-trace",
        "decided-source-invalid",
    }
)
# The criterion the small-story profile meets by its own recorded authorisation (D-52).
PROFILE_CRITERION = "FUN-G15"
# Checks an override may waive besides the criteria of the stage's table.
EXTRA_OVERRIDABLE = ("unreviewed-ai-content",)


@dataclass(frozen=True)
class Criterion:
    id: str
    text: str
    kind: str
    headings: tuple[str, ...] = ()  # sections that must exist (or be listed as not applicable)


CRITERIA_BY_STAGE: dict[str, tuple[Criterion, ...]] = {
    "requirements": (
        Criterion(
            "REQ-G01", "The problem is clearly understood.", JUDGMENT, ("Background", "Problem Statement")
        ),
        Criterion("REQ-G02", "The desired outcome is explicit.", STRUCTURAL, ("Desired Outcome",)),
        Criterion(
            "REQ-G03",
            "The relevant users and stakeholders are identified.",
            STRUCTURAL,
            ("Users and Stakeholders",),
        ),
        Criterion("REQ-G04", "The major use cases are understood.", STRUCTURAL, ("Use Cases",)),
        Criterion("REQ-G05", "Scope and exclusions are explicit.", STRUCTURAL, ("In Scope", "Out of Scope")),
        Criterion("REQ-G06", "Known constraints are documented.", STRUCTURAL, ("Constraints",)),
        Criterion("REQ-G07", "Dependencies are identified.", STRUCTURAL, ("Dependencies",)),
        Criterion("REQ-G08", "Material risks are understood.", STRUCTURAL, ("Risks",)),
        Criterion("REQ-G09", "Important assumptions are identified.", STRUCTURAL, ("Assumptions",)),
        Criterion(
            "REQ-G10",
            "Material open questions have been resolved or explicitly accepted.",
            TRACEABILITY,
            ("Open Questions",),
        ),
        Criterion("REQ-G11", "Success can be objectively assessed.", JUDGMENT, ("Success Criteria",)),
        Criterion("REQ-G12", "The requirements do not unnecessarily prescribe implementation.", JUDGMENT),
        Criterion(
            "REQ-G13",
            "A developer or business stakeholder can explain why the work is being undertaken.",
            JUDGMENT,
        ),
        Criterion(
            "REQ-G14",
            "The system context diagram shows the system, its users and its dependencies, and what is "
            "existing, new or changed.",
            STRUCTURAL,
        ),
    ),
}


CRITERIA_BY_STAGE["functional"] = (
    Criterion(
        "FUN-G01",
        "Functional requirements trace to approved requirements, and every requirement is covered.",
        TRACEABILITY,
        ("Functional Requirements",),
    ),
    Criterion(
        "FUN-G02",
        "Each significant use case has been described.",
        STRUCTURAL,
        ("Actors", "Use Cases and Scenarios"),
    ),
    Criterion("FUN-G03", "Business rules are explicit.", STRUCTURAL, ("Business Rules",)),
    Criterion("FUN-G04", "Inputs and outputs are defined.", STRUCTURAL, ("Inputs", "Outputs")),
    Criterion("FUN-G05", "Important state transitions are understood.", STRUCTURAL, ("State and Workflow",)),
    Criterion("FUN-G06", "Validation behaviour is defined.", STRUCTURAL, ("Validation",)),
    Criterion(
        "FUN-G07", "Important error conditions are defined.", STRUCTURAL, ("Error and Exception Behaviour",)
    ),
    Criterion(
        "FUN-G08",
        "Relevant security and audit behaviour is defined.",
        STRUCTURAL,
        ("Security and Access Behaviour", "Audit and Compliance Behaviour"),
    ),
    Criterion(
        "FUN-G09",
        "Applicable non-functional requirements are documented.",
        STRUCTURAL,
        ("Non-Functional Requirements",),
    ),
    Criterion("FUN-G10", "Acceptance criteria are testable.", JUDGMENT, ("Acceptance Criteria",)),
    Criterion("FUN-G11", "Ambiguities have been resolved or explicitly recorded.", TRACEABILITY),
    Criterion("FUN-G12", "The specification does not unnecessarily prescribe implementation.", JUDGMENT),
    Criterion(
        "FUN-G13",
        "A developer and a relevant business stakeholder can explain what the system must do without inspecting the implementation.",
        JUDGMENT,
    ),
    Criterion(
        "FUN-G14",
        "Each use case has a system-level sequence diagram of actors and the System, or a recorded reason none applies.",
        STRUCTURAL,
    ),
    Criterion(
        "FUN-G15",
        "Each screen state has a registered wireframe export, or a recorded reason there is none.",
        STRUCTURAL,
    ),
    Criterion("FUN-G16", "The comprehension check was taken on this version of the document.", STRUCTURAL),
)


CRITERIA_BY_STAGE["technical"] = (
    Criterion(
        "TEC-G01",
        "The proposed architecture satisfies the functional requirements.",
        JUDGMENT,
        ("Technical Requirements", "Architecture", "Component Design"),
    ),
    Criterion(
        "TEC-G02",
        "Significant technical decisions are explicit, complete, owned by a person and traced.",
        TRACEABILITY,
        ("Technical Decisions",),
    ),
    Criterion("TEC-G03", "Security implications have been considered.", STRUCTURAL, ("Security Design",)),
    Criterion("TEC-G04", "Data changes are understood.", STRUCTURAL, ("Data Design",)),
    Criterion(
        "TEC-G05",
        "Integration impacts are understood.",
        STRUCTURAL,
        ("API and Integration Design", "Existing System Impact"),
    ),
    Criterion("TEC-G06", "Failure behaviour is defined.", STRUCTURAL, ("Error Handling and Resilience",)),
    Criterion(
        "TEC-G07",
        "Relevant non-functional requirements are addressed.",
        STRUCTURAL,
        ("Observability", "Performance"),
    ),
    Criterion("TEC-G08", "The testing strategy is appropriate.", JUDGMENT, ("Testing Strategy",)),
    Criterion(
        "TEC-G09",
        "Deployment and migration impacts are understood.",
        STRUCTURAL,
        ("Deployment and Migration",),
    ),
    Criterion(
        "TEC-G10", "Significant alternatives have been considered.", STRUCTURAL, ("Alternatives Considered",)
    ),
    Criterion(
        "TEC-G11",
        "Material risks and trade-offs are documented.",
        STRUCTURAL,
        ("Risks and Trade-offs",),
    ),
    Criterion(
        "TEC-G12",
        "There are no unresolved technical questions that could materially change implementation.",
        TRACEABILITY,
    ),
    Criterion(
        "TEC-G13",
        "The design is consistent with existing engineering standards and architecture.",
        JUDGMENT,
    ),
    Criterion(
        "TEC-G14",
        "A developer can explain how the solution will work and why it was designed this way.",
        JUDGMENT,
    ),
    Criterion(
        "TEC-G15",
        "A container diagram shows the system's containers, consistent with the system context.",
        STRUCTURAL,
    ),
    Criterion(
        "TEC-G16",
        "Each new or changed container has a component diagram naming it, or a recorded reason none applies.",
        STRUCTURAL,
    ),
    Criterion(
        "TEC-G17",
        "Each use case has a technical sequence diagram of container or component elements citing a "
        "decision, or a recorded reason none applies.",
        STRUCTURAL,
    ),
    Criterion(
        "TEC-G18",
        "Persistent data has an ER diagram naming its data store in the container diagram, or a recorded "
        "reason there is none.",
        STRUCTURAL,
    ),
    Criterion("TEC-G19", "The comprehension check was taken on this version of the document.", STRUCTURAL),
)


AI_SPEC_HEADINGS = (
    "Functional Requirements",
    "Business Rules",
    "Technical Decisions",
    "Architectural Constraints",
    "Existing Code",
    "Interfaces",
    "Data Structures",
    "Testing Requirements",
    "Security Requirements",
    "Edge Cases",
    "Explicit Exclusions",
    "Implementation Constraints",
    "Artefacts in Scope",
)

CRITERIA_BY_STAGE["ai-spec"] = (
    Criterion(
        "AIS-G01",
        "Every section of the AI Specification is present, or listed as not applicable with a reason.",
        STRUCTURAL,
        AI_SPEC_HEADINGS,
    ),
    Criterion(
        "AIS-G02",
        "Every item traces to an approved requirement, functional requirement, decision or artefact, and "
        "nothing is written without a source.",
        TRACEABILITY,
    ),
    Criterion(
        "AIS-G03",
        "No clarification answer is pending: each has been carried to an approved earlier stage.",
        TRACEABILITY,
    ),
    Criterion(
        "AIS-G04",
        "Every artefact the agent is told to read is unchanged since its stage was approved.",
        TRACEABILITY,
    ),
    Criterion("AIS-G05", "The AI Specification draws no diagram of its own.", STRUCTURAL),
)


CRITERIA_BY_STAGE["plan"] = (
    Criterion(
        "PLN-G01",
        "Every section of the plan names the approved technical decision it is derived from.",
        TRACEABILITY,
    ),
    Criterion("PLN-G02", "The plan introduces no architecture beyond the approved decisions.", JUDGMENT),
)

CRITERIA_BY_STAGE["tasks"] = (
    Criterion(
        "TSK-G01",
        "Every task traces to an item of the AI Specification or an approved decision.",
        TRACEABILITY,
    ),
    Criterion(
        "TSK-G02",
        "Every wireframe, ER diagram and technical sequence diagram in scope is covered by at least one task.",
        TRACEABILITY,
    ),
    Criterion("TSK-G03", "No task introduces architecture beyond the approved design.", JUDGMENT),
)


CRITERIA_BY_STAGE["verification"] = (
    Criterion(
        "VER-G01",
        "The document separates automated evidence, manual evidence, exceptions and open tasks.",
        STRUCTURAL,
        ("Automated Evidence", "Manual Evidence", "Exceptions", "Open Tasks"),
    ),
    Criterion(
        "VER-G02",
        "Every requirement, functional requirement and approved artefact has a verification row.",
        TRACEABILITY,
    ),
    Criterion("VER-G03", "Every row has a status and the evidence its status needs.", STRUCTURAL),
    Criterion("VER-G04", "Every exception records who accepted it and why.", STRUCTURAL),
    Criterion("VER-G05", "Every open task is listed, none hidden.", TRACEABILITY),
    Criterion("VER-G06", "The document describes evidence and does not declare completion.", STRUCTURAL),
    Criterion(
        "VER-G07",
        "No review finding is open, and every upstream-rooted one has its correction.",
        TRACEABILITY,
    ),
)

COMPLETION_HEADINGS = (
    "Completion Status",
    "Implementation Summary",
    "Requirements Satisfied",
    "Outstanding Issues",
    "Accepted Deviations",
    "Relevant Technical Decisions",
    "Verification Summary",
    "Deployment Status",
    "Documentation and Support Implications",
    "Diagram Currency",
)

CRITERIA_BY_STAGE["completion"] = (
    Criterion(
        "CMP-G01",
        "Every section of the completion record is present, or listed as not applicable with a reason.",
        STRUCTURAL,
        COMPLETION_HEADINGS,
    ),
    Criterion("CMP-G02", "The Verification document exists.", STRUCTURAL),
    Criterion(
        "CMP-G03",
        "Every requirement is verified or excepted by a named person for a stated reason.",
        TRACEABILITY,
    ),
    Criterion(
        "CMP-G04",
        "Every approved artefact is verified or excepted by a named person for a stated reason.",
        TRACEABILITY,
    ),
    Criterion(
        "CMP-G05",
        "Every approved artefact is stated current, or is a deviation accepted by a person for a stated reason.",
        STRUCTURAL,
        ("Diagram Currency",),
    ),
    Criterion(
        "CMP-G06",
        "Every ticked task is confirmed against the current version of what it traces to.",
        TRACEABILITY,
    ),
    Criterion(
        "CMP-G07",
        "Every evidence row is confirmed against the current version of what it traces to.",
        TRACEABILITY,
    ),
    Criterion("CMP-G08", "No review finding is open.", TRACEABILITY),
)


def criteria_for(stage: str) -> tuple[Criterion, ...]:
    if stage not in CRITERIA_BY_STAGE:
        raise NotImplementedError(f"no gate is defined for stage {stage!r} yet")
    return CRITERIA_BY_STAGE[stage]


def overridable_ids(stage: str) -> tuple[str, ...]:
    return tuple(c.id for c in CRITERIA_BY_STAGE.get(stage, ())) + EXTRA_OVERRIDABLE


# ---- sections


_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_BULLET = re.compile(r"^\s{0,3}[-*]\s+(?P<rest>.+)$")


@dataclass
class Section:
    title: str
    level: int
    line: int
    content: list[str]

    @property
    def has_content(self) -> bool:
        return any(text.strip() for text in self.content)


def split_name_reason(rest: str) -> tuple[str, str]:
    """``**Name**: reason``, ``Name: reason`` or ``Name — reason`` into ``(name, reason)``."""
    bold = re.match(r"^\*\*(?P<n>.+?)\*\*\s*(?P<r>.*)$", rest)
    if bold:
        name, reason = bold["n"], bold["r"].lstrip(" :—–-").strip()
    else:
        parts = re.split(r"\s*(?::|—|–| - )\s*", rest, maxsplit=1)
        name, reason = parts[0], (parts[1] if len(parts) > 1 else "")
    return name.strip().strip("`").strip(), reason.strip()


class Sections:
    """The headings of a document and what is under each (fences count as content; comments do not)."""

    def __init__(self, doc: Doc) -> None:
        heads = []
        for index, line in enumerate(doc.lines):
            match = _HEADING.match(line.live) if line.kind == "text" else None
            if match:
                heads.append((index, len(match["hashes"]), match["title"].strip().rstrip(":")))
        self.sections: list[Section] = []
        for position, (index, level, title) in enumerate(heads):
            end = len(doc.lines)
            for later_index, later_level, _ in heads[position + 1 :]:
                if later_level <= level:
                    end = later_index
                    break
            content = [
                (row.raw if row.kind.startswith("fence") else row.live) for row in doc.lines[index + 1 : end]
            ]
            self.sections.append(
                Section(title, level, doc.lines[index].no, [c for c in content if c.strip()])
            )

    def find(self, name: str) -> Section | None:
        wanted = normalise_name(name)
        return next((s for s in self.sections if normalise_name(s.title) == wanted), None)

    def named_list(self, heading: str) -> list[str]:
        section = self.find(heading)
        if section is None:
            return []
        names = []
        for text in section.content:
            match = _BULLET.match(text)
            if match:
                names.append(split_name_reason(match["rest"])[0])
        return names

    def not_applicable(self) -> dict[str, str]:
        """Sections removed with a reason: ``normalised name -> reason`` (FR-018)."""
        section = self.find("Not applicable")
        entries: dict[str, str] = {}
        for text in section.content if section else []:
            match = _BULLET.match(text)
            if match:
                name, reason = split_name_reason(match["rest"])
                entries[normalise_name(name)] = reason
        return entries


# ---- evaluation context


@dataclass
class GateContext:
    pkg: Package
    stage: str
    doc: Doc
    text: str
    parsed: ParseResult
    artifacts: ArtifactScan
    sections: Sections
    na: dict[str, str]
    overrides: dict[str, dict[str, Any]]
    findings: list[Finding] = field(default_factory=list)
    structure_missing: list[str] = field(default_factory=list)
    upstream: dict[str, ParseResult] = field(default_factory=dict)
    cache: dict[Any, Any] = field(default_factory=dict)

    def note(self, finding: Finding) -> None:
        if finding not in self.findings:
            self.findings.append(finding)


def heading_problems(ctx: GateContext, names: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    for name in names:
        reason = ctx.na.get(normalise_name(name))
        if reason is not None:
            if not reason:
                problems.append(f"'{name}' is listed under Not applicable but gives no reason")
            continue
        section = ctx.sections.find(name)
        if section is None:
            problems.append(f"missing section '{name}'")
        elif not section.has_content:
            problems.append(f"section '{name}' is empty")
    return problems


# ---- code-decided checks beyond the headings


def _check_use_cases(ctx: GateContext) -> list[str]:
    if "use cases" in ctx.na or any(item.kind == "UC" for item in ctx.parsed.items):
        return []
    return ["no UC item under Use Cases (add **UC-001**: ...)"]


def open_question_problems(items: list[Any]) -> list[str]:
    """Questions that are open and material, or accepted with nobody named (FR-023)."""
    problems: list[str] = []
    for item in items:
        if item.kind != "OQ":
            continue
        material = True if item.material is None else item.material
        status = item.status or "open"
        if status == "open" and material:
            problems.append(
                f"{item.id} is open and material; resolve it, or accept it with (status: accepted) (accepted-by: NAME)"
            )
        elif status == "accepted" and material and not item.accepted_by:
            problems.append(f"{item.id} is accepted but has no (accepted-by: NAME)")
    return problems


def _check_open_questions(ctx: GateContext) -> list[str]:
    return open_question_problems(ctx.parsed.items)


def _check_context_diagram(ctx: GateContext) -> list[str]:
    problems = [f"{f.code}: {f.message}" for f in ctx.artifacts.findings]
    diagrams = [a for a in ctx.artifacts.artifacts if a.kind == "c4-context" and a.diagram is not None]
    if not diagrams:
        problems.append("no c4-context diagram (the system context, FR-072)")
        return problems
    present = {normalise_name(e.label) for a in diagrams for e in a.diagram.elements}  # type: ignore[union-attr]
    first = diagrams[0].id
    for heading in ("Users and Stakeholders", "Dependencies"):
        for name in ctx.sections.named_list(heading):
            if normalise_name(name) not in present:
                message = (
                    f"rule e: '{name}' ({heading}) does not appear in the system context diagram {first}"
                )
                ctx.note(Finding("diagram-inconsistent", first, message))
                problems.append(message)
    for artifact in diagrams:
        for element in artifact.diagram.elements:  # type: ignore[union-attr]
            if element.marker is None:
                message = f"rule f: element '{element.label}' in {artifact.id} has no [existing], [new] or [changed] marker"
                ctx.note(Finding("diagram-inconsistent", artifact.id, message))
                problems.append(message)
    return problems


CHECKS: dict[str, Callable[[GateContext], list[str]]] = {
    "REQ-G04": _check_use_cases,
    "REQ-G10": _check_open_questions,
    "REQ-G14": _check_context_diagram,
}


# ---- functional checks


def _own_ids(ctx: GateContext, *kinds: str) -> list[str]:
    return [i.id for i in ctx.parsed.items if i.kind in kinds]


def _check_functional_traceability(ctx: GateContext) -> list[str]:
    requirements = ctx.upstream.get("requirements")
    if requirements is None:
        return ["the requirements document is missing, so nothing can be traced"]
    gaps = coverage_gaps(requirements, ctx.parsed)
    problems = [f"{i} traces to no requirement or use case" for i in gaps.untraceable]
    derived = set(_own_ids(ctx, "FR", "NFR"))
    problems += [f.message for f in ctx.findings if f.code == "dangling-trace" and f.where in derived]
    problems += [f"{i} has no functional requirement" for i in gaps.uncovered_requirements]
    return problems


def _check_use_cases_described(ctx: GateContext) -> list[str]:
    section = ctx.sections.find("Use Cases and Scenarios")
    requirements = ctx.upstream.get("requirements")
    if section is None or requirements is None or "use cases and scenarios" in ctx.na:
        return []
    text = "\n".join(section.content)
    return [
        f"{i.id} is not described under Use Cases and Scenarios"
        for i in requirements.items
        if i.kind == "UC" and i.id not in text
    ]


def _check_nfr_items(ctx: GateContext) -> list[str]:
    if "non-functional requirements" in ctx.na or any(i.kind == "NFR" for i in ctx.parsed.items):
        return []
    return ["no NFR item under Non-Functional Requirements (add **NFR-001**: ...)"]


def _check_functional_ambiguities(ctx: GateContext) -> list[str]:
    return open_question_problems(ctx.parsed.items)


def _section_at(sections: Sections, line: int) -> str:
    enclosing = [s for s in sections.sections if s.line < line]
    return enclosing[-1].title if enclosing else ""


def _artifact_group(ctx: GateContext) -> dict[str, str]:
    """Which criterion an artifact's findings belong to: ``diagram`` (FUN-G14) or ``wireframe`` (FUN-G15)."""
    group: dict[str, str] = {}
    for art in ctx.artifacts.artifacts:
        if art.kind in DIAGRAM_KINDS:
            group[art.id] = "diagram"
        elif art.kind in ("wireframe", "image"):
            group[art.id] = "wireframe"
        else:  # nothing readable to say what it is: it belongs to the section it sits in
            section = _section_at(ctx.sections, art.item.line)
            group[art.id] = "wireframe" if normalise_name(section) == "wireframes" else "diagram"
    return group


def _findings_for(ctx: GateContext, wanted: str) -> list[str]:
    group = _artifact_group(ctx)
    out: list[str] = []
    for f in ctx.artifacts.findings:
        if f.where in group:
            belongs = group[f.where]
        elif f.code == "diagram-unparseable" or "mermaid" in f.message:
            belongs = "diagram"
        else:
            belongs = "wireframe"
        if belongs == wanted:
            out.append(f"{f.code}: {f.message}")
    return out


def _check_sequence_diagrams(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    requirements = ctx.upstream.get("requirements")
    sequences = [a for a in ctx.artifacts.artifacts if a.kind == "sequence"]
    use_cases = [i.id for i in requirements.items if i.kind == "UC"] if requirements else []
    for use_case in use_cases:
        reason = ctx.na.get(normalise_name(use_case))
        if reason is not None:
            if not reason.strip():
                problems.append(f"{use_case} is listed under Not applicable but gives no reason")
            continue
        if not any(use_case in a.traces for a in sequences):
            problems.append(f"{use_case} has no sequence diagram and no recorded reason")
    allowed = {normalise_name(n) for n in ctx.sections.named_list("Actors")} | {"system"}
    for art in sequences:
        for participant in art.diagram.participants if art.diagram else []:
            if normalise_name(participant.label) not in allowed:
                message = f"{art.id} names '{participant.label}', which is not a declared actor or the System (FR-081)"
                ctx.note(Finding("artifact-wrong-level", art.id, message))
                problems.append(message)
    return [*problems, *_findings_for(ctx, "diagram")]


def _check_wireframes(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    reason = ctx.na.get("wireframes")
    group = _artifact_group(ctx)
    present = any(group.get(a.id) == "wireframe" for a in ctx.artifacts.artifacts)
    if reason is not None and not reason.strip():
        problems.append("'Wireframes' is listed under Not applicable but gives no reason")
    elif reason is None and not present:
        problems.append(
            "no wireframe and no reason under Not applicable ('Wireframes'): export each screen state, or record why there is none"
        )
    return [*problems, *_findings_for(ctx, "wireframe")]


def _check_comprehension(ctx: GateContext) -> list[str]:
    fingerprint = fingerprint_text(ctx.text)
    read = ctx.pkg.record_read(ctx.stage, "comprehension")
    if read.error:
        ctx.note(Finding("malformed-comprehension", ctx.doc.path, f"comprehension region: {read.error}"))
        return [f"malformed comprehension record: {read.error}"]
    if read.obj is not None:
        error = comprehension.validate_record(read.obj, ctx.stage)
        if error:
            ctx.note(Finding("malformed-comprehension", ctx.doc.path, error))
            return [f"malformed comprehension record: {error}"]
    state = comprehension.summarise(read.obj, fingerprint)["state"]
    if state == "complete":
        return []
    code, why = {
        "missing": (
            "comprehension-missing",
            "no comprehension check has been taken; run /speckit-eil-comprehend",
        ),
        "stale": (
            "comprehension-stale",
            "the check was taken on an earlier version of this document; take it again",
        ),
        "incomplete": ("comprehension-incomplete", "the check has fewer than five levels recorded"),
    }[state]
    ctx.note(Finding(code, ctx.doc.path, why))
    return [why]


# ---- technical checks


def _check_decisions(ctx: GateContext) -> list[str]:
    decisions = [i for i in ctx.parsed.items if i.kind == "DEC"]
    if not decisions:
        return (
            []
            if "technical decisions" in ctx.na
            else ["no DEC item under Technical Decisions (add **DEC-001**: ...)"]
        )
    problems: list[str] = []
    ids = {d.id for d in decisions}
    for decision in decisions:
        fields = decision_fields(decision)
        problems += [f"{decision.id} has no {name}" for name in DECISION_FIELDS if not fields.get(name)]
        owner = fields.get("owner", "")
        if is_ai_decided(owner):
            if not fields.get("reason", "").strip():
                message = f"{decision.id} is ai-decided but gives no Reason: an AI-decided decision must say why it changes nothing a user observes (D-53)"
                problems.append(message)
                ctx.note(Finding("ai-decided-without-reason", decision.id, message))
        elif owner and is_ai_actor(owner):
            problems.append(
                f"{decision.id} is owned by '{owner}'; the owner is the developer who decided, not the AI (FR-033)"
            )
        if not any(ref.startswith(("FR-", "NFR-")) for ref in decision.traces):
            problems.append(f"{decision.id} traces to no FR or NFR (FR-026)")
    problems += [f.message for f in ctx.findings if f.code == "dangling-trace" and f.where in ids]
    return problems


def _check_technical_questions(ctx: GateContext) -> list[str]:
    problems = open_question_problems(ctx.parsed.items)
    problems += [
        f"{item.id} is pending clarification; resolve it in the stage it belongs to"
        for item in ctx.parsed.items
        if "pending-clarification" in item.tags
    ]
    return problems


TECHNICAL_GROUPS = {
    "c4-container": "TEC-G15",
    "c4-component": "TEC-G16",
    "sequence": "TEC-G17",
    "er": "TEC-G18",
}
_SECTION_GROUP = {
    "container view": "TEC-G15",
    "component views": "TEC-G16",
    "sequence diagrams": "TEC-G17",
    "data model": "TEC-G18",
}
_LINE = re.compile(r":(\d+)$")


def _group_of(ctx: GateContext, art: Any) -> str:
    kind = art.depicts if art.kind == "image" else art.kind
    if kind in TECHNICAL_GROUPS:
        return TECHNICAL_GROUPS[kind]
    return _SECTION_GROUP.get(normalise_name(_section_at(ctx.sections, art.item.line)), "TEC-G15")


def _technical_findings(ctx: GateContext, criterion_id: str) -> list[str]:
    """The artifact findings that belong to one diagram criterion: by artifact id, else by the
    attachment the finding's line falls in, else by the section it sits in."""
    arts = ctx.artifacts.artifacts
    by_id = {a.id: a for a in arts}
    out: list[str] = []
    for finding in ctx.artifacts.findings:
        art = by_id.get(finding.where)
        if art is None:
            line = _LINE.search(finding.where)
            number = int(line[1]) if line else None
            if number is not None:
                before = [a for a in arts if a.attachment_line and a.attachment_line <= number]
                art = max(before, key=lambda a: a.attachment_line or 0) if before else None
                if art is None:
                    title = normalise_name(_section_at(ctx.sections, number))
                    group = _SECTION_GROUP.get(title, "TEC-G15")
                    if group == criterion_id:
                        out.append(f"{finding.code}: {finding.message}")
                    continue
        group = _group_of(ctx, art) if art is not None else "TEC-G15"
        if group == criterion_id:
            out.append(f"{finding.code}: {finding.message}")
    return out


def _of_kind(ctx: GateContext, kind: str) -> list[Any]:
    return [a for a in ctx.artifacts.artifacts if a.kind == kind]


def _readable(artifact: Any) -> bool:
    return artifact.diagram is not None and not artifact.diagram.findings


def _context_diagram(ctx: GateContext) -> Diagram | None:
    """The system context diagram of the requirements, if there is a readable one (rule a, level 1)."""
    requirements = ctx.upstream.get("requirements")
    if requirements is None:
        return None
    scan = scan_document(ctx.pkg.doc("requirements"), "requirements", requirements)
    return next((a.diagram for a in scan.artifacts if a.kind == "c4-context" and _readable(a)), None)


def _finding(ctx: GateContext, art_id: str, message: str) -> str:
    ctx.note(Finding("diagram-inconsistent", art_id, message))
    return message


def _check_container_diagram(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    containers = _of_kind(ctx, "c4-container")
    if not containers:
        problems.append("no c4-container diagram (the container view, FR-074)")
    context = _context_diagram(ctx)
    for art in containers:
        if context is not None and _readable(art):
            problems += [_finding(ctx, art.id, f"{art.id}: {m}") for m in zoom_problems(context, art.diagram)]
    return [*problems, *_technical_findings(ctx, "TEC-G15")]


def _readable_containers(ctx: GateContext) -> list[Diagram]:
    return [a.diagram for a in _of_kind(ctx, "c4-container") if _readable(a)]


def _check_component_diagrams(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    containers = _readable_containers(ctx)
    components = _of_kind(ctx, "c4-component")
    detailed: set[str] = set()
    for art in components:
        if _readable(art):
            detailed |= {
                normalise_name(b.label) for b in art.diagram.boundaries if b.macro == "Container_Boundary"
            }
            if containers:
                problems += [
                    _finding(ctx, art.id, f"{art.id}: {m}")
                    for m in component_problems(containers[0], art.diagram)
                ]
    changed = {
        normalise_name(e.label): e.label
        for diagram in containers
        for e in diagram.elements
        if e.role == "container" and not e.external and e.marker in ("new", "changed")
    }
    for key, label in changed.items():
        reason = ctx.na.get(key)
        if reason is not None:
            if not reason.strip():
                problems.append(f"'{label}' is listed under Not applicable but gives no reason")
        elif key not in detailed:
            problems.append(f"{e_kind(label)} has no component diagram and no recorded reason")
    return [*problems, *_technical_findings(ctx, "TEC-G16")]


def e_kind(label: str) -> str:
    return f"the {label} container"


def _upstream_closure(ctx: GateContext, ids: list[str]) -> set[str]:
    """``ids`` and everything they trace to, through the documents of every stage."""
    traces: dict[str, list[str]] = {}
    for parsed in [*ctx.upstream.values(), ctx.parsed]:
        for item in parsed.items:
            traces[item.id] = item.traces
    seen: set[str] = set()
    todo = list(ids)
    while todo:
        current = todo.pop()
        if current not in seen:
            seen.add(current)
            todo.extend(traces.get(current, []))
    return seen


def _check_technical_sequences(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    sequences = _of_kind(ctx, "sequence")
    requirements = ctx.upstream.get("requirements")
    use_cases = [i.id for i in requirements.items if i.kind == "UC"] if requirements else []
    reached = {art.id: _upstream_closure(ctx, art.traces) for art in sequences}
    for use_case in use_cases:
        reason = ctx.na.get(normalise_name(use_case))
        if reason is not None:
            if not reason.strip():
                problems.append(f"{use_case} is listed under Not applicable but gives no reason")
            continue
        if not any(use_case in closure for closure in reached.values()):
            problems.append(f"{use_case} has no technical sequence diagram and no recorded reason")
    containers = _readable_containers(ctx)
    known = element_names(*containers, *[a.diagram for a in _of_kind(ctx, "c4-component") if _readable(a)])
    for art in sequences:
        if not any(ref.startswith("DEC-") for ref in art.traces):
            problems.append(f"{art.id} cites no decision (add a DEC to its traces)")
        if _readable(art) and containers:
            problems += [
                _finding(ctx, art.id, f"{art.id}: {m}") for m in sequence_problems(art.diagram, known)
            ]
    return [*problems, *_technical_findings(ctx, "TEC-G17")]


def _check_er_diagrams(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    diagrams = _of_kind(ctx, "er")
    reason = ctx.na.get("data model")
    if reason is not None:
        if not reason.strip():
            problems.append("'Data Model' is listed under Not applicable but gives no reason")
    elif not diagrams:
        problems.append(
            "no er diagram and no reason under Not applicable ('Data Model'): draw the data, or record why none changes"
        )
    containers = _readable_containers(ctx)
    for art in diagrams:
        if containers:
            problems += [
                _finding(ctx, art.id, f"{art.id}: {m}") for m in store_problems(art.store, containers[0])
            ]
    return [*problems, *_technical_findings(ctx, "TEC-G18")]


# ---- AI Specification checks (FR-027, FR-039, FR-067, FR-082)

SOURCE_KINDS = ("REQ", "UC", "FR", "NFR", "DEC", "ART")
APPROVED_SOURCE_STAGES = ("requirements", "functional", "technical")
PENDING = "pending-clarification"


def _stage_of_ids(ctx: GateContext) -> dict[str, str]:
    """Every id defined in an earlier document, whatever that document's state."""
    return {item.id: stage for stage, parsed in ctx.upstream.items() for item in parsed.items}


def _approved_ids(ctx: GateContext) -> set[str]:
    """Definition items an approval covers and no change upstream of them reaches (item level, D-35)."""
    from .blockstatus import approved_ids

    defined = {
        item.id for stage in APPROVED_SOURCE_STAGES if (parsed := ctx.upstream.get(stage)) for item in parsed.items
    }
    return approved_ids(ctx.pkg) & defined


def _unsourced_text(ctx: GateContext) -> list[tuple[int, str]]:
    """Lines of the content sections that sit outside any item: text with no source (FR-039)."""
    wanted = {normalise_name(h) for h in AI_SPEC_HEADINGS}
    inside = False
    in_item = False
    found: list[tuple[int, str]] = []
    for line in ctx.doc.lines:
        if line.kind != "text":
            continue
        text = line.live
        head = _HEADING.match(text)
        if head:
            level_two = head["hashes"] == "##"
            if level_two:
                inside = normalise_name(head["title"].strip().rstrip(":")) in wanted
            in_item = False
            continue
        if not inside:
            continue
        if not text.strip():
            in_item = False
        elif _ITEM_PREFIX.match(text):
            in_item = True
        elif not in_item:
            found.append((line.no, text.strip()))
            in_item = True  # report the first line of a paragraph once
    return found


def _check_ai_sources(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    approved = _approved_ids(ctx)
    defined = _stage_of_ids(ctx)
    own = {item.id for item in ctx.parsed.items}

    def fail(where: str, message: str) -> None:
        ctx.note(Finding("ai-spec-not-traceable", where, message))
        problems.append(message)

    for item in ctx.parsed.items:
        if item.kind != "AIS" or PENDING in item.tags:
            continue
        if not item.traces:
            fail(item.id, f"{item.id} traces to no approved source")
        for ref in item.traces:
            kind = ref.split("-")[0]
            if ref in approved:
                if kind not in SOURCE_KINDS:
                    fail(
                        item.id,
                        f"{item.id} traces to {ref}, which is not a requirement, decision or artefact",
                    )
            elif ref in defined:
                state = ctx.pkg.state(defined[ref]).state
                fail(
                    item.id,
                    f"{item.id} traces to {ref}, defined in {defined[ref]}, which is {state}, not approved",
                )
            elif ref in own:
                fail(item.id, f"{item.id} traces to {ref}, an item of this document, not an approved source")
            else:
                fail(item.id, f"{item.id} traces to {ref}, which nothing defines")
    for number, text in _unsourced_text(ctx):
        fail(f"line:{number}", f"line {number} has text with no AIS item and so no source: {text[:60]!r}")
    return problems


def _check_ai_pending(ctx: GateContext) -> list[str]:
    problems = []
    for item in ctx.parsed.items:
        if PENDING in item.tags:
            message = (
                f"{item.id} is a pending clarification answer; carry it to the earliest stage it affects "
                "(/speckit-eil-resolve)"
            )
            ctx.note(Finding(PENDING, item.id, message))
            problems.append(message)
    return problems


def _stage_hashes(ctx: GateContext, stage: str) -> dict[str, str]:
    """Current item hashes of an earlier stage's document, artefact attachments included."""
    key = ("hashes", stage)
    if key not in ctx.cache:
        parsed = ctx.upstream[stage]
        scan_document(ctx.pkg.doc(stage), stage, parsed)
        ctx.cache[key] = {item.id: item_hash(item) for item in parsed.items}
    return ctx.cache[key]


def _check_ai_artifacts(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    defined = _stage_of_ids(ctx)
    for item in ctx.parsed.items:
        if item.kind != "AIS":
            continue
        for ref in item.traces:
            stage = defined.get(ref) if ref.startswith("ART-") else None
            approval = ctx.pkg.state(stage).approval if stage else None
            if stage is None or not approval or not isinstance(approval.get("items"), dict):
                continue
            recorded = approval["items"].get(ref)
            if recorded is None:
                message = f"{ref} was not part of the approval of {stage}"
            elif _stage_hashes(ctx, stage).get(ref) != recorded:
                message = f"{ref} changed since {stage} was approved"
            else:
                continue
            ctx.note(Finding("artifact-changed-since-approval", item.id, f"{item.id}: {message}"))
            problems.append(message)
    return problems


def _check_no_ai_diagrams(ctx: GateContext) -> list[str]:
    return [f"{f.code}: {f.message}" for f in ctx.artifacts.findings]


# ---- plan and tasks checks (FR-057, FR-058, FR-083)

# The plan's headings that derive from nothing: every administrative heading the helper writes or reads
# (``trace.ADMINISTRATIVE_SECTIONS``, so the two cannot drift apart) and the plan's own non-derived ones.
_PLAN_EXEMPT = frozenset(
    normalise_name(n) for n in (*ADMINISTRATIVE_SECTIONS, "Not applicable")
)
_TRACES_IN_TITLE = re.compile(r"\(traces:\s*(?P<ids>[^)]*)\)")


def _approved_technical_decisions(ctx: GateContext) -> set[str]:
    technical = ctx.upstream.get("technical")
    if technical is None or ctx.pkg.state("technical").state != "approved":
        return set()
    return {item.id for item in technical.items if item.kind == "DEC"}


def _check_plan_derivation(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    decisions = _approved_technical_decisions(ctx)

    def fail(where: str, message: str) -> None:
        ctx.note(Finding("plan-not-derivable", where, message))
        problems.append(message)

    sections = [
        s
        for s in ctx.sections.sections
        if s.level == 2 and normalise_name(_TRACES_IN_TITLE.sub("", s.title)) not in _PLAN_EXEMPT
    ]
    if not sections:
        return ["the plan has no sections"]
    for section in sections:
        clause = _TRACES_IN_TITLE.search(section.title)
        name = _TRACES_IN_TITLE.sub("", section.title).strip()
        where = f"line:{section.line}"
        refs = [r.strip() for r in clause["ids"].split(",") if r.strip()] if clause else []
        if not refs:
            fail(where, f"section '{name}' names no approved decision it derives from (traces: DEC-###)")
            continue
        for ref in refs:
            if ref not in decisions:
                fail(
                    where,
                    f"section '{name}' traces to {ref}, which is not a decision of the approved Technical Specification",
                )
    return problems


def _ai_spec_ids(ctx: GateContext) -> set[str]:
    parsed = ctx.upstream.get("ai-spec")
    return {i.id for i in parsed.items if i.kind == "AIS"} if parsed else set()


def _check_task_traces(ctx: GateContext) -> list[str]:
    tasks = ctx.parsed.tasks
    if not tasks:
        return ["the task list has no tasks"]
    problems: list[str] = []
    sources = _ai_spec_ids(ctx) | _approved_technical_decisions(ctx)
    for task in tasks:
        if not task.traces:
            message = f"{task.id} traces to no AIS item or approved decision (traces: AIS-###)"
        else:
            bad = [ref for ref in task.traces if ref not in sources and not ref.startswith("ART-")]
            if not bad:
                continue
            message = f"{task.id} traces to {', '.join(bad)}, which is neither an AI Specification item nor an approved decision"
        ctx.note(Finding("task-untraced", task.id, message))
        problems.append(message)
    return problems


IN_SCOPE_ARTIFACTS = {"wireframe": "functional", "er": "technical", "sequence": "technical"}


def _in_scope_artifacts(ctx: GateContext) -> dict[str, tuple[str, str]]:
    """Artefacts the AI Specification tells the agent to read that need building work: ``id -> (kind, stage)``."""
    scope = _ai_spec_ids_to_arts(ctx)
    found: dict[str, tuple[str, str]] = {}
    for stage in ("functional", "technical"):
        parsed = ctx.upstream.get(stage)
        if parsed is None:
            continue
        for art in scan_document(ctx.pkg.doc(stage), stage, parsed).artifacts:
            kind = art.depicts if art.kind == "image" else art.kind
            if art.id in scope and IN_SCOPE_ARTIFACTS.get(kind or "") == stage:
                found[art.id] = (kind or "", stage)
    return found


def _ai_spec_ids_to_arts(ctx: GateContext) -> set[str]:
    parsed = ctx.upstream.get("ai-spec")
    return {
        ref
        for i in (parsed.items if parsed else [])
        if i.kind == "AIS"
        for ref in i.traces
        if ref.startswith("ART-")
    }


def _check_artifact_coverage(ctx: GateContext) -> list[str]:
    parsed = ctx.upstream.get("ai-spec")
    via: dict[str, set[str]] = {}
    for item in parsed.items if parsed else []:
        if item.kind == "AIS":
            for ref in item.traces:
                if ref.startswith("ART-"):
                    via.setdefault(ref, set()).add(item.id)
    cited = {ref for task in ctx.parsed.tasks for ref in task.traces}
    problems = []
    for art_id, (kind, stage) in sorted(_in_scope_artifacts(ctx).items()):
        if art_id in cited or via.get(art_id, set()) & cited:
            continue
        message = (
            f"{art_id} ({kind}, {stage}) is in scope but no task traces to it or to an AIS item that cites it"
        )
        ctx.note(Finding("artifact-uncovered", art_id, message))
        problems.append(message)
    return problems


# ---- verification and completion checks (FR-059 to FR-065, FR-084)

_DECLARES_COMPLETE = re.compile(
    r"\b(story|feature|work|implementation|project)\s+(is|are|was|has\s+been)\s+(now\s+)?"
    r"(complete|completed|done|finished)\b",
    re.IGNORECASE,
)


def _check_verification_rows(ctx: GateContext) -> list[str]:
    covered = {ref for row in _rows(ctx) for ref in row.traces}
    targets = [
        *verification.requirement_ids(ctx.pkg),
        *verification.functional_ids(ctx.pkg),
        *verification.approved_artifact_ids(ctx.pkg),
    ]
    return [f"{t} has no verification row" for t in targets if t not in covered]


def _rows(ctx: GateContext) -> list[Any]:
    return [i for i in ctx.parsed.items if i.kind == "EVD"]


def _check_row_shape(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    for row in _rows(ctx):
        if row.status not in verification.STATUSES:
            problems.append(f"{row.id} has no status (status: verified|failed|unverified|excepted)")
            continue
        if row.status in ("verified", "failed"):
            fields = evidence_fields(row)
            kind = fields.get("kind", "").lower()
            if not kind:
                problems.append(f"{row.id} has no kind (automated or manual)")
            elif kind not in verification.KINDS:
                problems.append(f"{row.id} has kind {kind!r}; use automated or manual")
            if not fields.get("evidence"):
                problems.append(f"{row.id} has no evidence")
    return problems


def _check_exceptions(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    for row in _rows(ctx):
        if row.status == "excepted":
            problems += verification.exception_problems(row)
    return problems


def _check_open_tasks(ctx: GateContext) -> list[str]:
    tasks = ctx.upstream.get("tasks")
    section = ctx.sections.find("Open Tasks")
    listed = "\n".join(section.content) if section else ""
    return [
        f"{t.id} is open but not listed under Open Tasks"
        for t in (tasks.tasks if tasks else [])
        if not t.done and not re.search(rf"\b{re.escape(t.id)}\b", listed)
    ]


def _check_no_completion_claim(ctx: GateContext) -> list[str]:
    problems: list[str] = []
    for line in ctx.doc.lines:
        if line.kind != "text":
            continue
        heading = _HEADING.match(line.live)
        if heading and normalise_name(heading["title"]) in ("completion", "story complete", "completed"):
            problems.append(f"line {line.no}: a Completion heading declares completion")
        elif _DECLARES_COMPLETE.search(line.live):
            problems.append(
                f"line {line.no}: the document declares completion; only the completion stage does"
            )
    if ctx.pkg.record(ctx.stage, "approval"):
        problems.append("the document carries an approval; verification is never approved")
    return problems


def _check_verification_exists(ctx: GateContext) -> list[str]:
    if ctx.pkg.exists("verification"):
        return []
    ctx.note(Finding("dangling-trace", "s07", "there is no verification document"))
    return ["there is no verification document (s07-verification.md), which completion needs (FR-064)"]


def _status_problems(ctx: GateContext, targets: list[str]) -> list[str]:
    if not ctx.pkg.exists("verification"):
        return []
    found = verification.statuses(ctx.pkg)
    return [
        f"{t} is {found[t]}" for t in targets if found.get(t, "unverified") not in ("verified", "excepted")
    ]


def _check_requirements_verified(ctx: GateContext) -> list[str]:
    return _status_problems(ctx, verification.requirement_ids(ctx.pkg))


def _check_artifacts_verified(ctx: GateContext) -> list[str]:
    return _status_problems(ctx, verification.approved_artifact_ids(ctx.pkg))


_UNTOUCHED_LINE = re.compile(r"^\s*(?:[-*]\s+)?untouched\s*:\s*(?P<ids>.*)$", re.IGNORECASE)
_CURRENCY_LINE = re.compile(r"(?P<id>ART-\d{3})\s*:\s*(?P<rest>.*)$")
_ACCEPTED_BY = re.compile(r"accepted by\s+(?P<who>[^,;.]+)", re.IGNORECASE)
_BECAUSE = re.compile(r"\b(because|reason|why)\b\s*:?\s*\S", re.IGNORECASE)


def _check_diagram_currency(ctx: GateContext) -> list[str]:
    section = ctx.sections.find("Diagram Currency")
    lines: dict[str, str] = {}
    for text in section.content if section else []:
        found = _CURRENCY_LINE.search(text)
        if found:
            lines.setdefault(found["id"], found["rest"].strip())
    deviations = ctx.sections.find("Accepted Deviations")
    listed = "\n".join(deviations.content) if deviations else ""
    untouched = {
        i
        for text in (section.content if section else [])
        if (m := _UNTOUCHED_LINE.search(text))
        for i in re.findall(r"ART-\d{3}", m["ids"])
    }
    touched = staleness.touched_artifacts(ctx.pkg)
    problems: list[str] = []
    for art in verification.approved_artifact_ids(ctx.pkg):
        rest = lines.get(art)
        if art in untouched and art in touched:
            problems.append(f"{art} is listed untouched but implementation touched it ({touched[art]})")
        elif rest is None and art in untouched:
            continue
        elif rest is None:
            problems.append(f"{art} has no line under Diagram Currency")
        elif rest.lower().startswith("current"):
            continue
        elif rest.lower().startswith("deviation"):
            who = _ACCEPTED_BY.search(rest)
            if not who:
                problems.append(f"{art} is a deviation but names no 'accepted by'")
            elif is_ai_actor(who["who"]):
                problems.append(f"{art} is a deviation accepted by {who['who'].strip()!r}, who is the AI")
            if not _BECAUSE.search(rest):
                problems.append(f"{art} is a deviation but gives no reason")
            if art not in listed:
                problems.append(f"{art} is not listed under Accepted Deviations")
        else:
            problems.append(f"{art} is neither 'current' nor a 'deviation'")
    return problems


CHECKS.update(
    {
        "VER-G02": _check_verification_rows,
        "VER-G03": _check_row_shape,
        "VER-G04": _check_exceptions,
        "VER-G05": _check_open_tasks,
        "VER-G06": _check_no_completion_claim,
        "CMP-G02": _check_verification_exists,
        "CMP-G03": _check_requirements_verified,
        "CMP-G04": _check_artifacts_verified,
        "CMP-G05": _check_diagram_currency,
    }
)

def _unanswered(ctx: GateContext, stage: str, kind: str, noun: str) -> list[str]:
    from . import reviews

    if not ctx.pkg.exists(stage):
        return []
    entries = reviews.build_list(ctx.pkg, stage, kind).entries
    return [f"{e.key}: {e.why}" for e in entries] and [
        f"{len(entries)} {noun}(s) not yet confirmed: " + "; ".join(f"{e.key} ({e.why})" for e in entries[:5])
    ]


def _check_tasks_current(ctx: GateContext) -> list[str]:
    return _unanswered(ctx, "tasks", "tasks", "ticked task")


def _check_evidence_current(ctx: GateContext) -> list[str]:
    return _unanswered(ctx, "verification", "evidence", "evidence row")


def _check_findings_ver(ctx: GateContext) -> list[str]:
    return [
        p
        for item in verification.review_findings(ctx.pkg)
        for p in verification.finding_problems(item, needs_correction=True, pkg=ctx.pkg)
        if item.status != "resolved" or "no correction" in p
    ]


def _check_findings_cmp(ctx: GateContext) -> list[str]:
    return [p for item in verification.review_findings(ctx.pkg) for p in verification.finding_problems(item)]


CHECKS.update(
    {
        "CMP-G06": _check_tasks_current,
        "CMP-G07": _check_evidence_current,
        "CMP-G08": _check_findings_cmp,
        "VER-G07": _check_findings_ver,
    }
)

CHECKS.update(
    {
        "PLN-G01": _check_plan_derivation,
        "TSK-G01": _check_task_traces,
        "TSK-G02": _check_artifact_coverage,
    }
)

CHECKS.update(
    {
        "AIS-G02": _check_ai_sources,
        "AIS-G03": _check_ai_pending,
        "AIS-G04": _check_ai_artifacts,
        "AIS-G05": _check_no_ai_diagrams,
    }
)

CHECKS.update(
    {
        "TEC-G02": _check_decisions,
        "TEC-G12": _check_technical_questions,
        "TEC-G15": _check_container_diagram,
        "TEC-G16": _check_component_diagrams,
        "TEC-G17": _check_technical_sequences,
        "TEC-G18": _check_er_diagrams,
        "TEC-G19": _check_comprehension,
    }
)

CHECKS.update(
    {
        "FUN-G01": _check_functional_traceability,
        "FUN-G02": _check_use_cases_described,
        "FUN-G09": _check_nfr_items,
        "FUN-G11": _check_functional_ambiguities,
        "FUN-G14": _check_sequence_diagrams,
        "FUN-G15": _check_wireframes,
        "FUN-G16": _check_comprehension,
    }
)

# ---- results


@dataclass
class CriterionResult:
    id: str
    text: str
    kind: str
    status: str  # met | not-met | overridden
    reason: str = ""
    basis: str = ""  # judgment only: the fingerprint of what the verdict was made against (D-29)

    def to_json(self, with_text: bool = True) -> dict[str, str]:
        out: dict[str, str] = {"id": self.id, "kind": self.kind, "status": self.status, "reason": self.reason}
        if self.basis:
            out["basis"] = self.basis
        if with_text:
            out["text"] = self.text
        return out


@dataclass
class GateResult:
    stage: str
    fingerprint: str
    criteria: list[CriterionResult]
    findings: list[Finding]
    assessment: dict[str, list[str]]

    @property
    def ok(self) -> bool:
        return all(c.status in ("met", "overridden") for c in self.criteria)

    def unmet(self) -> list[CriterionResult]:
        return [c for c in self.criteria if c.status == "not-met"]

    def ordered_criteria(self) -> list[CriterionResult]:
        """Unmet first, then judgment criteria, then the rest, each group in the gate's own order (FR-028)."""
        return sorted(self.criteria, key=lambda c: 0 if c.status == "not-met" else 1 if c.kind == "judgment" else 2)

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.criteria),
            "unmet": len(self.unmet()),
            "met_structural": sum(1 for c in self.criteria if c.status == "met" and c.kind != "judgment"),
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stage": self.stage,
            "fingerprint": self.fingerprint,
            "summary": self.summary(),
            "criteria": [c.to_json() for c in self.ordered_criteria()],
            "assessment": self.assessment,
            "findings": [f.to_json() for f in self.findings],
        }


# ---- judgments


class JudgmentsError(ValueError):
    """The ``--judgments`` file is not acceptable (exit 2, nothing written)."""


@dataclass
class Judgments:
    verdicts: dict[str, tuple[str, str]]  # id -> (status, reason)
    assessment: dict[str, list[str]]
    bases: dict[str, str] = field(default_factory=dict)  # id -> basis; absent id means "trust it"


def load_judgments(path: Path, stage: str) -> Judgments:
    try:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise JudgmentsError(f"cannot read {path}: {exc.strerror or exc}") from exc
    except ValueError as exc:
        raise JudgmentsError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise JudgmentsError("the judgments file must be a JSON object")
    unknown = set(body) - {"stage", "judgments", "assessment"}
    if unknown:
        raise JudgmentsError(f"unknown key(s) in the judgments file: {sorted(unknown)}")
    if body.get("stage") != stage:
        raise JudgmentsError(f"the judgments file is for stage {body.get('stage')!r}, not {stage!r}")
    entries = body.get("judgments")
    if not isinstance(entries, list):
        raise JudgmentsError("'judgments' must be a list")
    judged = {c.id for c in criteria_for(stage) if c.kind == JUDGMENT}
    known = {c.id for c in criteria_for(stage)}
    verdicts: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "status", "reason"}:
            raise JudgmentsError("each judgment needs exactly id, status and reason")
        criterion_id = entry["id"]
        if criterion_id not in known:
            raise JudgmentsError(f"{criterion_id!r} is not a criterion of stage {stage}")
        if criterion_id not in judged:
            raise JudgmentsError(f"{criterion_id} is not a judgment criterion; only code can meet it")
        if entry["status"] not in ("met", "not-met"):
            raise JudgmentsError(
                f"{criterion_id}: status must be 'met' or 'not-met', not {entry['status']!r}"
            )
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise JudgmentsError(f"{criterion_id}: a reason is required")
        if criterion_id in verdicts:
            raise JudgmentsError(f"{criterion_id} appears more than once")
        verdicts[criterion_id] = (entry["status"], entry["reason"].strip())
    lists = body.get("assessment", {})
    if not isinstance(lists, dict) or set(lists) - set(ASSESSMENT_LISTS):
        raise JudgmentsError(f"'assessment' may only hold the lists {list(ASSESSMENT_LISTS)}")
    assessment: dict[str, list[str]] = {}
    for name, values in lists.items():
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise JudgmentsError(f"assessment.{name} must be a list of strings")
        assessment[name] = values
    return Judgments(verdicts, assessment)


def _prior_judgments(region: dict[str, Any] | None, fingerprint: str, same_text: tuple[str, ...] = ()) -> Judgments:
    """The AI's earlier verdicts. Each judgment verdict is kept on its own criterion-scoped basis
    (D-29), independent of what else in the document changed; the five free-text assessment lists
    are carried forward only while the whole document is unchanged, since they can reference
    content anywhere in it.

    A verdict recorded before D-29 has no basis. It is current while the record's fingerprint is the
    document's, under the current rule or an earlier one (``same_text``, 003 D-56); otherwise it cannot
    be compared and is judged again."""
    empty = Judgments({}, {})
    if not region:
        return empty
    current = region.get("fingerprint") in (fingerprint, *same_text)
    verdicts: dict[str, tuple[str, str]] = {}
    bases: dict[str, str] = {}
    for entry in region.get("criteria", []):
        reason = str(entry.get("reason", ""))
        if (
            entry.get("kind") == JUDGMENT
            and reason.startswith(AI_PREFIX)
            and entry.get("status") in ("met", "not-met")
        ):
            verdicts[entry["id"]] = (entry["status"], reason[len(AI_PREFIX) :])
            if "basis" in entry or not current:
                bases[entry["id"]] = str(entry.get("basis", ""))
    lists = region.get("assessment", {}) if current else {}
    kept = {
        name: [v for v in lists.get(name, []) if not v.startswith(STRUCTURE_TAG)]
        for name in ASSESSMENT_LISTS
        if isinstance(lists.get(name), list)
    }
    return Judgments(verdicts, kept, bases)


# ---- evaluation


def ai_draft_lines(text: str) -> list[int]:
    """Lines (1-based) carrying an ``[ai-draft]`` tag in live text (not in comments or fences)."""
    return [line.no for line in Doc(text).lines if line.kind == "text" and "[ai-draft]" in line.live]


def _overrides(doc: Doc, stage: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for record in doc.records():
        if record.kind == "override" and record.obj and record.obj.get("stage") == stage:
            found.setdefault(str(record.obj.get("criterion", "")), record.obj)
    return found


def build_context(pkg: Package, stage: str, text: str, doc: Doc | None = None) -> GateContext:
    from .provenance import decided_findings  # deferred: provenance imports this module

    doc = doc or Doc(text, path=DOC_FILES[stage])
    parsed = parse_document(doc)
    scan = scan_document(doc, stage, parsed, root=pkg.root)
    sections = Sections(doc)
    ctx = GateContext(
        pkg, stage, doc, text, parsed, scan, sections, sections.not_applicable(), _overrides(doc, stage)
    )
    for earlier in pkg.existing_stages():
        if STAGES.index(earlier) < STAGES.index(stage):
            try:
                ctx.upstream[earlier] = parse_document(pkg.doc(earlier))
            except UnicodeDecodeError:
                continue
    for finding in [*doc.findings, *parsed.findings, *_story_findings_for(pkg, stage, parsed)]:
        ctx.note(finding)
    for finding in [*scan.findings, *orphan_findings(pkg), *decided_findings(pkg, stage, parsed)]:
        ctx.note(finding)
    return ctx


def _story_findings_for(pkg: Package, stage: str, own: ParseResult) -> list[Finding]:
    """``duplicate-id`` and ``dangling-trace`` that concern this stage's own items and tasks."""
    parsed: dict[str, ParseResult] = {}
    for other in pkg.existing_stages():
        if other != stage:
            try:
                parsed[other] = parse_document(pkg.doc(other))
            except UnicodeDecodeError:
                continue
    parsed[stage] = own
    mine = {i.id for i in own.items} | {t.id for t in own.tasks}
    seen: set[tuple[str, str]] = set()
    kept: list[Finding] = []
    for finding in story_findings(parsed):
        if finding.where in mine and (finding.code, finding.where) not in seen:
            seen.add((finding.code, finding.where))
            kept.append(finding)
    return kept


def _section_fingerprints_cached(ctx: GateContext) -> dict[str, str]:
    key = ("section_fingerprints",)
    if key not in ctx.cache:
        ctx.cache[key] = section_fingerprints(ctx.doc, ctx.parsed.items)
    return ctx.cache[key]


def _criterion_basis(ctx: GateContext, criterion: Criterion) -> str:
    """What a judgment verdict for this criterion is checked against: the content of just the
    sections it reads (``Criterion.headings``), so an edit elsewhere in the document does not void
    it (D-29). A criterion with no named sections judges the whole document, so it falls back to
    the whole-document fingerprint, unchanged from before this decision."""
    if not criterion.headings:
        return fingerprint_text(ctx.text)
    sections = _section_fingerprints_cached(ctx)
    parts = [f"{name}\x00{sections.get(name, '<absent>')}" for name in criterion.headings]
    return fingerprint_text("\n".join(parts))


def evaluate(ctx: GateContext, judgments: Judgments) -> list[CriterionResult]:
    results: list[CriterionResult] = []
    for criterion in criteria_for(ctx.stage):
        problems = heading_problems(ctx, criterion.headings) if criterion.headings else []
        ctx.structure_missing.extend(problems)
        basis = ""
        if criterion.kind == JUDGMENT:
            basis = _criterion_basis(ctx, criterion)
            fresh = criterion.id not in judgments.bases or judgments.bases[criterion.id] == basis
            if problems:
                status, reason = "not-met", "; ".join(problems)
            elif criterion.id in judgments.verdicts and fresh:
                status, reason = judgments.verdicts[criterion.id]
                reason = AI_PREFIX + reason
            else:
                status, reason = "not-met", "no judgment supplied"
        else:
            if not problems and criterion.id in CHECKS:
                problems = CHECKS[criterion.id](ctx)
            status, reason = ("not-met", "; ".join(problems)) if problems else ("met", "")
        if status == "not-met" and criterion.id == PROFILE_CRITERION:
            from .profile import active as profile_active
            from .profile import label as profile_label

            if (in_force := profile_active(ctx.pkg)) is not None:
                status, reason = "met", profile_label(in_force)  # met by the recorded authorisation (FR-021)
        if status == "not-met" and criterion.id in ctx.overrides:
            record = ctx.overrides[criterion.id]
            status = "overridden"
            reason = f"overridden by {record.get('by', '?')}: {record.get('reason', '')} ({record.get('id', 'OVR')})"
        results.append(CriterionResult(criterion.id, criterion.text, criterion.kind, status, reason, basis))
    return results


def _record(result: GateResult, evaluated_at: str) -> dict[str, Any]:
    return {
        "stage": result.stage,
        "evaluated_at": evaluated_at,
        "fingerprint": result.fingerprint,
        "criteria": [c.to_json(with_text=False) for c in result.criteria],
        "assessment": result.assessment,
        "findings": [f.to_json() for f in result.findings],
    }


def check_stage(
    pkg: Package, stage: str, judgments_path: Path | None = None, write: bool = True
) -> GateResult:
    """Evaluate a stage's gate and, unless ``write`` is false, record it in the assessment region.

    Raises ``JudgmentsError`` before anything is read or written if the judgments file is unacceptable.
    """
    criteria_for(stage)  # an unknown stage fails here
    supplied = load_judgments(judgments_path, stage) if judgments_path is not None else None
    original = pkg.read(stage)
    text = original
    doc = pkg.doc(stage)
    if "assessment" not in doc.regions:
        text = ensure_region(text, "assessment")
        doc = Doc(text, path=DOC_FILES[stage])
        fingerprint = fingerprint_text(text)
    else:
        fingerprint = pkg.fingerprint(stage) or fingerprint_text(text)
    prior = pkg.record(stage, "assessment")
    judgments = supplied if supplied is not None else _prior_judgments(prior, fingerprint, (fingerprint_text_001(text),))

    ctx = build_context(pkg, stage, text, doc)
    criteria = evaluate(ctx, judgments)
    lists = {name: list(judgments.assessment.get(name, [])) for name in ASSESSMENT_LISTS}
    lists["missing"] = [STRUCTURE_TAG + p for p in dict.fromkeys(ctx.structure_missing)] + lists["missing"]
    result = GateResult(stage, fingerprint, criteria, ctx.findings, lists)

    if write:
        stamp = utc_now()
        if prior and {k: v for k, v in prior.items() if k != "evaluated_at"} == {
            k: v for k, v in _record(result, stamp).items() if k != "evaluated_at"
        }:
            stamp = str(prior.get("evaluated_at", stamp))  # unchanged assessment keeps its timestamp
        try:
            pkg.write_record(stage, "assessment", _record(result, stamp), text=text)
        except RegionError:
            pass  # a malformed record file is reported by status and never written over (FR-011)
    return result

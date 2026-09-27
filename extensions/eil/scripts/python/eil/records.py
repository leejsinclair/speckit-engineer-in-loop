"""Approvals and overrides: the records that close a stage (task T040; FR-010 to FR-013, FR-045,
FR-066).

Every refusal here is decided by code and writes nothing. An approval is recorded only with a named,
configured person and their own words (Principle II: this makes a forged approval visible, it does
not make one impossible).
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from . import comprehension, impact
from .artifacts import scan_document
from .blocks import Doc, append_record, replace_record, write_region
from .clock import utc_now
from .fingerprint import fingerprint_text
from .gates import (
    EXTRA_OVERRIDABLE,
    INTEGRITY_CODES,
    Criterion,
    Sections,
    ai_draft_lines,
    build_context,
    check_stage,
    criteria_for,
    open_question_problems,
    overridable_ids,
)
from .identity import (
    Config,
    confirmer_refusal,
    git_identity,
    is_ai_actor,
    resolve_approvers,
    same_person,
    story_identities,
)
from .package import APPROVABLE, DOC_FILES, STAGES, Package
from .results import Refusal, refuse, usage_error
from .trace import item_hash, non_item_fingerprint, parse_document

DEFINITION_STAGES = ("requirements", "functional", "technical", "ai-spec")
# Completion has its own refusal codes (FR-064, FR-065); each is the reason for one criterion.
COMPLETION_REFUSALS = {
    "CMP-G02": ("verification-missing", "Record the evidence first: /speckit-eil-verify"),
    "CMP-G03": (
        "unverified-requirement",
        "Verify the requirement, or record an exception naming who accepted it and why; or record a named override of CMP-G03",
    ),
    "CMP-G04": (
        "unverified-artifact",
        "Verify the artefact, or record an exception naming who accepted it and why; or record a named override of CMP-G04",
    ),
}
_OVERRIDE_ID = re.compile(r"OVR-(\d{3,})")


def developer_identities(pkg: Package, config: Config) -> list[str]:
    from .overview import read_story

    _, owner = read_story(pkg)
    git_name, git_email = git_identity(pkg.project_root or pkg.root)
    return story_identities(config, owner, git_name, git_email)


def approvers_for(pkg: Package, config: Config, stage: str) -> list[str]:
    return resolve_approvers(config, stage, developer_identities(pkg, config))


def _require_stage_with_document(pkg: Package, stage: str) -> None:
    if stage not in STAGES:
        raise refuse(
            Refusal("unknown-stage", f"{stage!r} is not a stage", f"Use one of: {', '.join(STAGES)}")
        )
    if not pkg.exists(stage):
        raise refuse(
            Refusal(
                "unknown-stage",
                f"{stage} has no document yet ({DOC_FILES[stage]})",
                f"Start the stage first: eil stage-init {stage}",
            )
        )


def next_override_id(pkg: Package) -> str:
    highest = 0
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        for record in doc.records():
            if record.kind == "override" and record.obj:
                match = _OVERRIDE_ID.fullmatch(str(record.obj.get("id", "")))
                highest = max(highest, int(match[1]) if match else 0)
    return f"OVR-{highest + 1:03d}"


def prior_stage_refusals(pkg: Package, stage: str) -> list[Refusal]:
    refusals = []
    for earlier in APPROVABLE:
        if STAGES.index(earlier) >= STAGES.index(stage):
            break
        state = pkg.state(earlier).state
        if state != "approved":
            refusals.append(
                Refusal(
                    "stage-not-approved",
                    f"{earlier} must be approved before {stage} (it is {state})",
                    f"Approve {earlier} first",
                )
            )
    return refusals


def _gate_refusals(pkg: Package, stage: str, ctx: Any, text: str) -> list[Refusal]:
    ctx_overrides = ctx.overrides
    refusals: list[Refusal] = []
    try:
        result = check_stage(pkg, stage, write=False)
    except NotImplementedError:
        return [
            Refusal(
                "unmet-criteria",
                f"no quality gate is defined for {stage} in this version",
                "Nothing can approve it yet",
            )
        ]
    integrity = [f for f in result.findings if f.code in INTEGRITY_CODES]
    unmet: list[Criterion | Any] = []
    for criterion in result.unmet():
        questions = open_question_problems(ctx.parsed.items) if criterion.id == "REQ-G10" else []
        if criterion.id in COMPLETION_REFUSALS:
            code, fix = COMPLETION_REFUSALS[criterion.id]
            refusals.append(Refusal(code, criterion.reason, fix))
        elif questions:
            refusals.append(
                Refusal(
                    "open-question",
                    "; ".join(questions),
                    "Resolve each material open question, or accept it with (status: accepted) (accepted-by: NAME)",
                )
            )
        else:
            unmet.append(criterion)
    if unmet:
        listing = "".join(f"\n  {c.id}: {c.reason}" for c in unmet)
        refusals.append(
            Refusal(
                "unmet-criteria",
                f"unmet criteria:{listing}",
                "Fix the document and run `eil check` again; the AI's verdicts must be supplied with --judgments; "
                "or a configured confirmer may record an override for one criterion with a reason",
            )
        )
    if integrity:
        listing = "; ".join(f"{f.code} at {f.where}: {f.message}" for f in integrity)
        refusals.append(
            Refusal(
                "unmet-criteria",
                f"the document has errors: {listing}",
                "Correct them; they cannot be overridden",
            )
        )
    drafts = ai_draft_lines(text)
    if drafts and "unreviewed-ai-content" not in ctx_overrides:
        lines = ", ".join(str(n) for n in drafts[:10])
        refusals.append(
            Refusal(
                "unreviewed-ai-content",
                f"[ai-draft] tags remain on line(s) {lines}",
                "Review the AI's text, then remove each tag; or record an override for unreviewed-ai-content",
            )
        )
    return refusals


def approve(
    pkg: Package,
    config: Config,
    stage: str,
    by: str,
    attestation: str,
    played_back_to: str | None = None,
) -> dict[str, Any]:
    """Record one human's approval of ``stage``, or refuse and write nothing."""
    if stage not in STAGES:
        _require_stage_with_document(pkg, stage)
    if stage not in APPROVABLE:
        raise refuse(
            Refusal(
                "not-approvable",
                f"{stage} is never approved by a person",
                "Only requirements, functional, technical and completion carry an approval",
            )
        )
    _require_stage_with_document(pkg, stage)

    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(
            Refusal(
                "ai-approval",
                f"{by!r} is the AI; an approval must be a person's own confirmation",
                "Ask the developer to confirm",
            )
        )
    if not attestation.strip():
        refusals.append(
            Refusal(
                "attestation-required",
                "an approval needs the person's own confirmation text",
                "Ask the person and pass their words with --attestation",
            )
        )
    problem = confirmer_refusal(by, approvers_for(pkg, config, stage), stage)
    if problem:
        refusals.append(problem)
    refusals.extend(prior_stage_refusals(pkg, stage))
    refusals.extend(_open_challenge_refusals(pkg, stage))

    original = pkg.read(stage)
    text = original
    if "approval" not in Doc(text).regions:
        text = write_region(text, "approval", {}, heading="## Approval")
    ctx = build_context(pkg, stage, text)
    refusals.extend(_gate_refusals(pkg, stage, ctx, text))
    if refusals:
        raise refuse(*refusals)

    fingerprint = fingerprint_text(text)
    scan_document(ctx.doc, stage, ctx.parsed)  # attaches diagrams and exports so item hashes cover them
    record: dict[str, Any] = {
        "stage": stage,
        "by": by.strip(),
        "at": utc_now(),
        "fingerprint": fingerprint,
        "attestation": attestation.strip(),
    }
    if played_back_to and played_back_to.strip():
        record["played_back_to"] = played_back_to.strip()
    record["upstream"] = {
        earlier: fp
        for earlier in DEFINITION_STAGES
        if STAGES.index(earlier) < STAGES.index(stage) and (fp := pkg.fingerprint(earlier))
    }
    record["items"] = {item.id: item_hash(item) for item in ctx.parsed.items}
    record["prose_fingerprint"] = non_item_fingerprint(ctx.doc, ctx.parsed.items, ctx.doc.records())
    all_parsed = impact.parsed_story(pkg)
    all_parsed[stage] = ctx.parsed
    record["upstream_items"] = impact.upstream_item_hashes(pkg, stage, all_parsed)
    record["overrides_used"] = [str(o.get("id")) for o in ctx.overrides.values()]
    if stage in comprehension.ELIGIBLE_STAGES:  # copied so review sees skipped and revealed levels (FR-093)
        record["comprehension"] = comprehension.counts(ctx.doc.read_region("comprehension").obj or {})
    pkg.doc_path(stage).write_bytes(write_region(text, "approval", record).encode("utf-8"))
    return {
        "ok": True,
        "stage": stage,
        "approval": record,
        "text": f"Approved {stage} as {record['by']} at {record['at']}.",
    }


def override(
    pkg: Package, config: Config, stage: str, criterion: str, by: str, reason: str
) -> dict[str, Any]:
    """Record a named, reasoned override for one criterion, or refuse and write nothing (FR-045)."""
    _require_stage_with_document(pkg, stage)
    refusals: list[Refusal] = []
    if not reason.strip():
        refusals.append(
            Refusal("reason-required", "an override needs a reason", "Say why the criterion is being waived")
        )
    problem = confirmer_refusal(by, approvers_for(pkg, config, stage), stage)
    if problem:
        refusals.append(problem)
    if criterion not in overridable_ids(stage):
        known = ", ".join(overridable_ids(stage))
        refusals.append(
            Refusal(
                "unknown-criterion", f"{criterion!r} is not a criterion of {stage}", f"Use one of: {known}"
            )
        )
    if refusals:
        raise refuse(*refusals)
    record = {
        "id": next_override_id(pkg),
        "stage": stage,
        "criterion": criterion,
        "by": by.strip(),
        "at": utc_now(),
        "reason": reason.strip(),
    }
    pkg.doc_path(stage).write_bytes(
        append_record(pkg.read(stage), "Overrides", "override", record).encode("utf-8")
    )
    return {
        "ok": True,
        "override": record,
        "id": record["id"],
        "text": f"Recorded {record['id']}: {criterion} overridden by {record['by']}.",
    }


# ---- abbreviation (FR-040)


def authorisers_for(pkg: Package, config: Config) -> list[str]:
    """Who may abbreviate a stage: the configured list, else the story's developer."""
    return list(config.abbreviation_authorisers) or developer_identities(pkg, config)


def abbreviate(pkg: Package, config: Config, stage: str, by: str, reason: str) -> dict[str, Any]:
    """Record that a stage was abbreviated, who authorised it and why. A stage is never skipped: it
    needs a document. The record is part of the document, so an approved stage needs approving again."""
    if stage not in STAGES:
        _require_stage_with_document(pkg, stage)
    if not pkg.exists(stage):
        raise refuse(
            Refusal(
                "cannot-skip",
                f"{stage} has no document, and a stage is abbreviated, never skipped",
                f"Start it with: eil stage-init {stage}",
            )
        )
    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(
            Refusal(
                "ai-approval", f"{by!r} is the AI; a person authorises an abbreviation", "Ask the developer"
            )
        )
    else:
        problem = confirmer_refusal(by, authorisers_for(pkg, config), stage, authorising=True)
        if problem:
            refusals.append(problem)
    if not reason.strip():
        refusals.append(
            Refusal(
                "reason-required", "an abbreviation needs a reason", "Say why this stage is being shortened"
            )
        )
    if refusals:
        raise refuse(*refusals)
    record = {"stage": stage, "by": by.strip(), "at": utc_now(), "reason": reason.strip()}
    text = pkg.read(stage)
    existing = next((r for r in pkg.doc(stage).records() if r.kind == "abbreviation"), None)
    updated = (
        replace_record(text, existing, record)
        if existing is not None
        else append_record(text, "Abbreviation", "abbreviation", record)
    )
    pkg.doc_path(stage).write_bytes(updated.encode("utf-8"))
    return {
        "ok": True,
        "abbreviation": record,
        "text": f"{stage} is abbreviated (authorised by {record['by']}); it must still pass its gate.",
    }


# ---- challenges (FR-034 to FR-038)

CHALLENGE_STAGES = ("requirements", "functional", "technical", "ai-spec")
RESPONSES = ("accepted", "rejected", "deferred")
_CHALLENGE_ID = re.compile(r"CH-(\d{3,})")
_ITEM_ID = re.compile(r"^(?:[A-Z]{2,3}-\d{3}|T\d{3,})$")


def _challenge_records(doc: Doc) -> list[Any]:
    return [r for r in doc.records() if r.kind == "challenge" and isinstance(r.obj, dict)]


def open_challenge_ids(doc: Doc) -> list[str]:
    """Challenges still standing: open, or answered two different ways (a conflict)."""
    return [
        str(r.obj.get("id", "?")) for r in _challenge_records(doc) if r.obj.get("status", "open") != "closed"
    ]


def _next_challenge_id(pkg: Package) -> str:
    highest = 0
    for stage in pkg.existing_stages():
        try:
            records_ = _challenge_records(pkg.doc(stage))
        except UnicodeDecodeError:
            continue
        for record in records_:
            found = _CHALLENGE_ID.fullmatch(str(record.obj.get("id", "")))
            highest = max(highest, int(found[1]) if found else 0)
    return f"CH-{highest + 1:03d}"


def _same_point(a: str, b: str) -> bool:
    def flat(text: str) -> str:
        return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())

    left, right = flat(a), flat(b)
    return left == right or difflib.SequenceMatcher(None, left, right).ratio() >= 0.9


def _target_exists(pkg: Package, stage: str, target: str) -> bool:
    if _ITEM_ID.match(target):
        for name in pkg.existing_stages():
            try:
                parsed = parse_document(pkg.doc(name))
            except UnicodeDecodeError:
                continue
            if any(i.id == target for i in parsed.items) or any(t.id == target for t in parsed.tasks):
                return True
        return False
    return Sections(pkg.doc(stage)).find(target) is not None


def add_challenge(pkg: Package, stage: str, target: str, text: str, by: str | None = None) -> dict[str, Any]:
    """Record an open challenge (FR-034, FR-035), unless a person already settled this very point."""
    if stage not in STAGES:
        _require_stage_with_document(pkg, stage)
    if stage not in CHALLENGE_STAGES:
        raise refuse(
            Refusal(
                "stage-not-eligible",
                f"{stage} takes no challenges",
                f"Challenges are raised at a definition stage: {', '.join(CHALLENGE_STAGES)}",
            )
        )
    _require_stage_with_document(pkg, stage)
    if not text.strip() or not target.strip():
        raise usage_error("a challenge needs a target and a specific text")
    if not _target_exists(pkg, stage, target.strip()):
        raise refuse(
            Refusal(
                "unknown-item",
                f"{target!r} is neither an item of this story nor a section of {stage}",
                "Name the item id or section the challenge is about",
            )
        )
    for existing in _challenge_records(pkg.doc(stage)):
        found = existing.obj
        if found.get("target") != target.strip() or not _same_point(str(found.get("text", "")), text):
            continue
        state = found.get("status", "open")
        if state != "closed":
            raise refuse(
                Refusal(
                    "duplicate-of-closed",
                    f"{found.get('id')} raises the same point and is still open",
                    "Answer it instead of raising it again",
                )
            )
        if found.get("response") in ("rejected", "deferred"):
            raise refuse(
                Refusal(
                    "duplicate-of-closed",
                    f"{found.get('id')} raised this point and it was {found['response']} by {found.get('responder')}: "
                    f"{found.get('reason', '')}",
                    "A recorded response is a standing constraint; do not raise it again (FR-038)",
                )
            )
    record = {
        "id": _next_challenge_id(pkg),
        "stage": stage,
        "raised_by": (by or "ai").strip() or "ai",
        "raised_at": utc_now(),
        "target": target.strip(),
        "text": text.strip(),
        "status": "open",
    }
    pkg.doc_path(stage).write_bytes(
        append_record(pkg.read(stage), "Challenges", "challenge", record).encode("utf-8")
    )
    return {
        "ok": True,
        "id": record["id"],
        "challenge": record,
        "text": f"Raised {record['id']} on {target}.",
    }


def _find_challenge(pkg: Package, challenge_id: str) -> tuple[str, Any] | None:
    for stage in pkg.existing_stages():
        try:
            found = _challenge_records(pkg.doc(stage))
        except UnicodeDecodeError:
            continue
        for record in found:
            if record.obj.get("id") == challenge_id:
                return stage, record
    return None


def answer_challenge(
    pkg: Package, config: Config, challenge_id: str, response: str, by: str, reason: str | None = None
) -> dict[str, Any]:
    """Record a person's answer (FR-036). Two people answering differently make a conflict that any
    configured confirmer settles with the next answer."""
    located = _find_challenge(pkg, challenge_id)
    if located is None:
        raise refuse(
            Refusal(
                "unknown-item",
                f"{challenge_id} is not a challenge of this story",
                "Check the id with eil status",
            )
        )
    stage, record = located
    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(
            Refusal("ai-approval", f"{by!r} is the AI; a person answers a challenge", "Ask the developer")
        )
    else:
        problem = confirmer_refusal(by, approvers_for(pkg, config, stage), stage)
        if problem:
            refusals.append(problem)
    if response in ("rejected", "deferred") and not (reason or "").strip():
        refusals.append(
            Refusal(
                "reason-required",
                f"{response} needs a reason" + (" that accepts the risk" if response == "deferred" else ""),
                "Say why the challenge is set aside",
            )
        )
    if refusals:
        raise refuse(*refusals)

    current: dict[str, Any] = dict(record.obj)
    answer = {"responder": by.strip(), "response": response, "at": utc_now()}
    if reason and reason.strip():
        answer["reason"] = reason.strip()
    status = current.get("status", "open")
    conflict = False
    if status == "closed" and not same_person(by, str(current.get("responder", ""))):
        if current.get("response") == response:
            return {
                "ok": True,
                "id": challenge_id,
                "challenge": current,
                "conflict": False,
                "text": f"{challenge_id} already answered the same way.",
            }
        earlier = {k: current[k] for k in ("responder", "response", "at", "reason") if k in current}
        for key in ("responder", "response", "at", "reason"):
            current.pop(key, None)
        current["status"] = "conflict"
        current["responses"] = [earlier, answer]
        conflict = True
    else:
        settling = status == "conflict"
        for key in ("responder", "response", "at", "reason", "responses"):
            current.pop(key, None)
        current.update(answer)
        current["status"] = "closed"
        if settling:
            current["resolved_conflict"] = True
    pkg.doc_path(stage).write_bytes(replace_record(pkg.read(stage), record, current).encode("utf-8"))
    text = (
        f"{challenge_id} is now in conflict: two people answered differently; a configured confirmer must settle it."
        if conflict
        else f"{challenge_id} {response} by {by.strip()}."
    )
    return {"ok": True, "id": challenge_id, "challenge": current, "conflict": conflict, "text": text}


def _open_challenge_refusals(pkg: Package, stage: str) -> list[Refusal]:
    standing = [
        f"{r.obj.get('id', '?')} ({r.obj.get('status', 'open')})"
        for r in _challenge_records(pkg.doc(stage))
        if r.obj.get("status", "open") != "closed"
    ]
    if not standing:
        return []
    return [
        Refusal(
            "open-challenge",
            f"open challenge(s) on {stage}: {', '.join(standing)}",
            "A person answers each with `eil challenge answer` (accepted, rejected with a reason, or deferred); a conflict is settled by a configured confirmer",
        )
    ]


__all__ = [
    "abbreviate",
    "approve",
    "override",
    "next_override_id",
    "utc_now",
    "criteria_for",
    "EXTRA_OVERRIDABLE",
]

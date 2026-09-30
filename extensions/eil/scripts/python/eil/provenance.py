"""Human-decided provenance: the ``(decided: ID)`` clause, ``eil amend`` and ``eil review``
(D-24, D-25, D-28).

Text that is a human's own words, copied verbatim from a decision they already made — an accepted
challenge, a resolved open question, a clarify answer, or an ``eil review`` acceptance — carries
``(decided: ID)`` instead of ``[ai-draft]``. This module checks that the citation is real and in an
eligible state; it cannot, and does not try to, check that the marked text is a faithful
transcription of what the human said (Principle II: detectable, not tamper-proof).

It provides two ways to re-sign a stage's approval once every change since it is accounted for:
``amend``, citing decisions the human already made elsewhere, and ``eil review``, walking the human
through each change right now and recording their "ok" as the citation itself.
"""

from __future__ import annotations

import re
from typing import Any

from . import comprehension, impact
from .artifacts import scan_document
from .blocks import Doc, append_record, write_region
from .clock import utc_now
from .fingerprint import fingerprint_text
from .gates import ai_draft_lines
from .identity import Config, confirmer_refusal, is_ai_actor
from .package import APPROVABLE, STAGES, Package
from .records import DEFINITION_STAGES, approvers_for
from .results import Finding, Refusal, refuse, usage_error
from .trace import Item, ParseResult, item_hash, parse_document, section_fingerprints

DECIDED_KINDS = ("CH", "OQ", "AIS", "RVW")
REVIEW_HEADING = "Reviews"
_REVIEW_ID = re.compile(r"RVW-(\d{3,})")
_AI_DRAFT_TAG = re.compile(r"\s*\[ai-draft\]")


def _all_parsed(pkg: Package) -> dict[str, ParseResult]:
    return impact.parsed_story(pkg)


def _item_by_id(parsed: dict[str, ParseResult], item_id: str) -> Item | None:
    for result in parsed.values():
        for item in result.items:
            if item.id == item_id:
                return item
    return None


def _stage_of(parsed: dict[str, ParseResult], item_id: str) -> str | None:
    for stage, result in parsed.items():
        if any(item.id == item_id for item in result.items):
            return stage
    return None


def _challenge_response(pkg: Package, challenge_id: str) -> tuple[bool, str | None]:
    """``(found, response)``: whether the challenge exists, and its recorded response if it does."""
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        for record in doc.records():
            if record.kind == "challenge" and record.obj and record.obj.get("id") == challenge_id:
                return True, record.obj.get("response")
    return False, None


def _review_records(pkg: Package) -> list[Any]:
    """Every ``eil:review`` record in the story, whatever stage it was written under."""
    found = []
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        found += [r for r in doc.records() if r.kind == "review" and isinstance(r.obj, dict)]
    return found


def decided_eligible(
    pkg: Package, decided_id: str, parsed: dict[str, ParseResult] | None = None
) -> str | None:
    """Why ``decided_id`` cannot back a ``(decided: ...)`` clause or ``--from``, or ``None``."""
    kind = decided_id.split("-")[0]
    if kind not in DECIDED_KINDS:
        return f"{decided_id!r} is not a CH-###, OQ-###, AIS-### or RVW-### id"
    if kind == "CH":
        found, response = _challenge_response(pkg, decided_id)
        if not found:
            return f"{decided_id} is not a challenge of this story"
        if response != "accepted":
            return f"{decided_id} is not accepted (it is {response or 'open'})"
        return None
    if kind == "RVW":
        found = any(r.obj.get("id") == decided_id for r in _review_records(pkg))
        return None if found else f"{decided_id} is not a recorded review of this story"
    parsed = parsed if parsed is not None else _all_parsed(pkg)
    item = _item_by_id(parsed, decided_id)
    if item is None:
        return f"{decided_id} is not an item of this story"
    if kind == "OQ" and item.status not in ("resolved", "accepted"):
        return f"{decided_id} is not resolved or accepted (it is {item.status or 'open'})"
    return None


def decided_findings(pkg: Package, stage: str, parsed: ParseResult) -> list[Finding]:
    """``decided-source-invalid`` for every ``(decided: ...)`` clause that cannot be verified."""
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    findings: list[Finding] = []
    for item in parsed.items:
        if item.decided is None:
            continue
        problem = decided_eligible(pkg, item.decided, all_parsed)
        if problem:
            findings.append(Finding("decided-source-invalid", item.id, f"{item.id}: {problem}"))
    return findings


# ---- shared machinery for eil amend and eil review (D-25, D-28)


def _require_reviewable(pkg: Package, stage: str) -> Any:
    """The stage's current ``StageState``, or refuse. Shared by ``amend`` and ``eil review``."""
    if stage not in APPROVABLE:
        raise refuse(
            Refusal(
                "not-amendable",
                f"{stage} is never approved by a person",
                "Only requirements, functional, technical and completion carry an approval",
            )
        )
    state = pkg.state(stage)
    if state.approval is None or state.state != "needs-re-review":
        raise refuse(
            Refusal(
                "not-amendable",
                f"{stage} is {state.state}, not a previously approved stage now needing re-review",
                "This re-signs an existing approval; a first approval is /speckit-eil-approve",
            )
        )
    return state


def _confirmer_refusals(
    pkg: Package, config: Config, stage: str, by: str, attestation: str | None
) -> list[Refusal]:
    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(
            Refusal(
                "ai-approval",
                f"{by!r} is the AI; only a person may confirm",
                "Ask the developer to confirm",
            )
        )
    if attestation is not None and not attestation.strip():
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
    return refusals


def _changed_roots(pkg: Package, stage: str, all_parsed: dict[str, ParseResult], approval: dict) -> list[str]:
    """Every id whose change is why ``stage`` needs re-review: its own edited items, and any id in
    its recorded ``upstream_items`` whose current hash no longer matches (D-26) — a downstream stage
    with no edit of its own, only an upstream one propagating in, still has something to cover."""
    own = [i for i in impact.changed_items(pkg, all_parsed) if _stage_of(all_parsed, i) == stage]
    recorded_upstream = approval.get("upstream_items") or {}
    current = pkg.current_item_hashes()
    propagated = [i for i, h in recorded_upstream.items() if current.get(i) != h]
    return sorted(set(own) | set(propagated))


def _uncovered_items(
    changed: list[str], from_ids: list[str], all_parsed: dict[str, ParseResult]
) -> list[str]:
    uncovered = []
    for item_id in changed:
        item = _item_by_id(all_parsed, item_id)
        if item is None or item.decided is None or item.decided not in from_ids:
            uncovered.append(item_id)
    return uncovered


def _uncovered_sections(
    doc: Doc, parsed: ParseResult, approval: dict, from_ids: list[str], all_reviews: list[Any]
) -> list[str] | None:
    """Section titles changed since the approval with no matching ``eil:review`` record naming that
    section among ``from_ids``. ``None`` means the approval predates ``section_fingerprints`` — a
    stale-format approval the caller must refuse rather than silently trust."""
    recorded = approval.get("section_fingerprints")
    if not isinstance(recorded, dict):
        return None
    current = section_fingerprints(doc, parsed.items)
    reviewed_sections = {
        r.obj["target"] for r in all_reviews if r.obj.get("unit") == "section" and r.obj.get("id") in from_ids
    }
    changed = sorted(set(current) | set(recorded), key=lambda name: (name not in current, name))
    return [
        name for name in changed if current.get(name) != recorded.get(name) and name not in reviewed_sections
    ]


def _ensure_comprehension_current(
    pkg: Package, config: Config, stage: str, doc: Doc, text: str, by: str
) -> None:
    """When ``stage`` takes a comprehension check, make sure the record covers the current text
    before an amendment or review is signed — reusing delta comprehension's own zero-question
    short-circuit (D-27) so this costs nothing extra when everything really is covered, but keeps
    FUN-G16/TEC-G19 honest rather than silently skipped, which ``amend`` used to do."""
    if stage not in comprehension.ELIGIBLE_STAGES:
        return
    fingerprint = fingerprint_text(text)
    state = comprehension.summarise(doc.read_region("comprehension").obj, fingerprint)
    if state["state"] == "complete":
        return
    plan = comprehension.plan(pkg, stage)
    delta = plan.get("delta")
    if not delta or not delta.get("human_decided"):
        raise refuse(
            Refusal(
                "comprehension-prerequisites",
                "the comprehension check for this version is not current, and not every change is "
                "a recorded decision, so it cannot be completed without a question",
                "Run /speckit-eil-comprehend first",
            )
        )
    for level in comprehension.LEVELS:
        comprehension.record(pkg, config, stage, level, "not-applicable", by=by, reason=delta["reason"])


def _re_sign(
    pkg: Package,
    config: Config,
    stage: str,
    from_ids: list[str],
    by: str,
    attestation: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    """The shared core of ``amend`` and ``eil review finish``: refuse unless every change since the
    last approval is covered by a cited decision, then re-sign. ``extra`` is merged into the written
    record (``amended``/``amends``, or ``reviewed_change_by_change``/``reviewed_ids``)."""
    if not from_ids:
        raise usage_error("at least one covering id is required")
    state = _require_reviewable(pkg, stage)
    refusals = _confirmer_refusals(pkg, config, stage, by, attestation)

    text = pkg.read(stage)
    doc = pkg.doc(stage)
    drafts = ai_draft_lines(text)
    if drafts:
        lines = ", ".join(str(n) for n in drafts[:10])
        refusals.append(
            Refusal(
                "unreviewed-ai-content",
                f"[ai-draft] tags remain on line(s) {lines}",
                "Review the AI's text, then remove each tag",
            )
        )

    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)  # attaches diagrams/exports so item hashes match approve()
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    all_reviews = _review_records(pkg)

    for decided_id in from_ids:
        problem = decided_eligible(pkg, decided_id, all_parsed)
        if problem:
            refusals.append(
                Refusal(
                    "unknown-item",
                    problem,
                    "Cite an accepted challenge, a resolved open question, an AIS clarify answer, "
                    "or a recorded eil review acceptance",
                )
            )

    uncovered_sections = _uncovered_sections(doc, parsed, state.approval, from_ids, all_reviews)
    if uncovered_sections is None:
        refusals.append(
            Refusal(
                "amend-not-covered",
                "the last approval predates section_fingerprints and carries nothing to compare",
                "Approve the stage fully once with /speckit-eil-approve to enable this after it",
            )
        )
    elif uncovered_sections:
        refusals.append(
            Refusal(
                "amend-not-covered",
                "text outside any item changed with no matching review: " + ", ".join(uncovered_sections),
                "Review each section with eil review accept --sections, or run the full /speckit-eil-approve",
            )
        )

    changed = _changed_roots(pkg, stage, all_parsed, state.approval)
    uncovered_items = _uncovered_items(changed, from_ids, all_parsed)
    if uncovered_items:
        refusals.append(
            Refusal(
                "amend-not-covered",
                f"changed since the last approval with no matching (decided: ...) among {from_ids}: "
                f"{', '.join(uncovered_items)}",
                "Cite every human decision that covers a change, or run the full /speckit-eil-approve",
            )
        )
    if refusals:
        raise refuse(*refusals)

    _ensure_comprehension_current(pkg, config, stage, doc, text, by)
    # Re-read: comprehension.record() only touches the comprehension region, but re-read the doc
    # object so its cache reflects the just-written region before section_fingerprints reads it.
    doc = pkg.doc(stage)
    text = pkg.read(stage)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)

    fingerprint = fingerprint_text(text)
    record: dict[str, Any] = {
        "stage": stage,
        "by": by.strip(),
        "at": utc_now(),
        "fingerprint": fingerprint,
        "attestation": attestation.strip(),
        **extra,
    }
    record["upstream"] = {
        earlier: fp
        for earlier in DEFINITION_STAGES
        if STAGES.index(earlier) < STAGES.index(stage) and (fp := pkg.fingerprint(earlier))
    }
    record["items"] = {item.id: item_hash(item) for item in parsed.items}
    record["section_fingerprints"] = section_fingerprints(doc, parsed.items)
    record["upstream_items"] = impact.upstream_item_hashes(pkg, stage, all_parsed)
    record["overrides_used"] = list(state.approval.get("overrides_used") or [])
    if stage in comprehension.ELIGIBLE_STAGES:
        record["comprehension"] = comprehension.counts(doc.read_region("comprehension").obj or {})
    pkg.doc_path(stage).write_bytes(write_region(text, "approval", record).encode("utf-8"))
    return {"ok": True, "stage": stage, "approval": record}


# ---- eil amend (D-25)


def amend(
    pkg: Package, config: Config, stage: str, from_ids: list[str], by: str, attestation: str
) -> dict[str, Any]:
    """Re-sign ``stage``'s approval, or refuse and write nothing.

    Succeeds only when every item and section that changed since the last approval is covered by a
    cited human decision (a challenge, an open question, a clarify answer, or an ``eil review``
    acceptance), no ``[ai-draft]`` tag remains, and the comprehension check (if the stage takes one)
    is current. Anything else needs the full ``/speckit-eil-approve``.
    """
    result = _re_sign(
        pkg, config, stage, from_ids, by, attestation, {"amended": True, "amends": list(from_ids)}
    )
    result["text"] = (
        f"Amended {stage} as {result['approval']['by']} at {result['approval']['at']}, from {', '.join(from_ids)}."
    )
    return result


# ---- eil review (D-28): walk the human through each change, right now


def _highest_review_number(pkg: Package) -> int:
    highest = 0
    for record in _review_records(pkg):
        match = _REVIEW_ID.fullmatch(str(record.obj.get("id", "")))
        highest = max(highest, int(match[1]) if match else 0)
    return highest


def start(pkg: Package, stage: str) -> dict[str, Any]:
    """The items and sections changed since ``stage``'s last approval, ids and titles only — the
    prompt reads the actual diff with ``git diff``, the same way ``/speckit-eil-approve`` does; this
    module has never stored a document's old text, only ever a fingerprint of it."""
    state = _require_reviewable(pkg, stage)
    doc = pkg.doc(stage)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    all_reviews = [r for r in _review_records(pkg) if r.obj.get("stage") == stage]

    changed_items = _changed_roots(pkg, stage, all_parsed, state.approval)
    items_out = []
    for item_id in changed_items:
        item = _item_by_id(all_parsed, item_id)
        items_out.append(
            {
                "id": item_id,
                "stage": _stage_of(all_parsed, item_id),
                "decided": item.decided if item else None,
                "reviewed": item is not None
                and item.decided is not None
                and any(r.obj.get("id") == item.decided for r in all_reviews),
            }
        )

    recorded_sections = state.approval.get("section_fingerprints")
    sections_out: list[dict[str, Any]] = []
    if isinstance(recorded_sections, dict):
        current_sections = section_fingerprints(doc, parsed.items)
        reviewed_titles = {r.obj["target"] for r in all_reviews if r.obj.get("unit") == "section"}
        names = sorted(set(current_sections) | set(recorded_sections))
        for name in names:
            if current_sections.get(name) != recorded_sections.get(name):
                sections_out.append({"title": name, "reviewed": name in reviewed_titles})

    return {
        "ok": True,
        "stage": stage,
        "items": items_out,
        "sections": sections_out,
        "text": f"{len(items_out)} item(s) and {len(sections_out)} section(s) changed since the last approval.",
    }


def accept(
    pkg: Package,
    config: Config,
    stage: str,
    items: list[str],
    sections: list[str],
    by: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Record the human's "ok" to one or more changed items and/or sections, right now. For an item,
    writes ``(decided: RVW-###)`` onto its line (replacing an ``[ai-draft]`` tag if present) and the
    ``eil:review`` record together, as one action — never an AI hand-edit the helper has to trust
    after the fact."""
    if not items and not sections:
        raise usage_error("accept needs at least one of --items or --sections")
    state = _require_reviewable(pkg, stage)
    refusals = _confirmer_refusals(pkg, config, stage, by, None)
    if refusals:
        raise refuse(*refusals)

    text = pkg.read(stage)
    doc = pkg.doc(stage)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    changed_items = set(_changed_roots(pkg, stage, all_parsed, state.approval))

    unknown = [i for i in items if i not in changed_items or _stage_of(all_parsed, i) != stage]
    if unknown:
        raise refuse(
            Refusal(
                "unknown-item",
                f"not a changed item of {stage} since its last approval: {', '.join(unknown)}",
                "Use an id from eil review start",
            )
        )
    recorded_sections = state.approval.get("section_fingerprints")
    current_sections = section_fingerprints(doc, parsed.items) if isinstance(recorded_sections, dict) else {}
    bad_sections = [
        s
        for s in sections
        if not isinstance(recorded_sections, dict) or current_sections.get(s) == recorded_sections.get(s)
    ]
    if bad_sections:
        raise refuse(
            Refusal(
                "unknown-item",
                f"not a changed section of {stage} since its last approval: {', '.join(bad_sections)}",
                "Use a section title from eil review start",
            )
        )

    created: list[str] = []
    highest = _highest_review_number(pkg)
    note_field = {"note": note.strip()} if note and note.strip() else {}
    for item_id in items:
        highest += 1
        record_id = f"RVW-{highest:03d}"
        item = _item_by_id(all_parsed, item_id)
        text = _write_decided(text, item, record_id)
        text = append_record(
            text,
            REVIEW_HEADING,
            "review",
            {
                "id": record_id,
                "stage": stage,
                "unit": "item",
                "target": item_id,
                "by": by.strip(),
                "at": utc_now(),
                **note_field,
            },
        )
        created.append(record_id)
    for name in sections:
        highest += 1
        record_id = f"RVW-{highest:03d}"
        text = append_record(
            text,
            REVIEW_HEADING,
            "review",
            {
                "id": record_id,
                "stage": stage,
                "unit": "section",
                "target": name,
                "by": by.strip(),
                "at": utc_now(),
                **note_field,
            },
        )
        created.append(record_id)

    pkg.doc_path(stage).write_bytes(text.encode("utf-8"))
    return {
        "ok": True,
        "stage": stage,
        "created": created,
        "text": f"Recorded {', '.join(created)}.",
    }


def _write_decided(text: str, item: Item | None, record_id: str) -> str:
    """Add ``(decided: RVW-###)`` to an item's defining line, removing ``[ai-draft]`` if present."""
    if item is None:
        return text
    lines = text.split("\n")
    line = _AI_DRAFT_TAG.sub("", lines[item.line - 1])
    lines[item.line - 1] = line.rstrip() + f" (decided: {record_id})"
    return "\n".join(lines)


def finish(pkg: Package, config: Config, stage: str, by: str, attestation: str) -> dict[str, Any]:
    """Re-sign ``stage``'s approval from every ``eil review`` acceptance recorded for it since its
    last approval, or refuse the same way ``amend`` would for anything still uncovered."""
    all_reviews = [r for r in _review_records(pkg) if r.obj.get("stage") == stage]
    from_ids = [str(r.obj["id"]) for r in all_reviews]
    if not from_ids:
        raise refuse(
            Refusal(
                "amend-not-covered",
                f"no eil review acceptance is recorded for {stage} yet",
                "Run eil review accept for each changed item or section first",
            )
        )
    result = _re_sign(
        pkg,
        config,
        stage,
        from_ids,
        by,
        attestation,
        {"reviewed_change_by_change": True, "reviewed_ids": from_ids},
    )
    result["text"] = (
        f"Reviewed and re-approved {stage} as {result['approval']['by']} at {result['approval']['at']}, "
        f"from {len(from_ids)} change(s) reviewed one at a time."
    )
    return result


__all__ = ["decided_eligible", "decided_findings", "amend", "start", "accept", "finish"]

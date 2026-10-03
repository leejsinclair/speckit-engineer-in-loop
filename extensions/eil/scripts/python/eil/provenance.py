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
from dataclasses import dataclass
from typing import Any

from . import changelog, comprehension, corrections, impact, verification
from .artifacts import scan_document
from .blocks import Doc, RegionError, append_record
from .blockstatus import adopt, source_settled, unreviewed
from .clock import utc_now
from .content import blocks_of
from .fingerprint import fingerprint_text
from .identity import Config, confirmer_refusal, is_ai_actor
from .package import APPROVABLE, STAGES, Package
from .records import DEFINITION_STAGES, approvers_for
from .results import Finding, Refusal, refuse, usage_error
from .trace import Item, ParseResult, item_hash, parse_document, section_fingerprints

DECIDED_KINDS = ("CH", "OQ", "AIS", "RVW", "CR")
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
    pkg: Package, decided_id: str, parsed: dict[str, ParseResult] | None = None, item: Item | None = None
) -> str | None:
    """Why ``decided_id`` cannot back a ``(decided: ...)`` clause or ``--from``, or ``None``. A ``CR``
    backs a clause only on its own item, and only while that item's text equals the recorded wording."""
    kind = decided_id.split("-")[0]
    if kind not in DECIDED_KINDS:
        return f"{decided_id!r} is not a CH-###, OQ-###, AIS-###, RVW-### or CR-### id"
    if kind == "CR":
        return corrections.wording_problem(pkg, decided_id, item)[1]
    if kind == "CH":
        found, response = _challenge_response(pkg, decided_id)
        if not found:
            return f"{decided_id} is not a challenge of this story"
        if response != "accepted":
            return f"{decided_id} is not accepted (it is {response or 'open'})"
        return None
    if kind == "RVW":
        found = decided_id in acceptance_ids(pkg) or any(
            r.obj.get("id") == decided_id for r in _review_records(pkg)
        )
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
        problem = decided_eligible(pkg, item.decided, all_parsed, item)
        if not problem:
            continue
        code = "decided-source-invalid"
        if item.decided.startswith("CR-") and corrections.wording_problem(pkg, item.decided, item)[0]:
            code = "correction-wording-mismatch"  # ordinary review, not unverifiable provenance
        findings.append(Finding(code, item.id, f"{item.id}: {problem}"))
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
    state = comprehension.summarise(pkg.record(stage, "comprehension"), fingerprint)
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
    answered: set[str] | None = None,
    extra_refusals: list[Refusal] | None = None,
) -> dict[str, Any]:
    """The shared core of ``amend``, ``eil review finish`` and ``review confirm``: refuse unless every
    change since the last approval is covered by a cited decision (or, for ``confirm``, an accepted
    ``changes`` answer in ``answered``), then re-sign. ``extra`` is merged into the written record
    (``amended``/``amends``, ``reviewed_change_by_change``/``reviewed_ids``, or ``reached``/``rests_on``)."""
    confirming = answered is not None
    answered = answered or set()
    if not from_ids and not confirming:
        raise usage_error("at least one covering id is required")
    state = _require_reviewable(pkg, stage)
    refusals = [*(extra_refusals or []), *_confirmer_refusals(pkg, config, stage, by, attestation)]

    text = pkg.read(stage)
    doc = pkg.doc(stage)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)  # attaches diagrams/exports so item hashes match approve()
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    all_reviews = _review_records(pkg)
    reviewed_sections = {
        r.obj["target"] for r in all_reviews if r.obj.get("unit") == "section" and r.obj.get("id") in from_ids
    }
    pending = [
        i
        for i in unreviewed(pkg, stage)
        if getattr(getattr(i.block, "item", None), "decided", None) not in from_ids
        and i.block.section not in reviewed_sections
        and i.key not in answered
    ]
    if pending:
        listing = ", ".join(i.key for i in pending[:10])
        refusals.append(
            Refusal(
                "unreviewed-ai-content",
                f"{len(pending)} block(s) have not been reviewed: {listing}",
                f"Answer the inferred list for {stage}",
            )
        )



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
    uncovered_items = _uncovered_items([c for c in changed if c not in answered], from_ids, all_parsed)
    if uncovered_items:
        refusals.append(
            Refusal(
                "amend-not-covered",
                f"changed since the last approval with no matching (decided: ...) among {from_ids}: "
                f"{', '.join(uncovered_items)}",
                "Cite every human decision that covers a change, or run the full /speckit-eil-approve",
            )
        )
    if stage == "completion":
        open_findings = [p for f in verification.review_findings(pkg) for p in verification.finding_problems(f)]
        if open_findings:
            refusals.append(
                Refusal("review-finding-open", "; ".join(open_findings[:5]), "Resolve or except each review finding in the Verification document")
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
    if record.get("reached") == "carried-forward":
        record["sign_off"] = record.pop("attestation")
    record["upstream"] = {
        earlier: fp
        for earlier in DEFINITION_STAGES
        if STAGES.index(earlier) < STAGES.index(stage) and (fp := pkg.fingerprint(earlier))
    }
    record["items"] = {item.id: item_hash(item) for item in parsed.items}
    record["section_fingerprints"] = section_fingerprints(doc, parsed.items)
    record["upstream_items"] = impact.upstream_item_hashes(pkg, stage, all_parsed)
    record["overrides_used"] = list(state.approval.get("overrides_used") or [])
    if stage == "completion":
        record["review_findings"] = verification.finding_hashes(pkg)
    if stage in comprehension.ELIGIBLE_STAGES:
        record["comprehension"] = comprehension.counts(pkg.record(stage, "comprehension") or {})
    pkg.write_record(stage, "approval", record, text=text)
    return {"ok": True, "stage": stage, "approval": record}


@dataclass
class ChangeRow:
    id: str
    item: Item | None
    hash: str
    covered_by: str | None
    why: str


def change_rows(pkg: Package, stage: str) -> list[ChangeRow]:
    """The items that changed since ``stage``'s approval, each with the verified decision covering it."""
    if stage not in APPROVABLE:
        return []
    state = pkg.state(stage)
    if state.approval is None or state.state != "needs-re-review":
        return []
    doc = pkg.doc(stage)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)
    all_parsed = _all_parsed(pkg)
    all_parsed[stage] = parsed
    recorded = state.approval.get("items") if isinstance(state.approval.get("items"), dict) else {}
    rows = []
    for item_id in _changed_roots(pkg, stage, all_parsed, state.approval):
        item = _item_by_id(all_parsed, item_id)
        decided = item.decided if item is not None else None
        covered = decided if decided and decided_eligible(pkg, decided, all_parsed, item) is None else None
        if item is None:
            why = "removed since it was approved"
        elif item_id not in recorded:
            why = "new since it was approved"
        else:
            why = "changed since it was approved"
        rows.append(ChangeRow(item_id, item, item_hash(item) if item else "removed", covered, why))
    return rows


def _summary_refusal(missing: list[str]) -> Refusal:
    return Refusal(
        "summary-missing",
        f"no AI summary for: {', '.join(missing)}",
        "Draft a one-line summary per change and pass it with --summaries (review answer or review confirm)",
    )


def _origin(pkg: Package, stage: str, row: ChangeRow) -> str:
    for cr in corrections.open_for(pkg, stage):
        if cr.get("item") == row.id:
            return str(cr["id"])
    return row.covered_by or "edit"


def _record_changes(
    pkg: Package,
    stage: str,
    entries: list[dict[str, Any]],
    closing: list[str],
    by: str,
    at: str,
    approval_at: str | None,
) -> None:
    record = _load_record(pkg, stage)
    record.setdefault("changes", []).extend(entries)
    for cr_id in closing:
        corrections.close(record, cr_id, by.strip(), at, approval_at)
    _save_record(pkg, stage, record)
    changelog.refresh(Package(pkg.root), stage)


def _confirm_unapproved(
    pkg: Package, config: Config, stage: str, by: str, confirmation: str, summaries: dict[str, str]
) -> dict[str, Any]:
    """A stage nobody approves: close each open correction whose item is settled, and write no approval."""
    open_crs = corrections.open_for(pkg, stage) if pkg.exists(stage) else []
    if not open_crs:
        _require_reviewable(pkg, stage)
    refusals = _confirmer_refusals(pkg, config, stage, by, None)
    if not confirmation.strip():
        refusals.append(Refusal("confirmation-required", "a confirmation needs the person's own words", "Ask the person and pass their words with --confirmation"))
    settled = [c for c in open_crs if corrections.item_settled(pkg, stage, str(c.get("item")))]
    if not settled and not refusals:
        waiting = ", ".join(f"{c['id']} ({c.get('item')})" for c in open_crs)
        refusals.append(
            Refusal(
                "not-amendable",
                f"the item of {waiting} is not settled in {stage}",
                f"Answer the inferred list for {stage}, or edit the item with (decided: CR-###) first",
            )
        )
    missing = [str(c["item"]) for c in settled if not (summaries.get(str(c["item"])) or "").strip()]
    if missing and not refusals:
        refusals.append(_summary_refusal(missing))
    if refusals:
        raise refuse(*refusals)
    at = utc_now()
    entries = [
        changelog.entry(at, str(c["item"]), summaries[str(c["item"])], str(c["id"]), by.strip()) for c in settled
    ]
    _record_changes(pkg, stage, entries, [str(c["id"]) for c in settled], by, at, None)
    still = [str(c["id"]) for c in open_crs if c not in settled]
    closed = [str(c["id"]) for c in settled]
    return {
        "ok": True,
        "stage": stage,
        "closed": closed,
        "still_open": still,
        "text": f"Closed {', '.join(closed)} in {stage}; no approval is written for this stage."
        + (f" Still open: {', '.join(still)}." if still else ""),
    }


def confirm_changes(
    pkg: Package, config: Config, stage: str, by: str, confirmation: str, summaries: dict[str, str] | None = None
) -> dict[str, Any]:
    """Re-sign ``stage`` on the person's confirmation: carried forward when every change is a verified
    human decision, reviewed when some were answered on the changes list. The AI never supplies the
    confirmation (Constitution II). Every change needs the AI's one-line summary for the Change Log."""
    from . import reviews

    summaries = dict(summaries or {})
    if stage not in APPROVABLE:
        return _confirm_unapproved(pkg, config, stage, by, confirmation, summaries)
    _require_reviewable(pkg, stage)
    refusals = _confirmer_refusals(pkg, config, stage, by, None)
    if not confirmation.strip():
        refusals.append(
            Refusal("confirmation-required", "a confirmation needs the person's own words", "Ask the person and pass their words with --confirmation")
        )
    rows = change_rows(pkg, stage)
    answered = reviews.answered_changes(pkg, stage)
    conflicts = sorted(reviews.conflicted_keys(pkg, stage, {r.id: r.hash for r in rows}) & {r.id for r in rows})
    if conflicts:
        refusals.append(
            Refusal("acceptance-conflict", f"recorded answers disagree about: {', '.join(conflicts)}", "A configured confirmer answers the changes list again")
        )
    unanswered = [r.id for r in rows if r.covered_by is None and r.id not in answered]
    if unanswered:
        refusals.append(
            Refusal("changes-unanswered", f"changes with no recorded decision or answer: {', '.join(unanswered)}", f"Show `review list --kind changes` for {stage} and record the person's reply")
        )
    stored = _load_record(pkg, stage) if pkg.record_read(stage, "provenance").error is None else {}
    texts: dict[str, str] = {}
    for row in rows:
        text = (summaries.get(row.id) or "").strip() or changelog.stored_summary(stored, row.id, row.hash)
        if text:
            texts[row.id] = text
    missing = [r.id for r in rows if r.id not in texts]
    if missing and not refusals:
        refusals.append(_summary_refusal(missing))
    if refusals:
        raise refuse(*refusals)
    covered = {r.covered_by for r in rows if r.covered_by}
    taken = {answered[r.id][1] for r in rows if r.covered_by is None and r.id in answered}
    reached = "reviewed" if taken else "carried-forward"
    rests_on = sorted(covered | taken)
    origins = {r.id: _origin(pkg, stage, r) for r in rows}
    closing = [str(c["id"]) for c in corrections.open_for(pkg, stage) if c.get("item") in {r.id for r in rows}]
    result = _re_sign(
        pkg, config, stage, rests_on, by, confirmation,
        {"reached": reached, "rests_on": rests_on},
        answered={r.id for r in rows if r.covered_by is None},
    )  # fmt: skip
    at = result["approval"]["at"]
    entries = [changelog.entry(at, r.id, texts[r.id], origins[r.id], by.strip()) for r in rows]
    _record_changes(pkg, stage, entries, closing, by, at, at)
    if closing:
        result["closed"] = closing
    result["text"] = f"Confirmed {stage} as {result['approval']['by']} ({reached}), resting on {', '.join(rests_on) or 'no change'}."
    return result


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
    if not from_ids:
        raise usage_error("at least one covering id is required")
    _require_reviewable(pkg, stage)
    covering = {r.covered_by for r in change_rows(pkg, stage) if r.covered_by} | {
        str(r.obj["id"]) for r in _review_records(pkg) if r.obj.get("stage") == stage and r.obj.get("unit") == "section"
    }
    all_parsed = _all_parsed(pkg)
    outside = [i for i in from_ids if i not in covering and decided_eligible(pkg, i, all_parsed) is None]
    extra_refusals = (
        [
            Refusal(
                "amend-not-covering",
                f"{', '.join(outside)} does not cover any change to {stage}; the covering decisions are "
                f"{', '.join(sorted(covering)) or 'none'}",
                "Cite only the decisions that cover the changes, or use eil review confirm",
            )
        ]
        if outside
        else []
    )
    result = _re_sign(
        pkg, config, stage, from_ids, by, attestation,
        {"amended": True, "amends": list(from_ids), "reached": "carried-forward", "rests_on": list(from_ids)},
        extra_refusals=extra_refusals,
    )  # fmt: skip
    result["text"] = (
        f"Amended {stage} as {result['approval']['by']} at {result['approval']['at']}, from {', '.join(from_ids)}."
    )
    return result


# ---- eil review (D-28): walk the human through each change, right now


def acceptance_ids(pkg: Package) -> set[str]:
    """Every ``RVW`` id recorded as an acceptance in a provenance region (research D-36)."""
    found: set[str] = set()
    for stage in pkg.existing_stages():
        try:
            obj = pkg.record(stage, "provenance")
        except UnicodeDecodeError:
            continue
        for row in (obj or {}).get("acceptances", []):
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                found.add(row["id"])
    return found


def acceptance_numbers(pkg: Package) -> list[int]:
    return [int(m[1]) for i in acceptance_ids(pkg) if (m := _REVIEW_ID.fullmatch(i))]


def _highest_review_number(pkg: Package) -> int:
    highest = 0
    for record in _review_records(pkg):
        match = _REVIEW_ID.fullmatch(str(record.obj.get("id", "")))
        highest = max(highest, int(match[1]) if match else 0)
    for number in acceptance_numbers(pkg):
        highest = max(highest, number)
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

    from . import reviews

    return {
        "ok": True,
        "stage": stage,
        "kind": "changes",
        "digest": reviews.build_list(pkg, stage, "changes").digest,
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
        {"reviewed_change_by_change": True, "reviewed_ids": from_ids, "reached": "reviewed", "rests_on": from_ids},
    )
    result["text"] = (
        f"Reviewed and re-approved {stage} as {result['approval']['by']} at {result['approval']['at']}, "
        f"from {len(from_ids)} change(s) reviewed one at a time."
    )
    return result


# ---- classification of content blocks (research D-32). The [ai-draft] cue is never written into a
# document (003 D-50): `eil show` and the review lists show it.

_ID = re.compile(r"^[A-Z]+-\d+$")
_CUE = " [ai-draft]"
_CLASSIFY_KEYS = frozenset({"stage", "blocks"})
_VERDICT_KEYS = frozenset({"block", "adds"})


def _check_classification(pkg: Package, stage: str, data: Any) -> dict[str, str | None]:
    """``{block key: adds}`` from a classification file, or a usage error."""
    if not isinstance(data, dict) or set(data) != _CLASSIFY_KEYS:
        raise usage_error('a classification needs exactly "stage" and "blocks"')
    if data["stage"] != stage:
        raise usage_error(f"the classification is for {data['stage']!r}, not {stage}")
    rows = data["blocks"]
    if not isinstance(rows, list):
        raise usage_error('"blocks" must be a list')
    known = {b.key for b in blocks_of(pkg.doc(stage))}
    out: dict[str, str | None] = {}
    for row in rows:
        if not isinstance(row, dict) or not set(row) <= _VERDICT_KEYS or not isinstance(row.get("block"), str):
            raise usage_error('each verdict is {"block": KEY, "adds": TEXT or null}')
        adds = row.get("adds")
        if adds is not None and not isinstance(adds, str):
            raise usage_error(f'"adds" of {row["block"]} must be text or null')
        if row["block"] not in known:
            raise usage_error(f"{row['block']} is not a block of {stage}")
        out[row["block"]] = adds.strip() or None if adds is not None else None
    return out


def _load_record(pkg: Package, stage: str) -> dict[str, Any]:
    read = pkg.record_read(stage, "provenance")
    if read.error:
        raise refuse(Refusal("not-amendable", f"{stage} has a malformed provenance region: {read.error}", "Repair or remove it first"))
    record = read.obj if read.obj is not None else (adopt(pkg, stage) or {"version": 1, "blocks": {}})
    record.setdefault("blocks", {})
    return record


def _save_record(pkg: Package, stage: str, record: dict[str, Any]) -> None:
    try:
        pkg.write_record(stage, "provenance", record)
    except RegionError as exc:
        raise refuse(Refusal("not-amendable", f"cannot record in {stage}: {exc}", "Repair the document")) from exc


def classify(pkg: Package, stage: str, data: Any) -> dict[str, Any]:
    """Record, for each block of ``stage``, whether it restates settled sources, was decided by a person,
    or is inferred (and what it adds). The AI supplies only ``adds``; every other fact is decided here."""
    verdicts = _check_classification(pkg, stage, data)
    record = _load_record(pkg, stage)
    hashes = pkg.current_item_hashes()
    parsed = _all_parsed(pkg)
    entries = record["blocks"]
    for block in blocks_of(pkg.doc(stage)):
        old = entries.get(block.key) if isinstance(entries.get(block.key), dict) else None
        if stage in APPROVABLE and old is not None and old.get("class") == "adopted" and old.get("hash") == block.hash:
            continue
        if block.key not in verdicts and not block.numbered:
            continue
        same = old is not None and old.get("hash") == block.hash
        decided = block.item.decided if block.item is not None else None
        if decided and decided_eligible(pkg, decided, parsed, block.item) is None:
            entries[block.key] = {"hash": block.hash, "class": "decided", "basis": f"decided: {decided}"}
            continue
        adds = verdicts.get(block.key)
        if not adds and same and old.get("class") == "inferred":
            adds = old.get("adds")
        cited = [t for t in block.traces if _ID.match(t)]
        if block.key in verdicts and not adds and cited and all(source_settled(pkg, t) for t in cited):
            entries[block.key] = {"hash": block.hash, "class": "restated", "cites": {t: hashes[t] for t in cited if t in hashes}}
            continue
        entry: dict[str, Any] = {"hash": block.hash, "class": "inferred"}
        if adds:
            entry["adds"] = adds
        if same and old.get("class") == "inferred":
            for name in ("reviewed", "sources"):
                if name in old:
                    entry[name] = old[name]
        entries[block.key] = entry
    _save_record(pkg, stage, record)
    counts: dict[str, int] = {}
    for entry in entries.values():
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1
    listing = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    return {"ok": True, "stage": stage, "classes": counts, "text": f"Classified {stage}: {listing}."}


def reclassify(pkg: Package, stage: str, key: str, by: str, reason: str | None = None) -> dict[str, Any]:
    """Anyone may add scrutiny: turn a restated block into an inferred one, recorded with their name."""
    if not any(b.key == key for b in blocks_of(pkg.doc(stage))):
        raise refuse(Refusal("unknown-item", f"{key} is not a block of {stage}", "Use a key from `eil blocks list`"))
    record = _load_record(pkg, stage)
    entry = record["blocks"].get(key)
    if not isinstance(entry, dict) or entry.get("class") != "restated":
        raise refuse(Refusal("not-restated", f"{key} is not a restated block of {stage}", "Only restated blocks can be reclassified"))
    note = f"reclassified by {by.strip()}" + (f": {reason.strip()}" if reason and reason.strip() else "")
    record["blocks"][key] = {"hash": entry["hash"], "class": "inferred", "adds": note}
    _save_record(pkg, stage, record)
    return {"ok": True, "stage": stage, "block": key, "text": f"{key} is now inferred and needs review."}


__all__ = [
    "decided_eligible", "decided_findings", "amend", "start", "accept", "finish",
    "classify", "reclassify",
]  # fmt: skip

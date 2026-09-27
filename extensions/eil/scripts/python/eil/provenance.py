"""Human-decided provenance: the ``(decided: ID)`` clause, and ``eil amend`` (D-24, D-25).

Text that is a human's own words, copied verbatim from a decision they already made — an accepted
challenge, a resolved open question, or a clarify answer — carries ``(decided: ID)`` instead of
``[ai-draft]``. This module checks that the citation is real and in an eligible state; it cannot,
and does not try to, check that the marked text is a faithful transcription of what the human said
(Principle II: detectable, not tamper-proof). It also provides ``amend``, which re-signs a stage's
approval when every change since it is covered by such a citation, in place of a full re-approval.
"""

from __future__ import annotations

from typing import Any

from . import impact
from .artifacts import scan_document
from .blocks import write_region
from .clock import utc_now
from .comprehension import ELIGIBLE_STAGES
from .comprehension import counts as comprehension_counts
from .fingerprint import fingerprint_text
from .gates import ai_draft_lines
from .identity import Config, confirmer_refusal, is_ai_actor
from .package import APPROVABLE, STAGES, Package
from .records import DEFINITION_STAGES, approvers_for
from .results import Finding, Refusal, refuse, usage_error
from .trace import Item, ParseResult, item_hash, non_item_fingerprint, parse_document

DECIDED_KINDS = ("CH", "OQ", "AIS")


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


def decided_eligible(
    pkg: Package, decided_id: str, parsed: dict[str, ParseResult] | None = None
) -> str | None:
    """Why ``decided_id`` cannot back a ``(decided: ...)`` clause or ``eil amend --from``, or ``None``."""
    kind = decided_id.split("-")[0]
    if kind not in DECIDED_KINDS:
        return f"{decided_id!r} is not a CH-###, OQ-### or AIS-### id"
    if kind == "CH":
        found, response = _challenge_response(pkg, decided_id)
        if not found:
            return f"{decided_id} is not a challenge of this story"
        if response != "accepted":
            return f"{decided_id} is not accepted (it is {response or 'open'})"
        return None
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


# ---- eil amend (D-25)


def amend(
    pkg: Package, config: Config, stage: str, from_ids: list[str], by: str, attestation: str
) -> dict[str, Any]:
    """Re-sign ``stage``'s approval, or refuse and write nothing.

    Succeeds only when every item that changed since the last approval carries a ``(decided: ID)``
    clause naming one of ``from_ids``, no ``[ai-draft]`` tag remains, and nothing outside an item
    changed either (``non_item_fingerprint``). Anything else needs the full ``/speckit-eil-approve``.
    """
    if not from_ids:
        raise usage_error("amend needs at least one --from id")
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
                "Amend re-signs an existing approval; a first approval is /speckit-eil-approve",
            )
        )

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

    for decided_id in from_ids:
        problem = decided_eligible(pkg, decided_id, all_parsed)
        if problem:
            refusals.append(
                Refusal(
                    "unknown-item",
                    problem,
                    "Cite an accepted challenge, a resolved open question or an AIS clarify answer",
                )
            )

    prose_now = non_item_fingerprint(doc, parsed.items, doc.records())
    prose_then = state.approval.get("prose_fingerprint")
    if prose_then is None:
        refusals.append(
            Refusal(
                "amend-not-covered",
                "the last approval predates eil amend and carries no prose_fingerprint to compare",
                "Approve the stage fully once with /speckit-eil-approve to enable amendments after it",
            )
        )
    elif prose_then != prose_now:
        refusals.append(
            Refusal(
                "amend-not-covered",
                "text outside an item changed since the last approval (a heading, prose, or a diagram)",
                "A (decided: ...) clause only covers an item; run the full /speckit-eil-approve",
            )
        )

    changed = [i for i in impact.changed_items(pkg, all_parsed) if _stage_of(all_parsed, i) == stage]
    uncovered = []
    for item_id in changed:
        item = _item_by_id(all_parsed, item_id)
        if item is None or item.decided is None or item.decided not in from_ids:
            uncovered.append(item_id)
    if uncovered:
        refusals.append(
            Refusal(
                "amend-not-covered",
                f"changed since the last approval with no matching (decided: ...) among {from_ids}: "
                f"{', '.join(uncovered)}",
                "Cite every human decision that covers a change, or run the full /speckit-eil-approve",
            )
        )
    if refusals:
        raise refuse(*refusals)

    fingerprint = fingerprint_text(text)
    record: dict[str, Any] = {
        "stage": stage,
        "by": by.strip(),
        "at": utc_now(),
        "fingerprint": fingerprint,
        "attestation": attestation.strip(),
        "amended": True,
        "amends": list(from_ids),
    }
    record["upstream"] = {
        earlier: fp
        for earlier in DEFINITION_STAGES
        if STAGES.index(earlier) < STAGES.index(stage) and (fp := pkg.fingerprint(earlier))
    }
    record["items"] = {item.id: item_hash(item) for item in parsed.items}
    record["prose_fingerprint"] = prose_now
    record["upstream_items"] = impact.upstream_item_hashes(pkg, stage, all_parsed)
    record["overrides_used"] = list(state.approval.get("overrides_used") or [])
    if stage in ELIGIBLE_STAGES:
        record["comprehension"] = comprehension_counts(doc.read_region("comprehension").obj or {})
    pkg.doc_path(stage).write_bytes(write_region(text, "approval", record).encode("utf-8"))
    return {
        "ok": True,
        "stage": stage,
        "approval": record,
        "text": f"Amended {stage} as {record['by']} at {record['at']}, from {', '.join(from_ids)}.",
    }


__all__ = ["decided_eligible", "decided_findings", "amend"]

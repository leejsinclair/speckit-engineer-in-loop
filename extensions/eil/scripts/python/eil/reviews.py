"""The one-reply review list (contracts/cli.md `review list` and `review answer`; research D-36, FR-048, FR-050).

A review list is computed, never stored: the entries a person is asked about, with a digest that changes
whenever any entry would change. A reply is stored, word for word, as an acceptance in the stage's
provenance region. The AI never records a reply, and the helper refuses only the recognisable mismatches
between the words and the flags; the rest is an attestation limit printed with every list.

Each list kind registers a ``KindSpec`` in ``KINDS``: how to build its entries, and what settling or
reopening an entry writes. This module supplies the core and the ``inferred`` kind.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from . import clock
from .blocks import RegionError
from .blockstatus import DERIVED, NEEDS_REVIEW, SETTLED, UNKNOWN_CURRENCY, adopt, block_statuses
from .content import blocks_of
from .evidence import LIMIT as EVIDENCE_LIMIT
from .identity import Config, confirmer_refusal, is_ai_actor, normalise_person
from .package import STAGES
from .results import Refusal, refuse, usage_error

if TYPE_CHECKING:
    from .package import Package

REPLY_LIMIT = (
    "Your reply is recorded word for word; the helper checks only obvious mismatches between it and "
    "what is recorded as accepted."
)
FIDELITY_LIMIT = (
    "Restated content is checked against its source by hash; the check cannot prove two wordings mean "
    "the same (FR-014)."
)
CORRECTION_LIMIT = "Correction wording is recorded as given; the tool cannot tell who wrote it."

_AI_DRAFT = re.compile(r"\s*\[ai-draft\]")
_ALL_PHRASE = re.compile(
    r"^(?:ok(?:ay)?|yes|yep|yeah|approved?|accepted?|lgtm|agreed?|fine|good|looks good|all good|sounds good)"
    r"(?:\s+(?:to|for|with)\s+all|\s+all)?\s*[.!]*$",
    re.IGNORECASE,
)


@dataclass
class ListEntry:
    key: str
    hash: str
    what: str
    why: str = ""
    ai_view: str | None = None
    severity: str | None = None
    covered_by: str | None = None
    correction: str | None = None
    conflict: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"key": self.key, "what": self.what, "why": self.why}
        for name in ("ai_view", "severity", "covered_by", "correction"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.conflict:
            out["conflict"] = True
        return {**out, **self.extra}


@dataclass
class ReviewList:
    kind: str
    stage: str
    purpose: str
    entries: list[ListEntry]
    limits: list[str]

    @property
    def digest(self) -> str:
        pairs = sorted(f"{e.key}|{e.hash}" for e in self.entries)
        return "sha256:" + hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "stage": self.stage,
            "purpose": self.purpose,
            "entries": [e.to_json() for e in self.entries],
            "digest": self.digest,
            "limits": self.limits,
        }


@dataclass
class Act:
    """One answer being recorded, handed to a kind's hooks."""

    id: str
    by: str
    at: str
    reply: str
    summaries: dict[str, str]
    reason: str | None = None


Hook = Callable[["Package", str, dict[str, Any], dict[str, str], Act], None]


@dataclass
class KindSpec:
    purpose: str
    build: Callable[[Package, str], list[ListEntry]]
    settle: Hook | None = None
    reopen: Hook | None = None
    settled: Callable[[Package, str], dict[str, str]] | None = None
    defers: bool = False
    limits: tuple[str, ...] = ()
    rework_first: bool = False
    stages: tuple[str, ...] = ()


def _refuse(code: str, message: str, fix: str = "") -> Any:
    return refuse(Refusal(code, message, fix))


# ---- the inferred kind


def _record_blocks(package: Package, stage: str) -> dict[str, Any]:
    obj = package.record(stage, "provenance")
    blocks = (obj or {}).get("blocks")
    return blocks if isinstance(blocks, dict) else {}


def _build_inferred(package: Package, stage: str) -> list[ListEntry]:
    from . import corrections

    recorded = _record_blocks(package, stage)
    under = {
        k: str(cr["id"])
        for _, cr in corrections.open_all(package)
        for k in corrections.under_open_correction(package, stage)
        if cr.get("item") == k
    }
    entries = []
    for key, info in block_statuses(package).get(stage, {}).items():
        if info.status != NEEDS_REVIEW:
            continue
        entry = recorded.get(key) if isinstance(recorded.get(key), dict) else None
        if entry is None:
            why = "no record that a person has reviewed it"
        elif entry.get("reviewed"):
            why = "changed since it was reviewed"
        elif entry.get("adds"):
            why = f"adds {entry['adds']}"
        else:
            why = "inferred; not yet reviewed"
        entries.append(
            ListEntry(
                key,
                info.block.hash,
                _AI_DRAFT.sub("", info.block.text),
                why,
                correction=f"under open correction {under[key]}" if key in under else None,
            )
        )
    return entries


def _settle_inferred(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    blocks = blocks_of(package.doc(stage))
    by_key = {b.key: b for b in blocks}
    current = package.current_item_hashes()
    for key, digest in hashes.items():
        entry = dict(record["blocks"].get(key) or {})
        entry.update(hash=digest, reviewed={"by": act.by, "at": act.at, "list": act.id, "reply": act.reply})
        entry["class"] = entry.get("class") if entry.get("class") in ("restated", "inferred") else "inferred"
        entry.pop("basis", None)
        block = by_key.get(key)
        if stage in DERIVED and block is not None and block.traces:
            entry["sources"] = {i: current[i] for i in block.traces if i in current}
        record["blocks"][key] = entry


def _reopen_inferred(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    for key in hashes:
        entry = record["blocks"].get(key)
        if isinstance(entry, dict):
            entry.pop("reviewed", None)
            entry.pop("basis", None)
            if entry.get("class") == "adopted":
                entry["class"] = "inferred"


def _settled_inferred(package: Package, stage: str) -> dict[str, str]:
    recorded = _record_blocks(package, stage)
    out = {}
    for key, info in block_statuses(package).get(stage, {}).items():
        entry = recorded.get(key)
        if info.status == SETTLED and isinstance(entry, dict) and (
            entry.get("reviewed") or entry.get("class") == "adopted"
        ):
            out[key] = info.block.hash
    return out


# ---- the unknown-currency, tasks and evidence kinds (FR-005, FR-006, FR-008, D-34)


def _mix(block_hash: str, parts: list[str]) -> str:
    return "sha256:" + hashlib.sha256("\n".join([block_hash, *parts]).encode("utf-8")).hexdigest()


def _moved(recorded: Any, current: dict[str, str]) -> list[str]:
    return sorted(i for i, h in (recorded or {}).items() if current.get(i) != h)


def _build_unknown_currency(package: Package, stage: str) -> list[ListEntry]:
    return [
        ListEntry(key, info.block.hash, info.block.text, "no record of the versions of its sources")
        for key, info in block_statuses(package).get(stage, {}).items()
        if info.status == UNKNOWN_CURRENCY
    ]


def _settle_unknown_currency(
    package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act
) -> None:
    from . import staleness

    by_key = {b.key: b for b in blocks_of(package.doc(stage))}
    current = package.current_item_hashes()
    for key in hashes:
        entry, block = record["blocks"].get(key), by_key.get(key)
        if not isinstance(entry, dict) or block is None:
            continue
        entry["sources"] = {i: current[i] for i in block.traces if i in current}
        if stage == "tasks" and staleness.is_ticked(block) and "completed_against" not in entry:
            entry["completed_against"] = staleness.task_closure(package, key)
            entry["blocked_at_completion"] = False


def _build_tasks(package: Package, stage: str) -> list[ListEntry]:
    from . import staleness

    if stage != "tasks":
        return []
    recorded, current = _record_blocks(package, stage), package.current_item_hashes()
    entries = []
    for block in blocks_of(package.doc(stage)):
        entry = recorded.get(block.key)
        if block.kind != "task" or not staleness.is_ticked(block) or not isinstance(entry, dict):
            continue
        done = entry.get("completed_against")
        if not isinstance(done, dict):
            continue
        moved = _moved(done, current)
        if moved:
            why = f"{', '.join(moved)} changed since this task was completed"
        elif not done:
            why = "reopened and still ticked"
        elif entry.get("blocked_at_completion"):
            why = "completed while blocked"
        else:
            continue
        parts = [f"{i}:{current.get(i, '')}" for i in moved] + ["reopened"] * (not done) + ["blocked"] * bool(
            entry.get("blocked_at_completion")
        )
        entries.append(ListEntry(block.key, _mix(block.hash, parts), block.text, why))
    return entries


def _settle_tasks(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    from . import staleness

    for key in hashes:
        entry = record["blocks"].get(key)
        if isinstance(entry, dict):
            entry["completed_against"] = staleness.task_closure(package, key)
            entry["blocked_at_completion"] = False


def _reopen_tasks(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    for key in hashes:
        entry = record["blocks"].get(key)
        if isinstance(entry, dict) and "completed_against" in entry:
            entry["completed_against"] = {}
            entry["blocked_at_completion"] = False


def _settled_tasks(package: Package, stage: str) -> dict[str, str]:
    from . import staleness

    recorded, current = _record_blocks(package, stage), package.current_item_hashes()
    out = {}
    for block in blocks_of(package.doc(stage)):
        entry = recorded.get(block.key)
        done = entry.get("completed_against") if isinstance(entry, dict) else None
        if block.kind == "task" and staleness.is_ticked(block) and done and not _moved(done, current):
            out[block.key] = block.hash
    return out


def _build_evidence(package: Package, stage: str) -> list[ListEntry]:
    if stage != "verification":
        return []
    from . import evidence

    recorded, current = _record_blocks(package, stage), package.current_item_hashes()
    confirmed = evidence.confirmed_rows(package)
    entries = []
    for block in blocks_of(package.doc(stage)):
        entry = recorded.get(block.key)
        if block.kind != "item" or not block.key.startswith("EVD-") or not isinstance(entry, dict):
            continue
        moved = _moved(entry.get("sources"), current)
        if moved and block.key not in confirmed:
            entries.append(
                ListEntry(
                    block.key,
                    _mix(block.hash, [f"{i}:{current.get(i, '')}" for i in moved]),
                    block.text,
                    f"{', '.join(moved)} changed since this evidence was recorded",
                    extra={"confirmed": False},
                )
            )
    return entries


def _settle_evidence(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    by_key = {b.key: b for b in blocks_of(package.doc(stage))}
    current = package.current_item_hashes()
    for key in hashes:
        entry, block = record["blocks"].get(key), by_key.get(key)
        if isinstance(entry, dict) and block is not None:
            entry["sources"] = {i: current[i] for i in block.traces if i in current}


def _reopen_evidence(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    for key in hashes:
        entry = record["blocks"].get(key)
        if isinstance(entry, dict) and isinstance(entry.get("sources"), dict):
            entry["sources"] = {i: "sha256:" + "0" * 64 for i in entry["sources"]}


def _settled_evidence(package: Package, stage: str) -> dict[str, str]:
    if stage != "verification":
        return {}
    recorded, current = _record_blocks(package, stage), package.current_item_hashes()
    return {
        b.key: b.hash
        for b in blocks_of(package.doc(stage))
        if b.key.startswith("EVD-")
        and isinstance(recorded.get(b.key), dict)
        and recorded[b.key].get("sources")
        and not _moved(recorded[b.key]["sources"], current)
    }


# ---- the changes kind: what changed in an approved stage, covered or not (FR-015 to FR-018, D-37)


def _answers(package: Package, stage: str) -> dict[tuple[str, str], tuple[bool, str]]:
    """``{(key, hash): (settling?, acceptance id)}``: the latest word on each change, whoever gave it.

    An answer on the ``inferred`` list counts too: the person already saw this content at this hash (D-45).
    """
    obj = package.record(stage, "provenance")
    latest: dict[tuple[str, str], tuple[bool, str]] = {}
    for acc in (obj or {}).get("acceptances") or []:
        if not isinstance(acc, dict) or acc.get("kind") not in ("changes", "inferred"):
            continue
        for key, settling in _dispositions(acc).items():
            digest = (acc.get("hashes") or {}).get(key)
            if digest:
                latest[(key, digest)] = (settling, acc["id"])
    return latest


def answered_changes(package: Package, stage: str) -> dict[str, tuple[str, str]]:
    """``{key: (hash, acceptance id)}`` for changes whose current content a person accepted."""
    from .provenance import change_rows

    answers = _answers(package, stage)
    out = {}
    for row in change_rows(package, stage):
        found = answers.get((row.id, row.hash))
        if found and found[0]:
            out[row.id] = (row.hash, found[1])
    return out


def _build_changes(package: Package, stage: str) -> list[ListEntry]:
    from .provenance import change_rows

    answered = answered_changes(package, stage)
    inferred = {i.key for i in block_statuses(package).get(stage, {}).values() if i.status == NEEDS_REVIEW}
    entries = []
    for row in change_rows(package, stage):
        if row.id in answered:
            continue
        what = _AI_DRAFT.sub("", row.item.text) if row.item else f"{row.id} was removed"
        entry = ListEntry(row.id, row.hash, what, row.why, covered_by=row.covered_by)
        if row.covered_by is None and row.id in inferred:
            entry.extra["inferred"] = True
        entries.append(entry)
    return entries


def _settle_changes(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    by_key = {i.key: i for i in block_statuses(package).get(stage, {}).values() if i.status == NEEDS_REVIEW}
    _settle_inferred(package, stage, record, {k: by_key[k].block.hash for k in hashes if k in by_key}, act)


def _settled_changes(package: Package, stage: str) -> dict[str, str]:
    return {key: digest for key, (digest, _) in answered_changes(package, stage).items()}


# ---- the unsettled-challenges kind: a rejected or deferred challenge whose target changed since (FR-030)


def _challenge_entries(package: Package, stage: str) -> list[tuple[Any, dict[str, Any]]]:
    return [
        (r, r.obj)
        for r in package.doc(stage).records()
        if r.kind == "challenge" and isinstance(r.obj, dict) and r.obj.get("status") == "closed"
        and r.obj.get("response") in ("rejected", "deferred")
    ]


def _accepted_challenge_hashes(package: Package, stage: str, kind: str = "unsettled-challenges") -> dict[str, str]:
    obj = package.record(stage, "provenance")
    latest: dict[str, str] = {}
    for acc in (obj or {}).get("acceptances") or []:
        if not isinstance(acc, dict) or acc.get("kind") != kind:
            continue
        for key, settling in _dispositions(acc).items():
            digest = (acc.get("hashes") or {}).get(key)
            if settling and digest:
                latest[key] = digest
            elif not settling:
                latest.pop(key, None)
    return latest


def _unsettled_rows(package: Package, stage: str) -> list[tuple[str, str, dict[str, Any]]]:
    obj = package.record(stage, "provenance")
    changed = {}
    for c in (obj or {}).get("changes") or []:
        if isinstance(c, dict):
            changed.setdefault(str(c.get("item")), []).append(str(c.get("at", "")))
    current = package.current_item_hashes()
    rows = []
    for _, ch in _challenge_entries(package, stage):
        target, answered_at = str(ch.get("target", "")), str(ch.get("at", ""))
        if any(at >= answered_at for at in changed.get(target, [])):
            rows.append((str(ch["id"]), _mix(str(ch["id"]), [target, current.get(target, "")]), ch))
    return rows


def _build_unsettled(package: Package, stage: str) -> list[ListEntry]:
    accepted = _accepted_challenge_hashes(package, stage)
    return [
        ListEntry(
            key,
            digest,
            f"{ch.get('text', '')} ({ch['response']} by {ch.get('responder', '?')}: {ch.get('reason', '')})",
            f"{ch.get('target')} changed after this challenge was {ch['response']}",
        )
        for key, digest, ch in _unsettled_rows(package, stage)
        if accepted.get(key) != digest
    ]


def _settled_unsettled(package: Package, stage: str) -> dict[str, str]:
    accepted = _accepted_challenge_hashes(package, stage)
    return {key: digest for key, digest, _ in _unsettled_rows(package, stage) if accepted.get(key) == digest}


def _reopen_unsettled(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    from .blocks import replace_record

    for key in hashes:
        for rec, ch in _challenge_entries(package, stage):
            if ch.get("id") == key:
                current = {k: v for k, v in ch.items() if k not in ("responder", "response", "at", "reason", "responses")}
                current["status"] = "open"
                package.doc_path(stage).write_bytes(replace_record(package.read(stage), rec, current).encode("utf-8"))
                break


# ---- the low-challenges kind: every open low challenge, deferred together at completion (FR-040)


def _low_rows(package: Package, stage: str) -> list[tuple[str, Any, dict[str, Any]]]:
    from .records import challenge_severity

    stages = package.existing_stages() if stage == "completion" else [stage]
    return [
        (owner, rec, rec.obj)
        for owner in stages
        for rec in package.doc(owner).records()
        if rec.kind == "challenge" and isinstance(rec.obj, dict) and rec.obj.get("id")
        and rec.obj.get("status", "open") != "closed" and challenge_severity(rec.obj) == "low"
    ]  # fmt: skip


def _build_low_challenges(package: Package, stage: str) -> list[ListEntry]:
    return [
        ListEntry(
            str(ch["id"]),
            _mix(str(ch["id"]), [str(ch.get("target", "")), str(ch.get("text", ""))]),
            str(ch.get("text", "")),
            f"raised on {ch.get('target', '?')} in {owner} by {ch.get('raised_by', '?')}",
            severity="low",
            extra={"stage": owner, "target": ch.get("target")},
        )
        for owner, _, ch in _low_rows(package, stage)
    ]


def _settle_low_challenges(
    package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act
) -> None:
    from .blocks import replace_record

    for key in hashes:
        for owner, rec, ch in _low_rows(package, stage):
            if ch["id"] != key:
                continue
            closed = {k: v for k, v in ch.items() if k not in ("responder", "response", "at", "reason", "responses")}
            closed.update(
                status="closed", response="deferred", responder=act.by, at=act.at, reason=act.reason or "",
                deferred_in=act.id,
            )  # fmt: skip
            package.doc_path(owner).write_bytes(replace_record(package.read(owner), rec, closed).encode("utf-8"))
            break


# ---- the diagram-currency kind: artefacts implementation touched (FR-033)


def _currency_rows(package: Package, stage: str) -> dict[str, tuple[str, str]]:
    from . import staleness

    if stage != "completion":
        return {}
    current = package.current_item_hashes()
    return {art: (_mix(art, [current.get(art, ""), why]), why) for art, why in staleness.touched_artifacts(package).items()}


def _build_diagram_currency(package: Package, stage: str) -> list[ListEntry]:
    accepted = _accepted_challenge_hashes(package, stage, "diagram-currency")
    by_key = {b.key: b for b in package_items(package)}
    return [
        ListEntry(art, digest, by_key[art].text if art in by_key else art, why)
        for art, (digest, why) in _currency_rows(package, stage).items()
        if accepted.get(art) != digest
    ]


def _settled_diagram_currency(package: Package, stage: str) -> dict[str, str]:
    accepted = _accepted_challenge_hashes(package, stage, "diagram-currency")
    return {art: digest for art, (digest, _) in _currency_rows(package, stage).items() if accepted.get(art) == digest}


def package_items(package: Package) -> list[Any]:
    return [b for s in package.existing_stages() for b in blocks_of(package.doc(s)) if b.numbered]


KINDS: dict[str, KindSpec] = {
    "changes": KindSpec("revalidation", _build_changes, _settle_changes, None, _settled_changes),
    "inferred": KindSpec(
        "validation",
        _build_inferred,
        _settle_inferred,
        _reopen_inferred,
        _settled_inferred,
        limits=(FIDELITY_LIMIT,),
    ),
    "tasks": KindSpec(
        "revalidation", _build_tasks, _settle_tasks, _reopen_tasks, _settled_tasks, rework_first=True
    ),
    "evidence": KindSpec(
        "revalidation", _build_evidence, _settle_evidence, _reopen_evidence, _settled_evidence, limits=(EVIDENCE_LIMIT,)
    ),
    "low-challenges": KindSpec("decision", _build_low_challenges, _settle_low_challenges, defers=True),
    "diagram-currency": KindSpec(
        "validation", _build_diagram_currency, None, None, _settled_diagram_currency, stages=("completion",)
    ),
    "unknown-currency": KindSpec("awareness", _build_unknown_currency, _settle_unknown_currency),
    "unsettled-challenges": KindSpec(
        "revalidation", _build_unsettled, None, _reopen_unsettled, _settled_unsettled
    ),
}


# ---- building a list


def _check_stage(package: Package, stage: str) -> None:
    if stage not in STAGES or not package.exists(stage):
        raise _refuse("unknown-stage", f"{stage!r} has no document in this story", f"Use one of: {', '.join(STAGES)}")


def _spec(kind: str) -> KindSpec:
    spec = KINDS.get(kind)
    if spec is None:
        raise _refuse("unknown-item", f"no review list of kind {kind!r} is available", f"Use one of: {', '.join(KINDS)}")
    return spec


def build_list(package: Package, stage: str, kind: str, views: dict[str, str] | None = None) -> ReviewList:
    spec = _spec(kind)
    _check_stage(package, stage)
    entries = spec.build(package, stage)
    conflicted = conflicted_keys(package, stage, {e.key: e.hash for e in entries} if kind == "changes" else None)
    for entry in entries:
        if entry.key in (views or {}):
            entry.ai_view = f"AI assessment: {views[entry.key]}"  # type: ignore[index]
        entry.conflict = entry.key in conflicted
    if spec.rework_first:
        entries.sort(key=lambda e: bool(e.ai_view) and _looks_valid(e.ai_view))
    limits = [*spec.limits, REPLY_LIMIT]
    if any((e.covered_by or "").startswith("CR-") or e.correction for e in entries):
        limits.append(CORRECTION_LIMIT)
    return ReviewList(kind, stage, spec.purpose, entries, limits)


def _looks_valid(view: str) -> bool:
    return bool(re.match(r"AI assessment:\s*(still\s+)?(valid|fine|ok)", view, re.IGNORECASE))


def conflicted_keys(package: Package, stage: str, extra: dict[str, str] | None = None) -> set[str]:
    """Entries of ``stage`` whose recorded answers conflict at their current content (FR-050)."""
    if not package.exists(stage):
        return set()
    obj = package.record(stage, "provenance")
    rows = (obj or {}).get("conflicts") or []
    if not rows:
        return set()
    current = {b.key: b.hash for b in blocks_of(package.doc(stage))}
    current.update(extra or {})
    return {r["key"] for r in rows if isinstance(r, dict) and current.get(r.get("key")) == r.get("hash")}


# ---- answering


def _next_id(package: Package) -> str:
    from .provenance import _highest_review_number

    return f"RVW-{_highest_review_number(package) + 1:03d}"


def _names(reply: str, keys: list[str]) -> bool:
    return any(re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", reply, re.IGNORECASE) for k in keys)


def _dispositions(acceptance: dict[str, Any]) -> dict[str, bool]:
    """``{key: settling?}`` for the entries an acceptance names."""
    out = {k: True for k in (*acceptance.get("accepted", []), *acceptance.get("deferred", []))}
    out.update({k: False for k in (*acceptance.get("except", []), *acceptance.get("questioned", []), *acceptance.get("reopened", []))})
    return out


def _update_conflicts(
    record: dict[str, Any], acc: dict[str, Any], resolving: bool
) -> tuple[list[dict[str, Any]], bool]:
    rows = [dict(r) for r in record.get("conflicts") or []]
    resolved = False
    for key, settling in _dispositions(acc).items():
        digest = acc["hashes"].get(key)
        latest: dict[str, tuple[bool, str]] = {}
        for prior in record.get("acceptances") or []:
            if prior.get("hashes", {}).get(key) == digest and key in _dispositions(prior):
                latest[normalise_person(prior["by"])] = (_dispositions(prior)[key], prior["id"])
        latest[normalise_person(acc["by"])] = (settling, acc["id"])
        existing = next((r for r in rows if r["key"] == key and r["hash"] == digest), None)
        if existing is not None and resolving:
            rows.remove(existing)
            resolved = True
            continue
        opposed = len({s for s, _ in latest.values()}) > 1
        answers = sorted({i for _, i in latest.values()})
        if existing is not None:
            existing["answers"] = sorted({*existing["answers"], acc["id"]})
        elif opposed:
            rows.append({"key": key, "hash": digest, "answers": answers})
    return rows, resolved


def answer(
    package: Package,
    config: Config,
    stage: str,
    kind: str,
    *,
    digest: str | None,
    by: str,
    reply: str,
    all_: bool = False,
    all_except: list[str] | None = None,
    question: list[str] | None = None,
    reopen: list[str] | None = None,
    defer_reason: str | None = None,
    summaries: dict[str, str] | None = None,
) -> dict[str, Any]:
    from .records import approvers_for

    spec = _spec(kind)
    _check_stage(package, stage)
    modes = [all_, all_except is not None, bool(question), bool(reopen)]
    if sum(modes) != 1:
        raise usage_error("give exactly one of --all, --all-except, --question, --reopen")
    settling = all_ or all_except is not None
    listed = build_list(package, stage, kind)
    on_list = {e.key: e for e in listed.entries}
    settled = spec.settled(package, stage) if spec.settled else {}
    refusals: list[Refusal] = []

    def add(code: str, message: str, fix: str = "") -> None:
        refusals.append(Refusal(code, message, fix))

    if is_ai_actor(by):
        add("ai-approval", f"{by!r} is the AI; only a person may answer a review list", "Ask the developer to reply")
    if not reply.strip():
        add("reply-required", "a reply needs the person's own words", "Ask the person and pass their words with --reply")
    if settling and not digest:
        add("digest-required", "a settling answer must name the list the person saw", "Pass --digest from `review list`")
    elif digest and digest != listed.digest:
        add("list-changed", "the list changed since the person saw it", "Run `review list` again and show it")
    confirmer = confirmer_refusal(by, approvers_for(package, config, stage), stage) is None
    if settling and not confirmer and not is_ai_actor(by):
        add("not-a-confirmer", f"{by!r} is not configured to confirm {stage}", "Ask a configured confirmer")
    if settling and spec.defers and not (defer_reason or "").strip():
        add("reason-required", "a deferral needs a reason", "Pass --defer-reason")
    named = list(all_except or []) + list(question or []) + list(reopen or [])
    for key in named:
        allowed = key in on_list or (not settling and key in settled)
        if not allowed:
            add("unknown-item", f"{key} is not on this list or settled for {stage}", "Name an entry from `review list`")
    if reply.strip():
        if all_ and _names(reply, list(on_list)):
            add("reply-mismatch", "--all was given but the reply names an entry", "Use --all-except, or reword the reply")
        elif not all_ and _ALL_PHRASE.match(reply.strip()):
            add("reply-mismatch", "the reply says yes to everything but the flags do not", "Use --all, or reword the reply")
    if refusals:
        seen: dict[tuple[str, str], Refusal] = {(r.code, r.message): r for r in refusals}
        raise refuse(*seen.values())

    read = package.record_read(stage, "provenance")
    if read.error:
        raise _refuse("not-amendable", f"{stage} has a malformed provenance region: {read.error}", "Repair or remove it first")
    record = read.obj if read.obj is not None else (adopt(package, stage) or {"version": 1, "blocks": {}})
    record.setdefault("blocks", {})

    excepted = list(all_except or [])
    accepted = [k for k in on_list if k not in excepted] if settling else []
    hashes = {k: (on_list[k].hash if k in on_list else settled[k]) for k in named + accepted}
    deferring = settling and spec.defers
    act = Act(_next_id(package), by, clock.utc_now(), reply, summaries or {}, (defer_reason or "").strip() or None)
    acc: dict[str, Any] = {
        "id": act.id, "stage": stage, "kind": kind, "digest": digest, "by": by, "at": act.at, "reply": reply,
        "accepted": [] if deferring else accepted, "except": excepted, "questioned": list(question or []),
        "reopened": list(reopen or []), "reason": act.reason, "hashes": hashes,
    }  # fmt: skip
    if deferring:
        acc["deferred"] = accepted
    if summaries:
        acc["summaries"] = {k: v.strip() for k, v in summaries.items() if k in hashes and v.strip()}
    if spec.settle and accepted:
        spec.settle(package, stage, record, {k: hashes[k] for k in accepted}, act)
    undone = {k: hashes[k] for k in (*excepted, *(reopen or []))}
    if spec.reopen and undone:
        spec.reopen(package, stage, record, undone, act)

    rows, resolved = _update_conflicts(record, acc, confirmer and settling)
    if resolved:
        acc["resolved_conflict"] = True
    record.setdefault("acceptances", []).append(acc)
    if rows or "conflicts" in record:
        record["conflicts"] = rows
    try:
        package.write_record(stage, "provenance", record)
    except RegionError as exc:
        raise _refuse("not-amendable", f"cannot record the answer in {stage}: {exc}", "Repair the document") from exc
    conflicts = sorted({r["key"] for r in rows if r["key"] in hashes})
    lines = [f"Recorded {act.id} by {by}: {len(accepted)} accepted, {len(excepted)} excepted."]
    if conflicts:
        lines.append("In conflict: " + ", ".join(conflicts))
    return {
        "ok": True,
        "id": act.id,
        "stage": stage,
        "kind": kind,
        "accepted": acc["accepted"],
        "except": excepted,
        "questioned": acc["questioned"],
        "reopened": acc["reopened"],
        "deferred": acc.get("deferred", []),
        "conflicts": conflicts,
        "resolved_conflict": resolved,
        "text": "\n".join(lines),
    }


def confirm(
    package: Package, config: Config, stage: str, *, by: str, confirmation: str, summaries: dict[str, str] | None = None
) -> dict[str, Any]:
    """Bring an approved stage back once its changes are covered or answered (research D-37)."""
    from .provenance import confirm_changes

    return confirm_changes(package, config, stage, by, confirmation, summaries)

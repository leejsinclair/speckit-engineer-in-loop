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
from .trace import decision_fields, is_ai_decided

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


ONE_AT_A_TIME, SUMMARY = "one-at-a-time", "summary"
DEFAULT_THRESHOLD = 8
# Each of these sections is one entry on an inferred list, however many blocks it holds (FR-018).
SCAFFOLDING_SECTIONS = ("Actors", "Dependencies", "Not applicable", "Inputs", "Outputs")
SUMMARY_LIMIT = 120
_SUMMARY_PREFIX = re.compile(r"^\s*(?:[-*]\s+\[[ xX]\]\s+)?(?:\*\*[A-Z]{2,4}-\d{3,}\*\*:|T\d{3,})\s*")
_SUMMARY_CLAUSE = re.compile(r"\s*\((?:traces|decided|status|material|code|actor|store|accepted-by)[^)]*\)")
_SENTENCE = re.compile(r"(?<=[.!?])\s")


def summarise(text: str) -> str:
    """A deterministic one-line summary: an item's title, or the first sentence, at most 120
    characters. The AI writes no summary (D-51)."""
    first = next((line for line in text.splitlines() if line.strip() and not line.strip().startswith("```")), "")
    plain = _SUMMARY_CLAUSE.sub("", _SUMMARY_PREFIX.sub("", _AI_DRAFT.sub("", first))).strip()
    plain = _SENTENCE.split(plain, maxsplit=1)[0].strip()
    plain = " ".join(plain.split())
    return plain if len(plain) <= SUMMARY_LIMIT else plain[: SUMMARY_LIMIT - 1].rstrip() + "…"


def mode_for(count: int, threshold: int) -> str:
    return ONE_AT_A_TIME if count <= threshold else SUMMARY


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
    section: str = ""
    summary: str = ""
    members: dict[str, str] = field(default_factory=dict)  # a scaffolding entry's blocks: key to hash
    question: str = ""  # the helper's fixed question for this entry (004 D-64)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"key": self.key, "what": self.what, "why": self.why, "summary": self.summary}
        if self.question:
            out["question"] = self.question
        if self.section:
            out["section"] = self.section
        if self.members:
            out["members"] = list(self.members)
        for name in ("ai_view", "severity", "covered_by", "correction"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.conflict:
            out["conflict"] = True
        return {**out, **self.extra}


@dataclass
class ReviewList:
    """A list as presented. ``entries`` are what the person is asked about now; while a review session
    is open they are its unanswered entries, and ``all_entries`` is the whole list, which the digest,
    the mode and the answer checks always use."""

    kind: str
    stage: str
    purpose: str
    entries: list[ListEntry]
    limits: list[str]
    threshold: int = DEFAULT_THRESHOLD
    all_entries: list[ListEntry] | None = None
    session_mode: str | None = None
    session: dict[str, int] | None = None
    answers: list[dict[str, Any]] | None = None  # the open session's stored answers (004 D-72)
    last_answers: list[dict[str, Any]] | None = None  # send-backs and questions once it closed (D-72)

    @property
    def full(self) -> list[ListEntry]:
        return self.entries if self.all_entries is None else self.all_entries

    @property
    def digest(self) -> str:
        pairs = sorted(f"{e.key}|{e.hash}" for e in self.full)
        return "sha256:" + hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()

    @property
    def mode(self) -> str:
        return self.session_mode or mode_for(len(self.full), self.threshold)

    def groups(self) -> list[dict[str, Any]]:
        found: dict[str, list[str]] = {}
        for entry in self.entries:
            found.setdefault(entry.section, []).append(entry.key)
        return [{"section": name, "entries": keys} for name, keys in found.items()]

    def to_json(self) -> dict[str, Any]:
        out = {
            "kind": self.kind,
            "stage": self.stage,
            "purpose": self.purpose,
            "mode": self.mode,
            "threshold": self.threshold,
            "groups": self.groups(),
            "entries": [e.to_json() for e in self.entries],
            "digest": self.digest,
            "limits": self.limits,
        }
        if self.session is not None:
            out["session"] = self.session
        if self.answers is not None:
            out["answers"] = self.answers
        if self.last_answers:
            out["last_answers"] = self.last_answers
        return out


@dataclass
class Act:
    """One answer being recorded, handed to a kind's hooks."""

    id: str
    by: str
    at: str
    reply: str
    summaries: dict[str, str]
    reason: str | None = None
    marks: set[str] = field(default_factory=set)  # keys reopened by a comment: they get a ``reopened`` mark (004 D-65)
    comment: str | None = None
    via: str | None = None


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
    reopenable: Callable[[Package, str], dict[str, str]] | None = None  # wider than ``settled`` for --reopen


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
        elif isinstance(entry.get("reopened"), dict):
            mark = entry["reopened"]
            why = f"reopened by {mark.get('by')}: {mark.get('comment')}"
        elif entry.get("reviewed"):
            why = "changed since it was reviewed"
        elif entry.get("adds"):
            why = f"adds {entry['adds']}"
        else:
            why = "inferred; not yet reviewed"
        item = info.block.item
        ai_decided = item is not None and item.kind == "DEC" and is_ai_decided(decision_fields(item).get("owner"))
        entries.append(
            ListEntry(
                key,
                info.block.hash,
                _AI_DRAFT.sub("", info.block.text),
                f"AI-decided: {decision_fields(item).get('reason', '')}".strip() if ai_decided else why,
                correction=f"under open correction {under[key]}" if key in under else None,
                section=AI_DECIDED_GROUP if ai_decided else "",
            )
        )
    return entries


AI_DECIDED_GROUP = "AI-decided decisions"


def _settle_inferred(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    blocks = blocks_of(package.doc(stage))
    by_key = {b.key: b for b in blocks}
    current = package.current_item_hashes()
    for key, digest in hashes.items():
        entry = dict(record["blocks"].get(key) or {})
        reopened = entry.pop("reopened", None)
        entry.update(hash=digest, reviewed={"by": act.by, "at": act.at, "list": act.id, "reply": act.reply})
        if not reopened:  # a reopened block keeps its class: the comment changed nothing about where it came from
            entry["class"] = entry.get("class") if entry.get("class") in ("restated", "inferred") else "inferred"
            entry.pop("basis", None)
        block = by_key.get(key)
        if stage in DERIVED and block is not None and block.traces:
            entry["sources"] = {i: current[i] for i in block.traces if i in current}
        record["blocks"][key] = entry


def _reopen_inferred(package: Package, stage: str, record: dict[str, Any], hashes: dict[str, str], act: Act) -> None:
    for key in hashes:
        if key in act.marks:
            # 004 D-65: the mark alone puts a settled block back on the list; its hash, class and traces stay.
            entry = record["blocks"].setdefault(key, {"hash": hashes[key], "class": "inferred"})
            mark = {"by": act.by, "at": act.at, "list": act.id, "comment": act.comment or act.reply}
            if act.via:
                mark["via"] = act.via
            entry["reopened"] = mark
            continue
        entry = record["blocks"].get(key)
        if isinstance(entry, dict):
            entry.pop("reviewed", None)
            entry.pop("basis", None)
            if entry.get("class") in ("adopted", "adopted-pending"):
                entry["class"] = "inferred"


def _reopenable_inferred(package: Package, stage: str) -> dict[str, str]:
    """Every settled block of ``stage``, of any class: what a comment may reopen (004 D-65)."""
    return {key: info.block.hash for key, info in block_statuses(package).get(stage, {}).items() if info.status == SETTLED}


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


LEGACY_STATEMENT = (
    "This document changed since an approval the tool cannot compare section by section: the approval "
    "predates section-level records. One reply re-signs the stage, recorded as given without a comparison."
)


def legacy_entry(package: Package, stage: str) -> ListEntry | None:
    """The ``legacy:<stage>`` change entry, while the stage's approval predates section-level records and
    its document changed since (research D-56; FR-025)."""
    from .blockstatus import legacy_approval

    if stage not in ("requirements", "functional", "technical", "completion") or not package.exists(stage):
        return None
    approval = legacy_approval(package, stage)
    if approval is None:
        return None
    digest = _mix(f"legacy:{stage}", [str(approval.get("fingerprint")), str(package.fingerprint(stage))])
    return ListEntry(
        f"legacy:{stage}", digest, LEGACY_STATEMENT,
        f"approved by {approval.get('by')} on {str(approval.get('at', ''))[:10]}, before section-level records",
    )  # fmt: skip


def legacy_answered(package: Package, stage: str) -> str | None:
    """The acceptance id that answered the stage's legacy entry at its current content, if any."""
    entry = legacy_entry(package, stage)
    if entry is None:
        return None
    found = _answers(package, stage).get((entry.key, entry.hash))
    return found[1] if found and found[0] else None


def entry_question(kind: str, entry: ListEntry) -> str:
    """The fixed question a person answers for ``entry`` (004 D-64). A page answer stores it, so the
    record shows what an "Accept" confirmed; chat may show it too."""
    if entry.key.startswith("legacy:"):
        return f"{LEGACY_STATEMENT} Accept?"
    if kind == "inferred":
        if entry.key.startswith("§") and entry.members:
            return f"Accept every block under {entry.key[1:]} as written?"
        return f"Accept {entry.key} as written?"
    if kind == "changes":
        if entry.why.startswith("removed"):
            return f"Accept the removal of {entry.key}?"
        if entry.why.startswith("new"):
            return f"Accept the new {entry.key} as written?"
        return f"Accept {entry.key} as it now reads?"
    return f"Accept {entry.key}?"


def _build_changes(package: Package, stage: str) -> list[ListEntry]:
    from .provenance import change_rows

    answered = answered_changes(package, stage)
    inferred = {i.key for i in block_statuses(package).get(stage, {}).values() if i.status == NEEDS_REVIEW}
    entries = []
    legacy = legacy_entry(package, stage)
    if legacy is not None and legacy_answered(package, stage) is None:
        entries.append(legacy)
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
    out = {key: digest for key, (digest, _) in answered_changes(package, stage).items()}
    legacy = legacy_entry(package, stage)
    if legacy is not None and legacy_answered(package, stage):
        out[legacy.key] = legacy.hash
    return out


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
        reopenable=_reopenable_inferred,
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


DERIVED_LIST = "derived"
DERIVED_MEMBERS = ("ai-spec", "plan", "tasks")


def _check_stage(package: Package, stage: str) -> None:
    if stage == DERIVED_LIST:
        from .profile import active

        if active(package) is None:
            raise _refuse(
                "no-profile",
                "the combined derived list exists only under the small-story profile",
                "Review each stage's own list (--stage ai-spec, plan or tasks), or authorise the profile",
            )
        return
    if stage not in STAGES or not package.exists(stage):
        raise _refuse("unknown-stage", f"{stage!r} has no document in this story", f"Use one of: {', '.join(STAGES)}")


def _spec(kind: str) -> KindSpec:
    spec = KINDS.get(kind)
    if spec is None:
        raise _refuse("unknown-item", f"no review list of kind {kind!r} is available", f"Use one of: {', '.join(KINDS)}")
    return spec


def _scaffolding(entries: list[ListEntry]) -> list[ListEntry]:
    """Fold the blocks of each scaffolding section into one ``§<Section>`` entry (FR-018)."""
    wanted = {name.casefold(): name for name in SCAFFOLDING_SECTIONS}
    folded: dict[str, ListEntry] = {}
    out: list[ListEntry] = []
    for entry in entries:
        name = wanted.get(entry.section.casefold())
        if name is None or entry.conflict:
            out.append(entry)
            continue
        group = folded.get(name)
        if group is None:
            group = folded[name] = ListEntry(f"§{name}", "", "", section=entry.section)
            out.append(group)
        group.members[entry.key] = entry.hash
        group.what = f"{group.what}\n\n{entry.what}" if group.what else entry.what
    for name, group in folded.items():
        group.hash = _mix("§" + name, [f"{k}:{h}" for k, h in sorted(group.members.items())])
        count = len(group.members)
        group.why = f"{count} block{'s' if count != 1 else ''} of {name}, answered together"
    return out


def _sections(package: Package, stage: str) -> dict[str, str]:
    return {b.key: b.section for b in blocks_of(package.doc(stage))}


def build_list(
    package: Package,
    stage: str,
    kind: str,
    views: dict[str, str] | None = None,
    threshold: int = DEFAULT_THRESHOLD,
    session_view: bool = True,
) -> ReviewList:
    """The list of ``kind`` for ``stage``. With ``session_view`` (the default), an open review session
    narrows ``entries`` to what is still unanswered and fixes the mode to the session's."""
    spec = _spec(kind)
    _check_stage(package, stage)
    if stage == DERIVED_LIST:
        return _build_derived(package, kind, views, threshold, session_view)
    entries = spec.build(package, stage)
    conflicted = conflicted_keys(package, stage, {e.key: e.hash for e in entries} if kind == "changes" else None)
    sections = _sections(package, stage)
    for entry in entries:
        if entry.key in (views or {}):
            entry.ai_view = f"AI assessment: {views[entry.key]}"  # type: ignore[index]
        entry.conflict = entry.key in conflicted
        entry.section = entry.section or sections.get(entry.key, "")
    if kind == "inferred":
        entries = _scaffolding(entries)
    for entry in entries:
        entry.summary = entry.summary or summarise(entry.what)
        entry.question = entry_question(kind, entry)
    if spec.rework_first:
        entries.sort(key=lambda e: bool(e.ai_view) and _looks_valid(e.ai_view))
    limits = [*spec.limits, REPLY_LIMIT]
    if any((e.covered_by or "").startswith("CR-") or e.correction for e in entries):
        limits.append(CORRECTION_LIMIT)
    listed = ReviewList(kind, stage, spec.purpose, entries, limits, threshold)
    return _with_session(package, listed, session_view)


def _with_session(package: Package, listed: ReviewList, session_view: bool) -> ReviewList:
    entries = listed.entries
    stage, kind = listed.stage, listed.kind
    if session_view:
        found = _open_session(package, stage, kind)
        if found is not None:
            _, session = found
            answered = _live_answers(session, {e.key: e.hash for e in entries})
            listed.all_entries = entries
            listed.entries = [e for e in entries if e.key not in answered]
            listed.session_mode = str(session.get("mode") or listed.mode)
            listed.session = {"answered": len(answered), "remaining": len(listed.entries)}
            listed.answers = [_answer_row(e.key, answered[e.key]) for e in entries if e.key in answered]
        else:
            listed.last_answers = _last_answers(package, stage, kind, entries)
    return listed


def _last_answers(package: Package, stage: str, kind: str, entries: list[ListEntry]) -> list[dict[str, Any]]:
    """The latest send-back or question still standing on each listed entry, with its comment, from the
    recorded acceptances (004 D-72): what the agent acts on after the person says "done"."""
    if stage == DERIVED_LIST:
        return []
    group_of = {member: e.key for e in entries for member in e.members}
    latest: dict[str, dict[str, Any]] = {}
    for acc in (package.record(stage, "provenance") or {}).get("acceptances") or []:
        if not isinstance(acc, dict) or acc.get("kind") != kind:
            continue
        comments, questions = acc.get("comments") or {}, acc.get("questions") or {}
        for disposition, keys in (("accept", acc.get("accepted")), ("except", acc.get("except")), ("question", acc.get("questioned"))):
            for raw in keys or []:
                key = group_of.get(raw, raw)
                if disposition == "accept":
                    latest.pop(key, None)
                    continue
                comment = comments.get(key) or comments.get(raw) or (None if acc.get("via") else acc.get("reply"))
                latest[key] = {
                    "key": key, "disposition": disposition, "by": acc.get("by"), "at": acc.get("at"), "via": acc.get("via"),
                    "comment": comment, "question": questions.get(key) or questions.get(raw),
                }  # fmt: skip
    return [latest[e.key] for e in entries if e.key in latest]


def _answer_row(key: str, answer_: dict[str, Any]) -> dict[str, Any]:
    """One stored answer as ``review list`` returns it (004 D-72)."""
    return {
        "key": key, "disposition": answer_.get("disposition"), "by": answer_.get("by"), "at": answer_.get("at"),
        "via": answer_.get("via"), "comment": answer_.get("comment"), "question": answer_.get("question"),
    }  # fmt: skip


def _build_derived(
    package: Package, kind: str, views: dict[str, str] | None, threshold: int, session_view: bool
) -> ReviewList:
    """The ``derived`` list (D-52): the union of the inferred lists of the AI Specification, plan and
    tasks, each entry carrying its stage; settling it settles each in its own stage."""
    if kind != "inferred":
        raise _refuse("unknown-item", f"the derived list is an inferred list, not {kind!r}", "Use --kind inferred")
    entries: list[ListEntry] = []
    limits: list[str] = []
    for member in DERIVED_MEMBERS:
        if not package.exists(member):
            continue
        sub = build_list(package, member, kind, views, threshold, session_view=False)
        for entry in sub.entries:
            entry.extra["stage"] = member
            entry.section = f"{member}: {entry.section}" if entry.section else member
        entries += sub.entries
        limits += [limit for limit in sub.limits if limit not in limits]
    listed = ReviewList(kind, DERIVED_LIST, KINDS[kind].purpose, entries, limits or [REPLY_LIMIT], threshold)
    return _with_session(package, listed, session_view)


REVIEWED_ON_PAGE = ("requirements", "functional", "technical")


def current_review(package: Package, threshold: int = DEFAULT_THRESHOLD) -> dict[str, Any]:
    """The review the page shows (004 D-61): the current stage if it is Requirements, Functional or
    Technical and has a document, on its ``changes`` list once it has an approval record and on its
    ``inferred`` list before. ``document`` is that stage, or, with none, the latest of the three that
    exists. Derived on every call; never stored."""
    stage = package.current_stage()
    if stage not in REVIEWED_ON_PAGE or not package.exists(stage):
        stage = None
    existing = [s for s in REVIEWED_ON_PAGE if package.exists(s)]
    document = stage or (existing[-1] if existing else None)
    if stage is None:
        return {"stage": None, "kind": None, "entries": [], "document": document, "list": None}
    kind = "changes" if package.record(stage, "approval") else "inferred"
    listed = build_list(package, stage, kind, threshold=threshold)
    return {"stage": stage, "kind": kind, "entries": listed.entries, "document": document, "list": listed}


def show_entries(
    package: Package,
    stage: str,
    kind: str,
    entry: str | None = None,
    group: str | None = None,
    all_: bool = False,
    threshold: int = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """``review show``: the full text of one entry, one section's entries, or the whole list. Reads only."""
    listed = build_list(package, stage, kind, threshold=threshold, session_view=False)
    if entry is not None:
        chosen = [e for e in listed.entries if e.key == entry]
        if not chosen:
            raise _refuse("unknown-entry", f"{entry} is not on the {kind} list for {stage}", "Use a key from `review list`")
    elif group is not None:
        chosen = [e for e in listed.entries if e.section.casefold() == group.casefold() or e.key == f"§{group}"]
        if not chosen:
            raise _refuse("unknown-entry", f"no entry of the {kind} list for {stage} is in {group!r}", "Use a section from `review list`")
    else:
        chosen = list(listed.entries)
    parts = []
    for e in chosen:
        parts.append(f"{e.key} ({e.why})" + (f"\n{e.ai_view}" if e.ai_view else "") + f"\n{e.what}")
    return {
        "ok": True,
        "stage": stage,
        "kind": kind,
        "entries": [e.to_json() for e in chosen],
        "text": "\n\n".join(parts) or "The list is empty.",
    }


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


def _open_session(package: Package, stage: str, kind: str) -> tuple[str, dict[str, Any]] | None:
    """The open review session of ``stage``/``kind`` (story.review_sessions), with its key."""
    sessions = package.story_record().get("review_sessions") or {}
    for key, session in sessions.items():
        if isinstance(session, dict) and session.get("stage") == stage and session.get("kind") == kind:
            return key, session
    return None


def _live_answers(session: dict[str, Any], current: dict[str, str]) -> dict[str, dict[str, Any]]:
    """The session's answers still standing: an answer lapses when its entry's content changed."""
    return {
        key: answer
        for key, answer in (session.get("answers") or {}).items()
        if isinstance(answer, dict) and current.get(key) == answer.get("hash")
    }


def _save_session(package: Package, key: str, session: dict[str, Any] | None) -> None:
    sessions = dict(package.story_record().get("review_sessions") or {})
    if session is None:
        sessions.pop(key, None)
    else:
        sessions[key] = session
    try:
        package.write_story_record("review_sessions", sessions or None)
    except RegionError as exc:
        raise _refuse("not-amendable", f"cannot store the answer: {exc}", "Repair or remove eil-record.json first") from exc


def _expand(keys: list[str], on_list: dict[str, ListEntry]) -> list[str]:
    """Scaffolding entries stand for their member blocks when an answer is recorded."""
    out: list[str] = []
    for key in keys:
        entry = on_list.get(key)
        out += list(entry.members) if entry is not None and entry.members else [key]
    return out


def _hashes(keys: list[str], on_list: dict[str, ListEntry], settled: dict[str, str]) -> dict[str, str]:
    members = {m: h for e in on_list.values() for m, h in e.members.items()}
    return {k: members.get(k) or (on_list[k].hash if k in on_list else settled[k]) for k in keys}


def _apply(
    package: Package,
    spec: KindSpec,
    stage: str,
    kind: str,
    *,
    digest: str | None,
    by: str,
    reply: str,
    accepted: list[str],
    excepted: list[str],
    questioned: list[str],
    reopened: list[str],
    hashes: dict[str, str],
    resolving: bool,
    defer_reason: str | None,
    summaries: dict[str, str] | None,
    mode: str,
    unseen: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    comment: str | None = None,
    via: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Record one acceptance and let the kind settle or reopen what it names (the one answer path).
    ``extra`` carries 004's ``via``, ``questions``, ``comments`` and ``together`` when they apply."""
    read = package.record_read(stage, "provenance")
    if read.error:
        raise _refuse("not-amendable", f"{stage} has a malformed provenance region: {read.error}", "Repair or remove it first")
    record = read.obj if read.obj is not None else (adopt(package, stage) or {"version": 1, "blocks": {}})
    record.setdefault("blocks", {})
    deferring = bool(accepted) and spec.defers
    act = Act(_next_id(package), by, clock.utc_now(), reply, summaries or {}, (defer_reason or "").strip() or None)
    act.marks, act.comment, act.via = set(reopened) if spec.reopenable else set(), comment, via
    acc: dict[str, Any] = {
        "id": act.id, "stage": stage, "kind": kind, "digest": digest, "by": by, "at": act.at, "reply": reply,
        "accepted": [] if deferring else accepted, "except": excepted, "questioned": questioned,
        "reopened": reopened, "reason": act.reason, "hashes": hashes, "mode": mode,
    }  # fmt: skip
    if deferring:
        acc["deferred"] = accepted
    if unseen:
        acc["unseen"] = unseen
    if summaries:
        acc["summaries"] = {k: v.strip() for k, v in summaries.items() if k in hashes and v.strip()}
    acc.update({k: v for k, v in (extra or {}).items() if v})
    if spec.settle and accepted:
        spec.settle(package, stage, record, {k: hashes[k] for k in accepted}, act)
    undone = {k: hashes[k] for k in (*excepted, *reopened)}
    if spec.reopen and undone:
        spec.reopen(package, stage, record, undone, act)
    rows, resolved = _update_conflicts(record, acc, resolving)
    if resolved:
        acc["resolved_conflict"] = True
    record.setdefault("acceptances", []).append(acc)
    if rows or "conflicts" in record:
        record["conflicts"] = rows
    try:
        package.write_record(stage, "provenance", record)
    except RegionError as exc:
        raise _refuse("not-amendable", f"cannot record the answer in {stage}: {exc}", "Repair the document") from exc
    return acc, rows, resolved


def _settled_for(spec: KindSpec, package: Package, stage: str) -> dict[str, str]:
    if spec.settled is None:
        return {}
    if stage == DERIVED_LIST:
        return {k: h for member in DERIVED_MEMBERS if package.exists(member) for k, h in spec.settled(package, member).items()}
    return spec.settled(package, stage)


def _apply_split(
    package: Package, spec: KindSpec, stage: str, kind: str, on_list: dict[str, ListEntry], **kwargs: Any
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """``_apply``, once per member stage when the list is the combined ``derived`` one."""
    if stage != DERIVED_LIST:
        return _apply(package, spec, stage, kind, **kwargs)
    owner = {}
    for entry in on_list.values():
        for key in entry.members or [entry.key]:
            owner[key] = entry.extra.get("stage")
    results: list[tuple[dict[str, Any], list[dict[str, Any]], bool]] = []
    for member in DERIVED_MEMBERS:
        part = {name: [k for k in kwargs[name] if owner.get(k) == member] for name in ("accepted", "excepted", "questioned", "reopened")}
        if not any(part.values()):
            continue
        hashes = {k: h for k, h in kwargs["hashes"].items() if owner.get(k) == member}
        unseen = [k for k in kwargs.get("unseen") or [] if owner.get(k) == member]
        extra = {
            name: ({k: v for k, v in value.items() if owner.get(k) == member} if isinstance(value, dict) else value)
            for name, value in (kwargs.get("extra") or {}).items()
        }
        results.append(
            _apply(
                type(package)(package.root), spec, member, kind,
                **{**kwargs, **part, "hashes": hashes, "unseen": unseen, "extra": extra},
            )  # fmt: skip
        )
    if not results:
        return {"id": None, "accepted": [], "questioned": [], "reopened": []}, [], False
    accs = [r[0] for r in results]
    merged = {
        "id": ", ".join(a["id"] for a in accs),
        "accepted": [k for a in accs for k in a["accepted"]],
        "questioned": [k for a in accs for k in a["questioned"]],
        "reopened": [k for a in accs for k in a["reopened"]],
        "deferred": [k for a in accs for k in a.get("deferred", [])],
    }
    return merged, [row for r in results for row in r[1]], any(r[2] for r in results)


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
    entry: str | None = None,
    disposition: str = "accept",
    rest: bool = False,
    threshold: int | None = None,
    shown: str | None = None,
    via: str | None = None,
    asked: str | None = None,
    comment: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    """Record a person's reply to a list: to the whole list in one reply (``all_``, ``all_except``,
    ``question``, ``reopen``), or to one entry (``entry``) or to every remaining one (``rest``), which are
    stored in a review session and applied together when the last entry is answered (D-51).

    004 (D-63, D-70): ``shown`` is the version of the entry the person saw (``entry-changed`` when it is
    not the current one); ``asked`` is the fixed question they answered (``question-mismatch`` unless it
    is the helper's); ``comment`` is stored verbatim; ``via="page"`` marks an answer given on the review
    page, whose reply is its comment or "Accept", and whose send-back, question or reopen needs a comment
    (``comment-required``). ``section`` narrows ``rest`` to one section, accepted together and seen."""
    from .records import approvers_for

    spec = _spec(kind)
    _check_stage(package, stage)
    threshold = config.one_at_a_time_max if threshold is None else threshold
    modes = [all_, all_except is not None, bool(question), bool(reopen), entry is not None, rest]
    if sum(modes) != 1:
        raise usage_error("give exactly one of --all, --all-except, --question, --reopen, --entry, --rest")
    if disposition not in DISPOSITIONS:
        raise usage_error(f"--disposition is one of {', '.join(DISPOSITIONS)}")
    if via not in (None, "page"):
        raise usage_error("via is the page or nothing")
    if section is not None and not rest:
        raise usage_error("--section is given with --rest")
    listed = build_list(package, stage, kind, threshold=threshold, session_view=False)
    on_list = {e.key: e for e in listed.entries}
    settled = _settled_for(spec, package, stage)
    authority = DERIVED_MEMBERS[0] if stage == DERIVED_LIST else stage
    confirmer = confirmer_refusal(by, approvers_for(package, config, authority), authority) is None
    session = _open_session(package, stage, kind)
    refusals: list[Refusal] = []

    def add(code: str, message: str, fix: str = "") -> None:
        refusals.append(Refusal(code, message, fix))

    if is_ai_actor(by):
        add("ai-approval", f"{by!r} is the AI; only a person may answer a review list", "Ask the developer to reply")
    if via == "page":
        words = (comment or "").strip()
        if (entry is not None and disposition != "accept") or reopen:
            if not words:
                add("comment-required", "a send-back, a question or a reopen on the page needs a comment", "Write what should change, or what you want to know")
        reply = words or ("Accept" if not reopen and (rest or disposition == "accept") else "")
    if not reply.strip() and not any(r.code == "comment-required" for r in refusals):
        add("reply-required", "a reply needs the person's own words", "Ask the person and pass their words with --reply")
    if entry is not None or rest:
        return _answer_session(
            package, spec, stage, kind, listed, on_list, session, refusals, confirmer=confirmer, by=by, reply=reply,
            entry=entry, disposition=disposition, rest=rest, defer_reason=defer_reason, summaries=summaries,
            shown=shown, via=via, asked=asked, comment=comment, section=section,
        )  # fmt: skip
    settling = all_ or all_except is not None
    if settling and not digest:
        add("digest-required", "a settling answer must name the list the person saw", "Pass --digest from `review list`")
    elif digest and digest != listed.digest:
        add("list-changed", "the list changed since the person saw it", "Run `review list` again and show it")
    if settling and not confirmer and not is_ai_actor(by):
        add("not-a-confirmer", f"{by!r} is not configured to confirm {stage}", "Ask a configured confirmer")
    if settling and spec.defers and not (defer_reason or "").strip():
        add("reason-required", "a deferral needs a reason", "Pass --defer-reason")
    named = list(all_except or []) + list(question or []) + list(reopen or [])
    if reopen and spec.reopenable is not None and stage != DERIVED_LIST:
        settled = {**spec.reopenable(package, stage), **settled}
    for key in reopen or []:
        now = on_list[key].hash if key in on_list else settled.get(key)
        if shown is not None and now is not None and shown != now:
            add("entry-changed", f"{key} changed since it was shown; nothing was stored", "Read it again before commenting")
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

    if session is not None and not reopen:
        # A reply to the whole list while answers are being stored entry by entry answers what remains.
        key, held = session
        current = {e.key: e.hash for e in listed.entries}
        answers = _live_answers(held, current)
        stamp = clock.utc_now()
        for k in on_list:
            if k in answers and k not in named:
                continue
            if question and k not in question:
                continue
            chosen = "question" if question else ("except" if k in (all_except or []) else "accept")
            answers[k] = {"by": by, "at": stamp, "disposition": chosen, "reply": reply, "hash": current[k], "seen": True}
        held["answers"] = answers
        return _close_or_keep(package, spec, stage, kind, listed, on_list, key, held, defer_reason, summaries, confirmer)

    excepted = list(all_except or [])
    accepted = [k for k in on_list if k not in excepted] if settling else []
    accepted_x, excepted_x = _expand(accepted, on_list), _expand(excepted, on_list)
    questioned_x, reopened_x = _expand(list(question or []), on_list), list(reopen or [])
    hashes = _hashes([*excepted_x, *questioned_x, *reopened_x, *accepted_x], on_list, settled)
    acc, rows, resolved = _apply_split(
        package, spec, stage, kind, on_list, digest=digest, by=by, reply=reply, accepted=accepted_x, excepted=excepted_x,
        questioned=questioned_x, reopened=reopened_x, hashes=hashes, resolving=confirmer and settling,
        defer_reason=defer_reason, summaries=summaries, mode=listed.mode, comment=comment, via=via,
        extra={"via": via, "comments": {k: comment for k in reopened_x} if comment and reopened_x else None},
    )  # fmt: skip
    conflicts = sorted({r["key"] for r in rows if r["key"] in hashes})
    lines = [f"Recorded {acc['id']} by {by}: {len(accepted_x)} accepted, {len(excepted_x)} excepted."]
    if conflicts:
        lines.append("In conflict: " + ", ".join(conflicts))
    return {
        "ok": True,
        "id": acc["id"],
        "stage": stage,
        "kind": kind,
        "mode": listed.mode,
        "accepted": acc["accepted"],
        "except": excepted_x,
        "questioned": acc["questioned"],
        "reopened": acc["reopened"],
        "deferred": acc.get("deferred", []),
        "conflicts": conflicts,
        "resolved_conflict": resolved,
        "closed": True,
        "text": "\n".join(lines),
    }


DISPOSITIONS = ("accept", "except", "question")


def _answer_session(
    package: Package,
    spec: KindSpec,
    stage: str,
    kind: str,
    listed: ReviewList,
    on_list: dict[str, ListEntry],
    session: tuple[str, dict[str, Any]] | None,
    refusals: list[Refusal],
    *,
    confirmer: bool,
    by: str,
    reply: str,
    entry: str | None,
    disposition: str,
    rest: bool,
    defer_reason: str | None,
    summaries: dict[str, str] | None,
    shown: str | None = None,
    via: str | None = None,
    asked: str | None = None,
    comment: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    """Store one entry's answer (or "ok to the rest") in the review session; apply it when complete."""
    settling = rest or disposition == "accept"
    if entry is not None and entry not in on_list:
        if shown is not None:
            refusals.append(Refusal("entry-changed", f"{entry} changed since it was shown and is no longer on the list as shown", "Reload and read the list again"))
        else:
            refusals.append(Refusal("unknown-entry", f"{entry} is not on the {kind} list for {stage}", "Name an entry from `review list`"))
    elif entry is not None:
        now = on_list[entry]
        if shown is not None and shown != now.hash:
            refusals.append(
                Refusal(
                    "entry-changed", f"{entry} changed since it was shown; nothing was stored",
                    "Read it again before answering", current={"key": entry, "hash": now.hash, "what": now.what},
                )  # fmt: skip
            )
        if asked is not None and asked != entry_question(kind, now):
            refusals.append(Refusal("question-mismatch", f"that is not the helper's question for {entry}", f'Ask: "{entry_question(kind, now)}"'))
    if settling and not confirmer and not is_ai_actor(by):
        refusals.append(Refusal("not-a-confirmer", f"{by!r} is not configured to confirm {stage}", "Ask a configured confirmer"))
    if settling and spec.defers and not (defer_reason or "").strip():
        refusals.append(Refusal("reason-required", "a deferral needs a reason", "Pass --defer-reason"))
    if reply.strip() and not settling and _ALL_PHRASE.match(reply.strip()):
        refusals.append(Refusal("reply-mismatch", f"the reply says yes but the answer is {disposition}", "Use --disposition accept, or reword the reply"))
    if refusals:
        seen: dict[tuple[str, str], Refusal] = {(r.code, r.message): r for r in refusals}
        raise refuse(*seen.values())
    current = {e.key: e.hash for e in listed.entries}
    if session is None:
        key = f"{stage}/{kind}/{listed.digest}"
        held: dict[str, Any] = {
            "stage": stage, "kind": kind, "digest": listed.digest, "mode": listed.mode,
            "opened_at": clock.utc_now(), "entries": dict(current), "answers": {},
        }  # fmt: skip
    else:
        key, held = session
    answers = _live_answers(held, current)
    stamp = clock.utc_now()
    reason = (defer_reason or "").strip() or None
    targets = [entry] if entry is not None else [k for k in on_list if k not in answers]
    if section is not None:
        targets = [k for k in targets if on_list[k].section.casefold() == section.casefold()]
        if not targets:
            raise refuse(Refusal("unknown-entry", f"no unanswered entry of the {kind} list for {stage} is in {section!r}", "Name a section from `review list`"))
    for target in targets:
        record = {"by": by, "at": stamp, "disposition": "accept" if rest else disposition, "reply": reply, "hash": current[target], "seen": not rest or section is not None}
        if via is not None:
            record["via"] = via
        if asked is not None or via == "page":
            record["question"] = asked if asked is not None and entry is not None else entry_question(kind, on_list[target])
        if comment is not None and comment.strip():
            record["comment"] = comment
        if section is not None:
            record["together"] = section
        earlier = answers.get(target)
        if earlier is not None and normalise_person(earlier["by"]) != normalise_person(by) and earlier["disposition"] != record["disposition"]:
            held.setdefault("superseded", []).append({"key": target, **earlier})
        answers[target] = record
        if reason:
            held.setdefault("reasons", {})[target] = reason
        if summaries and summaries.get(target, "").strip():
            held.setdefault("summaries", {})[target] = summaries[target].strip()
    held["answers"] = answers
    return _close_or_keep(package, spec, stage, kind, listed, on_list, key, held, defer_reason, summaries, confirmer)


def _close_or_keep(
    package: Package,
    spec: KindSpec,
    stage: str,
    kind: str,
    listed: ReviewList,
    on_list: dict[str, ListEntry],
    key: str,
    held: dict[str, Any],
    defer_reason: str | None,
    summaries: dict[str, str] | None,
    confirmer: bool,
) -> dict[str, Any]:
    answers = held["answers"]
    remaining = [k for k in on_list if k not in answers]
    if remaining:
        _save_session(package, key, held)
        return {
            "ok": True, "stage": stage, "kind": kind, "mode": held["mode"], "closed": False,
            "answered": len(answers), "remaining": remaining,
            "text": f"Stored. {len(answers)} answered, {len(remaining)} to go: {', '.join(remaining)}.",
        }  # fmt: skip
    groups: dict[tuple[str, str, bool, str, str], dict[str, Any]] = {}
    ordered = [(a.get("key"), a) for a in held.get("superseded", [])] + sorted(answers.items(), key=lambda kv: kv[1]["at"])
    ids: list[str] = []
    for entry_key, answer_ in ordered:
        if entry_key not in on_list:
            continue
        reason = (held.get("reasons") or {}).get(entry_key, "")
        group_key = (answer_["by"], answer_["reply"], bool(answer_["seen"]), reason, answer_.get("via") or "")
        slot = groups.setdefault(group_key, {"accept": [], "except": [], "question": [], "questions": {}, "comments": {}, "together": {}})
        slot[answer_["disposition"]].append(entry_key)
        for field_name, stored in (("questions", "question"), ("comments", "comment"), ("together", "together")):
            if answer_.get(stored):
                slot[field_name][entry_key] = answer_[stored]
    stored_summaries = {**(held.get("summaries") or {}), **(summaries or {})}
    settled = _settled_for(spec, package, stage)
    for (by, reply, seen, reason, via), slot in groups.items():
        accepted_x, excepted_x = _expand(slot["accept"], on_list), _expand(slot["except"], on_list)
        questioned_x = _expand(slot["question"], on_list)
        hashes = _hashes([*excepted_x, *questioned_x, *accepted_x], on_list, settled)
        acc, _, _ = _apply_split(
            type(package)(package.root), spec, stage, kind, on_list, digest=held["digest"], by=by, reply=reply,
            accepted=accepted_x, excepted=excepted_x, questioned=questioned_x, reopened=[], hashes=hashes,
            resolving=confirmer and bool(accepted_x), defer_reason=reason or defer_reason,
            summaries=stored_summaries, mode=held["mode"], unseen=[] if seen else accepted_x,
            extra={"via": via or None, "questions": slot["questions"], "comments": slot["comments"], "together": slot["together"]},
        )  # fmt: skip
        ids.append(acc["id"])
    _save_session(type(package)(package.root), key, None)
    return {
        "ok": True, "stage": stage, "kind": kind, "mode": held["mode"], "closed": True, "ids": ids,
        "answered": len(answers), "remaining": [],
        "text": f"All {len(answers)} entries answered; recorded {', '.join(ids)}.",
    }  # fmt: skip


def confirm(
    package: Package, config: Config, stage: str, *, by: str, confirmation: str, summaries: dict[str, str] | None = None
) -> dict[str, Any]:
    """Bring an approved stage back once its changes are covered or answered (research D-37)."""
    from .provenance import confirm_changes

    return confirm_changes(package, config, stage, by, confirmation, summaries)

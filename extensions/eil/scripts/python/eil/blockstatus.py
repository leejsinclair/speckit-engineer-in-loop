"""Derived status of content blocks, and upgrade adoption (data-model "Derived status"; research D-34, D-42).

Status is computed from the provenance region, the current block hashes and the approvals. It is never
stored. ``adopt`` is a pure function returning the provenance record an upgrade would write for a stage
that has none; ``sync`` persists it, and ``status`` and ``check`` use the in-memory result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .content import Block, blocks_of
from .trace import _TAG, parse_document, section_fingerprints

if TYPE_CHECKING:
    from .package import Package

DEFINITION = ("requirements", "functional", "technical")
DERIVED = ("ai-spec", "plan", "tasks", "verification")
SETTLED, NEEDS_REVIEW, SOURCE_CHANGED, UNKNOWN_CURRENCY = (
    "settled",
    "needs-review",
    "source-changed",
    "unknown-currency",
)
# A block covered by an approval older than section-level records, on a document changed since (D-56).
# It does not need review and is on no inferred list; one reply to the stage's ``legacy:<stage>`` change
# entry re-signs the stage and turns it into ``adopted``.
SETTLED_PENDING = "settled-pending"
ADOPTED_PENDING = "adopted-pending"


def _approval(package: Package, stage: str) -> dict[str, Any] | None:
    """The stage's recorded approval, read directly: never through ``Package.state``, which derives a
    derived stage's ``reviewed`` state from these block statuses (D-58)."""
    if package.approval_line_without_record(stage) is not None:
        return None
    obj = package.record(stage, "approval")
    return obj if isinstance(obj, dict) and isinstance(obj.get("fingerprint"), str) else None


def legacy_approval(package: Package, stage: str) -> dict[str, Any] | None:
    """The stage's approval when it predates section-level records and the document changed since."""
    approval = _approval(package, stage)
    if approval is None or approval.get("fingerprint") == package.fingerprint(stage):
        return None
    return approval if not isinstance(approval.get("section_fingerprints"), dict) else None


@dataclass
class BlockInfo:
    stage: str
    block: Block
    status: str
    klass: str | None = None
    stale: bool = False  # source-changed, or a source is not settled (D-34)

    @property
    def key(self) -> str:
        return self.block.key


def _tagged(block: Block) -> bool:
    return bool(_TAG.search(block.text))


def adopt(package: Package, stage: str) -> dict[str, Any] | None:
    """The provenance record an upgrade writes for ``stage``, or ``None`` when the document is absent,
    already has a provenance region, or has a malformed one (never auto-adopted)."""
    if not package.exists(stage):
        return None
    doc = package.doc(stage)
    if "provenance" in doc.regions or package.record_read(stage, "provenance").error:
        return None
    approval = _approval(package, stage)
    fingerprint = package.fingerprint(stage)
    blocks = blocks_of(doc)
    entries: dict[str, Any] = {}

    def adopted(block: Block, basis: str) -> dict[str, Any]:
        return {"hash": block.hash, "class": "adopted", "basis": basis}

    if approval is not None and approval.get("fingerprint") == fingerprint:
        basis = f"approval {approval.get('by')} {approval.get('at')}"
        entries = {b.key: adopted(b, basis) for b in blocks}
    elif approval is not None:
        basis = f"approval {approval.get('by')} {approval.get('at')}"
        recorded = approval.get("items") if isinstance(approval.get("items"), dict) else {}
        parsed = parse_document(doc)
        now = section_fingerprints(doc, parsed.items)
        then = approval.get("section_fingerprints")
        then = then if isinstance(then, dict) else {}
        legacy = not isinstance(approval.get("section_fingerprints"), dict)
        for b in blocks:
            if b.numbered:
                covered = recorded.get(b.key) == b.hash if b.kind != "plan" else False
            else:
                covered = b.section in then and then[b.section] == now.get(b.section)
            if covered:
                entries[b.key] = adopted(b, basis)
            elif legacy:
                # Nothing to compare it with: covered by the legacy approval until one reply re-signs it.
                entries[b.key] = {"hash": b.hash, "class": ADOPTED_PENDING, "basis": f"legacy {basis}"}
    else:
        for b in blocks:
            if _tagged(b):
                entries[b.key] = {"hash": b.hash, "class": "inferred"}
            else:
                entries[b.key] = adopted(b, "untagged before upgrade")
    return {"version": 1, "currency": "unknown" if stage in DERIVED else "known", "blocks": entries}


def persist_adoption(package: Package) -> None:
    """D-42: the first writing command records the provenance an upgrade adopts, once per document.
    Shared by the command line and the review page, so both write the same records (004 D-63)."""
    for stage in package.existing_stages():
        record = adopt(package, stage)
        if record is not None:
            package.write_record(stage, "provenance", record)


def approved_ids(package: Package) -> set[str]:
    """Ids of the definition items (s01 to s03) whose current text an approval covers and that no change
    upstream of them reaches. Item-level, so one edited decision does not unsettle its neighbours (D-35)."""
    key = tuple(package.fingerprint(s) or "" for s in package.existing_stages())
    cached = package.__dict__.get("_approved_ids")
    if cached is None or cached[0] != key:
        parsed = package.parsed_story()
        hit = {i for ids in package.affected_items().values() for i in ids}
        current = package.current_item_hashes()
        out: set[str] = set()
        for stage in DEFINITION:
            if stage not in parsed:
                continue
            state = package.state(stage)
            recorded = (state.approval or {}).get("items")
            if state.approval is None:
                continue
            for item in parsed[stage].items:
                if isinstance(recorded, dict):
                    covered = recorded.get(item.id) == current.get(item.id)
                else:
                    covered = state.state == "approved"
                if covered and item.id not in hit:
                    out.add(item.id)
        cached = (key, out)
        package.__dict__["_approved_ids"] = cached
    return set(cached[1])


class _Computer:
    def __init__(self, package: Package) -> None:
        self.package = package
        self.hashes = package.current_item_hashes()
        self.approved = approved_ids(package)
        self.done: dict[str, dict[str, BlockInfo]] = {}
        self.active: set[str] = set()
        self.owner: dict[str, str] = {}
        for stage in package.existing_stages():
            for b in blocks_of(package.doc(stage)):
                self.owner.setdefault(b.key, stage)

    def stage(self, stage: str) -> dict[str, BlockInfo]:
        if stage not in self.done:
            if stage in self.active:  # a tracing cycle: treat the inner reference as unsettled
                return {}
            self.active.add(stage)
            try:
                self.done[stage] = self._compute(stage)
            finally:
                self.active.discard(stage)
        return self.done[stage]

    def _record(self, stage: str) -> tuple[dict[str, Any], str]:
        read = self.package.record_read(stage, "provenance")
        if read.error:
            return {}, "known"
        if read.obj is None:
            adopted = adopt(self.package, stage)
            return (adopted or {}).get("blocks", {}), (adopted or {}).get("currency", "known")
        blocks = read.obj.get("blocks")
        return (blocks if isinstance(blocks, dict) else {}), read.obj.get("currency", "known")

    def _source_settled(self, source: str) -> bool:
        owner = self.owner.get(source)
        if owner is None:
            return False
        if owner in DEFINITION:
            return source in self.approved
        info = self.stage(owner).get(source)
        return info is not None and info.status in (SETTLED, UNKNOWN_CURRENCY) and not info.stale

    def _compute(self, stage: str) -> dict[str, BlockInfo]:
        record, _currency = self._record(stage)
        out: dict[str, BlockInfo] = {}
        for block in blocks_of(self.package.doc(stage)):
            out[block.key] = self._one(stage, block, record.get(block.key))
        return out

    def _differs(self, mapping: Any) -> bool:
        return isinstance(mapping, dict) and any(self.hashes.get(i) != h for i, h in mapping.items())

    def _one(self, stage: str, block: Block, entry: dict[str, Any] | None) -> BlockInfo:
        if not isinstance(entry, dict):
            return BlockInfo(stage, block, NEEDS_REVIEW)
        klass = entry.get("class")
        info = BlockInfo(stage, block, NEEDS_REVIEW, klass)
        if klass == ADOPTED_PENDING:
            if entry.get("hash") == block.hash:
                info.status = SETTLED_PENDING
            return info
        if klass == "decided":
            info.status = SETTLED
            return info
        own_current = entry.get("hash") == block.hash
        cites, sources = entry.get("cites"), entry.get("sources")
        reviewed = bool(entry.get("reviewed"))
        moved = self._differs(cites) or self._differs(sources)
        if klass == "restated":
            unsettled = [i for i in (cites or {}) if not self._source_settled(i)]
            if not own_current:
                pass
            elif moved:
                info.status, info.stale = SOURCE_CHANGED, True
            elif unsettled:
                info.stale = True
            elif not entry.get("adds"):
                info.status = SETTLED
            return info
        if own_current and (reviewed or klass == "adopted"):
            if moved:
                info.status, info.stale = SOURCE_CHANGED, True
            else:
                info.status = SETTLED
        if (
            info.status == SETTLED
            and stage in DERIVED
            and block.traces
            and not isinstance(sources, dict)
            and entry.get("class") != "decided"
        ):
            info.status = UNKNOWN_CURRENCY
        if info.status == SETTLED and isinstance(sources, dict):
            info.stale = any(not self._source_settled(i) for i in sources)
        return info


def block_statuses(package: Package) -> dict[str, dict[str, BlockInfo]]:
    """``{stage: {block key: BlockInfo}}`` for every existing stage, cached on ``package`` against the
    fingerprint of every stage, like ``Package.parsed_story``."""
    key = tuple(package.fingerprint(s) or "" for s in package.existing_stages())
    cached = package.__dict__.get("_block_statuses")
    if cached is None or cached[0] != key:
        computer = _Computer(package)
        cached = (key, {s: computer.stage(s) for s in package.existing_stages()})
        package.__dict__["_block_statuses"] = cached
    return cached[1]


def source_settled(package: Package, source: str) -> bool:
    """Whether ``source`` may be restated from: an approved definition item, or a derived block that is
    settled and not stale (research D-32)."""
    return _Computer(package)._source_settled(source)


def unreviewed(package: Package, stage: str) -> list[BlockInfo]:
    """The blocks of ``stage`` that need review, in document order."""
    return [i for i in block_statuses(package).get(stage, {}).values() if i.status == NEEDS_REVIEW]


def counts(package: Package, stage: str) -> dict[str, int]:
    """``{settled, needs_review, stale, unknown}`` for ``stage`` (``source-changed`` counts as stale)."""
    out = {"settled": 0, "needs_review": 0, "stale": 0, "unknown": 0, "pending": 0}
    for info in block_statuses(package).get(stage, {}).values():
        if info.status == SETTLED_PENDING:
            out["pending"] += 1
        if info.status == SETTLED:
            out["settled"] += 1
        elif info.status == NEEDS_REVIEW:
            out["needs_review"] += 1
        elif info.status == UNKNOWN_CURRENCY:
            out["unknown"] += 1
        if info.stale or info.status == SOURCE_CHANGED:
            out["stale"] += 1
    return out


def stale_sources(package: Package, stage: str) -> dict[str, list[str]]:
    """``{block key: source ids whose hash no longer matches}`` from the recorded ``sources`` and ``cites``."""
    if not package.exists(stage):
        return {}
    obj = package.record(stage, "provenance")
    blocks = (obj or {}).get("blocks")
    hashes = package.current_item_hashes()
    out: dict[str, list[str]] = {}
    for key, entry in (blocks if isinstance(blocks, dict) else {}).items():
        moved = [
            i
            for field_name in ("sources", "cites")
            for i, h in (entry.get(field_name) or {}).items()
            if isinstance(entry, dict) and hashes.get(i) != h
        ]
        if moved:
            out[key] = sorted(set(moved))
    return out

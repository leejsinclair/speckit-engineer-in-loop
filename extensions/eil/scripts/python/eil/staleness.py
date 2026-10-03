"""Scoped staleness: which work a change reaches, and only that work (research D-34, D-35; FR-002, FR-003).

Nothing here is stored. Whether a derived block is stale comes from the source versions recorded when it
was settled (``blockstatus``); this module turns that into the set of blocked work with its causes, the
document errors that make a trace graph untrustworthy, and the snapshots that say which versions a
ticked task was completed against.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .blocks import RegionError
from .blockstatus import DERIVED, NEEDS_REVIEW, SETTLED, SOURCE_CHANGED, adopt, block_statuses
from .content import Block, blocks_of

if TYPE_CHECKING:
    from .package import Package

PENDING = "pending-clarification"
_ID = re.compile(r"^[A-Z]+-\d+$")
_TICKED = re.compile(r"^\s*-\s+\[[xX]\]")


def _blocks(package: Package) -> dict[str, tuple[str, Block]]:
    """Every numbered block by key, with its stage."""
    out: dict[str, tuple[str, Block]] = {}
    for stage in package.existing_stages():
        for b in blocks_of(package.doc(stage)):
            if b.numbered:
                out.setdefault(b.key, (stage, b))
    return out


def _reachable(start: str, edges: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(edges.get(start, ()))
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(edges.get(node, ()))
    return seen


def _cycle_members(edges: dict[str, list[str]]) -> set[str]:
    return {k for k in edges if k in _reachable(k, edges)}


def problems(package: Package) -> list[tuple[str, str]]:
    """``[(code, message)]``: a tracing cycle or an id nothing defines in a derived document."""
    known = _blocks(package)
    edges = {k: [t for t in b.traces if t in known] for k, (_, b) in known.items()}
    out: list[tuple[str, str]] = []
    members = sorted(_cycle_members(edges))
    if members:
        out.append(("trace-cycle", "these items trace to each other in a cycle: " + ", ".join(members)))
    for key, (stage, block) in known.items():
        if stage in DERIVED:
            out += [
                ("dangling-trace", f"{key} traces to {t}, which nothing defines")
                for t in block.traces
                if _ID.match(t) and t not in known
            ]
    return out


def _pending(block: Block) -> bool:
    return f"[{PENDING}]" in block.text


def _sources_moved(package: Package, stage: str, key: str, hashes: dict[str, str]) -> list[str]:
    obj = package.record(stage, "provenance")
    entry = ((obj or {}).get("blocks") or {}).get(key)
    if not isinstance(entry, dict):
        return []
    moved = []
    for name in ("sources", "cites"):
        recorded = entry.get(name)
        if isinstance(recorded, dict):
            moved += [i for i, h in recorded.items() if hashes.get(i) != h]
    return sorted(set(moved))


class Cause(str):
    """Why some work is blocked, with the fix that would unblock it."""

    fix: str

    def __new__(cls, text: str, fix: str = "") -> Cause:
        obj = super().__new__(cls, text)
        obj.fix = fix
        return obj


def scoped_work(package: Package) -> tuple[dict[str, list[Cause]], dict[str, list[Cause]]]:
    """``(blocked, rederive)``: the derived blocks that may not be relied on, and of those, the ones whose
    every changed source is already settled, so they only need deriving again (D-35).

    A block is blocked when a source it was settled against changed and is not yet accepted, when it or
    something it traces to is a pending clarification, when it sits in a tracing cycle or cites an id
    nothing defines, when its recorded answers conflict (FR-050), or when a block it traces to is itself
    blocked or needs deriving again."""
    from .blockstatus import approved_ids
    from .reviews import conflicted_keys

    known = _blocks(package)
    statuses = block_statuses(package)
    hashes = package.current_item_hashes()
    approved = approved_ids(package)
    edges = {k: list(b.traces) for k, (_, b) in known.items()}
    hard: dict[str, list[Cause]] = {}
    soft: dict[str, list[Cause]] = {}

    def add(table: dict[str, list[Cause]], key: str, cause: Cause) -> None:
        if str(cause) not in table.setdefault(key, []):
            table[key].append(cause)

    def accept(source: str) -> str:
        return f"/speckit-eil-accept {known[source][0]}" if source in known else "Correct the trace"

    for key, (stage, block) in known.items():
        if stage not in DERIVED:
            continue
        info = statuses.get(stage, {}).get(key)
        if info is not None and (info.stale or info.status == SOURCE_CHANGED):
            found = False
            for source in _sources_moved(package, stage, key, hashes):
                if source not in known:
                    add(hard, key, Cause(f"{source} no longer exists", "Restore it, or re-derive without it"))
                elif known[source][0] not in DERIVED:
                    found = True
                    if source in approved:
                        add(soft, key, Cause(f"{source} changed and was accepted"))
                    else:
                        add(hard, key, Cause(f"{source} changed", accept(source)))
                elif statuses[known[source][0]][source].status == SETTLED and not statuses[known[source][0]][source].stale:
                    found = True
                    add(soft, key, Cause(f"{source} changed"))
            for source in block.traces:
                if source in known and known[source][0] not in DERIVED and source not in approved:
                    found = True
                    add(hard, key, Cause(f"{source} is not approved", accept(source)))
            if not found and not any(s in known and known[s][0] in DERIVED for s in block.traces):
                add(hard, key, Cause("a source it traces to is not settled"))
        if _pending(block):
            add(hard, key, Cause(f"{key} is a pending clarification", f"/speckit-eil-resolve {key}"))
    for key, (stage, block) in known.items():
        if stage not in DERIVED:
            continue
        for source in block.traces:
            owner = known.get(source)
            source_info = statuses.get(owner[0], {}).get(source) if owner and owner[0] in DERIVED else None
            if source_info is not None and source_info.status == NEEDS_REVIEW:
                add(
                    hard,
                    key,
                    Cause(
                        f"{source} is inferred and has not been reviewed",
                        f"Review {source} (eil review list --stage {owner[0]} --kind inferred)",  # type: ignore[index]
                    ),
                )
    for key in sorted(_cycle_members({k: [t for t in v if t in known] for k, v in edges.items()})):
        add(hard, key, Cause("it is part of a tracing cycle", "Remove one of the traces that form the cycle"))
    for code, message in problems(package):
        if code == "dangling-trace":
            add(hard, message.split(" ", 1)[0], Cause(message, "Correct the id or remove the trace"))
    for stage in package.existing_stages():
        for key in conflicted_keys(package, stage):
            add(hard, key, Cause("its recorded answers conflict", "A configured confirmer resolves the conflict"))
    from .corrections import blocked_keys

    for key, cr_id in blocked_keys(package).items():
        if key in known and known[key][0] in DERIVED:
            add(hard, key, Cause(f"{cr_id} is open and corrects or reaches {key}", f"Confirm {cr_id} (/speckit-eil-accept)"))
    changed = True
    while changed:
        changed = False
        for key, (stage, block) in known.items():
            if stage not in DERIVED:
                continue
            for source in block.traces:
                if source not in known or known[source][0] not in DERIVED:
                    continue
                if source in hard:
                    cause = Cause(f"{source} is blocked ({hard[source][0]})", f"Clear {source} first: {hard[source][0].fix}")
                elif source in soft:
                    cause = Cause(f"{source} must be re-derived first", f"Re-derive {source} first")
                else:
                    continue
                if str(cause) not in hard.get(key, []):
                    add(hard, key, cause)
                    changed = True
    blocked = {k: [*v, *soft.get(k, [])] for k, v in sorted(hard.items())}
    rederive = {k: v for k, v in sorted(soft.items()) if k not in hard}
    return blocked, rederive


def rows(blocked: dict[str, list[Cause]]) -> list[dict[str, Any]]:
    """The ``blocked[]`` shape of ``enter`` and ``status``: ``{id, because[], fix}``."""
    return [
        {
            "id": key,
            "because": [str(c) for c in causes],
            "fix": "; ".join(dict.fromkeys(c.fix for c in causes if c.fix)),
        }
        for key, causes in blocked.items()
    ]


def blocked_work(package: Package) -> dict[str, list[Cause]]:
    """``{block key: [causes]}`` for the work that may not proceed (see ``scoped_work``)."""
    return scoped_work(package)[0]


# ---- task snapshots


def task_closure(package: Package, key: str) -> dict[str, str]:
    """``{id: current hash}`` of everything ``key`` traces to, directly or not."""
    known = _blocks(package)
    hashes = package.current_item_hashes()
    edges = {k: list(b.traces) for k, (_, b) in known.items()}
    return {i: hashes[i] for i in sorted(_reachable(key, edges)) if i in hashes}


def is_ticked(block: Block) -> bool:
    return bool(_TICKED.match(block.text))


def sync_task_snapshots(package: Package) -> dict[str, Any]:
    """Record ``completed_against`` the first time a task is seen ticked, and clear it when it is
    unticked. ``blocked_at_completion`` says the task was blocked when it was ticked (FR-005)."""
    result: dict[str, Any] = {"snapshotted": [], "completed_while_blocked": [], "cleared": []}
    if not package.exists("tasks"):
        return result
    doc = package.doc("tasks")
    read = package.record_read("tasks", "provenance")
    if read.error:
        return result
    record = read.obj if read.obj is not None else (adopt(package, "tasks") or {"version": 1, "blocks": {}})
    record.setdefault("blocks", {})
    blocked_now, again = scoped_work(package)
    blocked = {**blocked_now, **again}
    dirty = False
    for block in blocks_of(doc):
        if block.kind != "task":
            continue
        entry = record["blocks"].get(block.key)
        if not isinstance(entry, dict):
            continue
        if is_ticked(block) and "completed_against" not in entry:
            entry["completed_against"] = task_closure(package, block.key)
            entry["blocked_at_completion"] = block.key in blocked
            result["snapshotted"].append(block.key)
            if block.key in blocked:
                result["completed_while_blocked"].append(block.key)
            dirty = True
        elif not is_ticked(block) and "completed_against" in entry:
            del entry["completed_against"]
            entry.pop("blocked_at_completion", None)
            result["cleared"].append(block.key)
            dirty = True
    if dirty:
        try:
            package.write_record("tasks", "provenance", record)
        except RegionError:
            return result
    return result


def settled_keys(package: Package, stage: str) -> set[str]:
    return {k for k, i in block_statuses(package).get(stage, {}).items() if i.status == SETTLED}


def touched_artifacts(package: Package) -> dict[str, str]:
    """``{ART id: why}`` for the approved artefacts implementation may have made out of date: reached, directly
    or through other items, by a task that carries code, or changed since the approval that covered them
    (research D-41; FR-033)."""
    from . import impact, verification
    from .trace import parse_document

    arts = verification.approved_artifact_ids(package)
    out: dict[str, str] = {}
    if not arts:
        return out
    if package.exists("tasks"):
        known = _blocks(package)
        edges = {k: list(b.traces) for k, (_, b) in known.items()}
        wanted = set(arts)
        for task in parse_document(package.doc("tasks")).tasks:
            if task.code:
                for art in sorted(_reachable(task.id, edges) & wanted):
                    out.setdefault(art, f"{task.id} carries code that reaches it")
    current = package.current_item_hashes()
    for stage in verification.DEFINITION_STAGES:
        approval = impact._approval(package, stage) if package.exists(stage) else None
        recorded = approval.get("items") if approval else None
        if isinstance(recorded, dict):
            for art in arts:
                if art in recorded and current.get(art) != recorded[art]:
                    out.setdefault(art, "changed since the approval that covered it")
    return {art: out[art] for art in arts if art in out}

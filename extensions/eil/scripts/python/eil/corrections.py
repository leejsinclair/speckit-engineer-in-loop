"""Backwards corrections: a problem found downstream is one action with an impact preview and a
recorded origin (research D-38; FR-021 to FR-025).

``propose`` is read-only. ``open`` records ``CR-###`` in the owning stage's provenance region. The AI
never writes the person's wording: ``--wording`` is stored verbatim, and only text equal to it can carry
``(decided: CR-###)``. A correction closes when its owning stage is re-signed with the item covered, or,
for a stage nobody approves, when ``review confirm`` finds the item settled.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from . import clock
from .blockstatus import DERIVED, SETTLED, block_statuses
from .content import blocks_of
from .fingerprint import normalise_fragment
from .identity import is_ai_actor
from .package import STAGES, Package
from .results import Refusal, refuse, usage_error
from .trace import Item, build_graph

if TYPE_CHECKING:
    from .trace import ParseResult

LATER_THAN_STAGES = ("implementation", "code-review")
_CR_NUMBER = re.compile(r"^CR-(\d{3,})$")


def _records(pkg: Package, stage: str) -> list[dict[str, Any]]:
    try:
        obj = pkg.record(stage, "provenance")
    except (OSError, UnicodeDecodeError):
        return []
    found = (obj or {}).get("corrections")
    return [c for c in found if isinstance(c, dict)] if isinstance(found, list) else []


def all_crs(pkg: Package) -> list[tuple[str, dict[str, Any]]]:
    """Every correction of the story with the stage that owns it, in stage order."""
    return [(stage, cr) for stage in pkg.existing_stages() for cr in _records(pkg, stage)]


def find(pkg: Package, cr_id: str) -> tuple[str, dict[str, Any]] | None:
    return next(((s, c) for s, c in all_crs(pkg) if c.get("id") == cr_id), None)


def open_for(pkg: Package, stage: str) -> list[dict[str, Any]]:
    return [c for c in _records(pkg, stage) if c.get("status") == "open"]


def open_all(pkg: Package) -> list[tuple[str, dict[str, Any]]]:
    return [(s, c) for s, c in all_crs(pkg) if c.get("status") == "open"]


def next_id(pkg: Package) -> str:
    highest = 0
    for _, cr in all_crs(pkg):
        match = _CR_NUMBER.match(str(cr.get("id", "")))
        if match:
            highest = max(highest, int(match[1]))
    return f"CR-{highest + 1:03d}"


def _words(text: str) -> str:
    return " ".join(text.split())


def same_text(wording: str, item_text: str) -> bool:
    """Whitespace-collapsed equality, falling back to the fingerprint's own normalisation."""
    return _words(wording) == _words(item_text) or normalise_fragment(wording) == normalise_fragment(
        item_text
    )


def wording_problem(pkg: Package, cr_id: str, item: Item | None) -> tuple[bool, str | None]:
    """``(exists, why not)``: whether ``cr_id`` is a correction of the story, and why it cannot back a
    ``(decided: ...)`` clause on ``item`` if it cannot."""
    found = find(pkg, cr_id)
    if found is None:
        return False, f"{cr_id} is not a correction of this story"
    cr = found[1]
    if item is not None and cr.get("item") != item.id:
        return True, f"{cr_id} corrects {cr.get('item')}, not {item.id}"
    wording = cr.get("wording")
    if not isinstance(wording, str) or not wording.strip():
        return True, f"{cr_id} has no recorded wording, so it cannot vouch for any text"
    if item is not None and not same_text(wording, item.title):
        return True, f"the text of {item.id} is not the wording recorded in {cr_id}"
    return True, None


# ---- propose and open


def _parse_found_in(found_in: str) -> dict[str, str]:
    stage, _, item = found_in.partition(":")
    if stage not in (*STAGES, *LATER_THAN_STAGES):
        raise usage_error(f"--found-in {found_in!r}: {stage!r} is not a stage, implementation or code-review")
    out = {"stage": stage}
    if item:
        out["item"] = item
    return out


def _locate(pkg: Package, item_id: str) -> tuple[str, Item, ParseResult]:
    from . import impact

    parsed = impact.parsed_story(pkg)
    for stage, result in parsed.items():
        for item in result.items:
            if item.id == item_id:
                return stage, item, result
        for task in result.tasks:
            if task.id == item_id:
                raise refuse(
                    Refusal("unknown-item", f"{item_id} is a task; correct the item it traces to", "")
                )
    raise refuse(
        Refusal("unknown-item", f"{item_id} is not an item of this story", "Name an existing item id")
    )


def propose(pkg: Package, item_id: str, found_in: str, problem: str) -> dict[str, Any]:
    """Owner candidates, whether the choice is ambiguous, and what the change would reach. Writes nothing."""
    from . import impact

    origin = _parse_found_in(found_in)
    defining, item, _ = _locate(pkg, item_id)
    candidates = [defining]
    if defining in DERIVED:
        info = block_statuses(pkg).get(defining, {}).get(item_id)
        if info is not None and info.klass == "restated":
            parsed = impact.parsed_story(pkg)
            for source in item.traces:
                for stage, result in parsed.items():
                    if stage not in candidates and any(i.id == source for i in result.items):
                        candidates.append(stage)
    graph = build_graph(impact.parsed_story(pkg))
    reach = graph.downstream([item_id])
    return {
        "ok": True,
        "item": item_id,
        "found_in": origin,
        "problem": problem,
        "candidates": candidates,
        "ambiguous": len(candidates) > 1,
        "impact": reach,
        "text": (
            f"{item_id} is owned by {' or '.join(candidates)}; correcting it reaches "
            + (", ".join(reach) if reach else "nothing else")
            + "."
        ),
    }


def open_correction(
    pkg: Package,
    item_id: str,
    found_in: str,
    problem: str,
    by: str,
    owner: str | None = None,
    wording: str | None = None,
) -> dict[str, Any]:
    from .provenance import _load_record, _save_record

    if is_ai_actor(by):
        raise refuse(
            Refusal(
                "ai-approval",
                f"{by!r} is the AI; a correction is opened in a person's name",
                "Ask the developer",
            )
        )
    proposal = propose(pkg, item_id, found_in, problem)
    candidates = proposal["candidates"]
    if owner is None and proposal["ambiguous"]:
        raise refuse(
            Refusal(
                "owner-ambiguous",
                f"{item_id} could be corrected in {' or '.join(candidates)}",
                "Ask the person which stage owns it and pass --owner",
            )
        )
    if owner is not None and owner not in candidates:
        raise refuse(
            Refusal(
                "owner-not-candidate",
                f"{owner} is not one of the candidates: {', '.join(candidates)}",
                "Pass one of the candidates as --owner",
            )
        )
    owner = owner or candidates[0]
    cr = {
        "id": next_id(pkg),
        "item": item_id,
        "owner": owner,
        "found_in": proposal["found_in"],
        "problem": problem,
        "wording": wording if wording is not None and wording.strip() else None,
        "impact": proposal["impact"],
        "opened_by": by.strip(),
        "at": clock.utc_now(),
        "status": "open",
    }
    record = _load_record(pkg, owner)
    record.setdefault("corrections", []).append(cr)
    _save_record(pkg, owner, record)
    return {"ok": True, "correction": cr, "text": f"Opened {cr['id']} in {owner} for {item_id}."}


# ---- what an open correction blocks


def blocked_keys(pkg: Package) -> dict[str, str]:
    """``{block key: CR id}`` for the item of every open correction and everything that traces to it."""
    from . import impact

    opened = open_all(pkg)
    if not opened:
        return {}
    graph = build_graph(impact.parsed_story(pkg))
    out: dict[str, str] = {}
    for _, cr in opened:
        item = str(cr.get("item", ""))
        for key in (item, *graph.downstream([item])):
            out.setdefault(key, str(cr["id"]))
    return out


def under_open_correction(pkg: Package, stage: str) -> set[str]:
    """Keys of ``stage``'s blocks whose item is the subject of an open correction."""
    subjects = {str(c.get("item")) for _, c in open_all(pkg)}
    return {b.key for b in blocks_of(pkg.doc(stage)) if b.numbered and b.key in subjects}


# ---- closing


def item_settled(pkg: Package, stage: str, item_id: str) -> bool:
    info = block_statuses(pkg).get(stage, {}).get(item_id)
    return info is not None and info.status == SETTLED and not info.stale


def close(record: dict[str, Any], cr_id: str, by: str, at: str, approval_at: str | None) -> None:
    for cr in record.get("corrections") or []:
        if cr.get("id") == cr_id:
            cr["status"] = "closed"
            cr["closed_by"] = by
            cr["closed_at"] = at
            if approval_at:
                cr["closed_by_approval"] = approval_at

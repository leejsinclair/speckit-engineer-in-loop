"""``eil show``: a stage as a person reads it, in chat (research D-49; FR-012).

The document with every region replaced by its rendered line, HTML comments dropped and fences
kept. After the first line of each block that needs review it prints the review cue ``[ai-draft]``,
which is never written into a document (D-50); before a fenced block that needs review the cue is
a line of its own, so the fence stays intact. ``--items`` prints just those items under their
section headings (an item of an upstream stage is found there); ``--section`` prints one section.

The JSON form also returns each block's key, status and line range in the document, so a prompt can
address a block without opening the file. It reads; it never writes.
"""

from __future__ import annotations

import re
from typing import Any

from . import recordfile
from .blocks import Doc
from .blockstatus import NEEDS_REVIEW, block_statuses
from .content import Block, blocks_of
from .package import RECORD_NAMES, STAGES, Package
from .results import Refusal, refuse
from .trace import decision_fields, is_ai_decided

CUE = "[ai-draft]"
_OLD_TAG = re.compile(r"[ \t]*\[ai-draft\]")
_HEADING = re.compile(r"^\s{0,3}(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_CLAUSE = re.compile(r"\s*\((?:traces|decided|status|material|store):[^)]*\)")


def _title(text: str) -> str:
    return " ".join(_CLAUSE.sub("", text).split()).casefold()


def record_line(kind: str, obj: dict[str, Any] | None) -> str:
    """One readable line for an ``eil:<kind>`` record block (a challenge, an override, an export...)."""
    if not isinstance(obj, dict):
        return f"(an unreadable eil:{kind} record)"
    get = obj.get
    if kind == "challenge":
        state = get("status", "open")
        answer = f"; {get('response')} by {get('responder')}" + (f": {get('reason')}" if get("reason") else "") if get("response") else ""
        return f"{get('id')} ({state}, {get('severity', 'medium')}, on {get('target')}, raised by {get('raised_by')}): {get('text')}{answer}"
    if kind == "override":
        return f"{get('id')}: {get('criterion')} overridden by {get('by')} on {str(get('at', ''))[:10]}: {get('reason')}"
    if kind == "abbreviation":
        return f"Abbreviated, authorised by {get('by')} on {str(get('at', ''))[:10]}: {get('reason')}"
    if kind == "artifact":
        source = get("source") if isinstance(get("source"), dict) else {}
        return (
            f"Export {get('file')} ({get('kind')}, from {source.get('tool')}, exported {source.get('exported_at')} "
            f"by {source.get('exported_by')})"
        )
    if kind == "review":
        return f"{get('id')}: {get('unit')} {get('target')} reviewed by {get('by')} on {str(get('at', ''))[:10]}"
    return f"(eil:{kind} record {get('id', '')})".replace(" )", ")")


def view_lines(
    pkg: Package, stage: str, doc: Doc, cues: set[int], fence_cues: set[int], notes: dict[int, str] | None = None
) -> list[tuple[int, str]]:
    """``[(document line number, text)]`` of the clean view (region bodies rendered, comments gone).
    ``notes`` adds a note after the cue of a block's first line (why a reopened block is back, 004)."""
    notes = notes or {}
    region_at = {r.begin_no: r for r in doc.regions.values()}
    record_at = {r.open_no: r for r in doc.records()}
    decided = {
        b.first_line
        for b in blocks_of(doc)
        if b.item is not None and b.item.kind == "DEC" and is_ai_decided(decision_fields(b.item).get("owner"))
    }
    out: list[tuple[int, str]] = []
    skip_to = 0
    for line in doc.lines:
        if line.no <= skip_to:
            continue
        record = record_at.get(line.no)
        if record is not None:
            skip_to = record.close_no or line.no
            if line.no in fence_cues:
                out.append((line.no, f"{CUE} {notes[line.no]}" if line.no in notes else CUE))
            out.append((line.no, record_line(record.kind, record.obj)))
            continue
        region = region_at.get(line.no)
        if region is not None:
            skip_to = region.end_no
            if region.name in RECORD_NAMES:
                body = recordfile.render(region.name, pkg.record(stage, region.name))
            else:  # the Change Log table is already readable
                body = [ln.raw for ln in doc.lines[region.begin_no : region.end_no - 1]]
            out += [(line.no, text) for text in body]
            continue
        if line.kind == "comment":
            continue
        if line.kind in ("fence-open", "fence-body", "fence-close"):
            if line.no in fence_cues:
                out.append((line.no, f"{CUE} {notes[line.no]}" if line.no in notes else CUE))
            out.append((line.no, line.raw))
            continue
        text = _OLD_TAG.sub("", line.live).rstrip()  # the cue comes from status, never from a tag in the text
        if not text and line.raw.strip():
            continue  # a line that only held a comment
        if line.no in decided:
            text = f"{text} [ai-decided]"
        if line.no in cues:
            text = f"{text} {CUE}"
            if line.no in notes:
                text = f"{text} {notes[line.no]}"
        out.append((line.no, text))
    return out


def reopen_notes(pkg: Package, stage: str, blocks: list[Block]) -> dict[int, str]:
    """``{first line: "(reopened by NAME: COMMENT)"}`` for each block a comment reopened (004 D-65)."""
    recorded = (pkg.record(stage, "provenance") or {}).get("blocks") or {}
    out = {}
    for block in blocks:
        mark = (recorded.get(block.key) or {}).get("reopened") if isinstance(recorded.get(block.key), dict) else None
        if isinstance(mark, dict):
            out[block.first_line] = f"(reopened by {mark.get('by')}: {' '.join(str(mark.get('comment', '')).split())})"
    return out


def _collapse(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    kept: list[tuple[int, str]] = []
    for no, text in lines:
        if not text.strip() and (not kept or not kept[-1][1].strip()):
            continue
        kept.append((no, text))
    while kept and not kept[-1][1].strip():
        kept.pop()
    return kept


def _cues(blocks: list[Block], statuses: dict[str, Any]) -> tuple[set[int], set[int]]:
    lines, fences = set(), set()
    for block in blocks:
        info = statuses.get(block.key)
        if info is not None and info.status == NEEDS_REVIEW:
            (fences if block.kind == "fence" else lines).add(block.first_line)
    return lines, fences


def _row(block: Block, statuses: dict[str, Any]) -> dict[str, Any]:
    info = statuses.get(block.key)
    return {
        "key": block.key,
        "status": info.status if info is not None else NEEDS_REVIEW,
        "first_line": block.first_line,
        "last_line": block.last_line,
    }


def _unknown(what: str, stage: str) -> Any:
    return refuse(Refusal("unknown-item", f"{what} is not in {stage} or an earlier stage", "Use an id from `eil blocks list`, or a section heading of the stage"))


def view(pkg: Package, stage: str, items: list[str] | None = None, section: str | None = None) -> dict[str, Any]:
    if stage not in STAGES or not pkg.exists(stage):
        raise refuse(Refusal("unknown-stage", f"{stage!r} has no document in this story", f"Use one of: {', '.join(STAGES)}"))
    statuses_all = block_statuses(pkg)
    if items:
        return _items(pkg, stage, items, statuses_all)
    doc = pkg.doc(stage)
    blocks = blocks_of(doc)
    statuses = statuses_all.get(stage, {})
    cues, fence_cues = _cues(blocks, statuses)
    lines = view_lines(pkg, stage, doc, cues, fence_cues, reopen_notes(pkg, stage, blocks))
    rows = [_row(b, statuses) for b in blocks]
    if section is not None:
        lines, rows = _section(doc, lines, rows, section, stage)
    text = "\n".join(t for _, t in _collapse(lines))
    return {"ok": True, "stage": stage, "text": text, "blocks": rows}


def _section(
    doc: Doc, lines: list[tuple[int, str]], rows: list[dict[str, Any]], name: str, stage: str
) -> tuple[list[tuple[int, str]], list[dict[str, Any]]]:
    wanted = _title(name)
    heads = [
        (line.no, len(m["hashes"]), _title(m["title"]))
        for line in doc.lines
        if line.kind == "text" and (m := _HEADING.match(line.live))
    ]
    for index, (no, level, title) in enumerate(heads):
        if title != wanted:
            continue
        end = next((n for n, lv, _ in heads[index + 1 :] if lv <= level), len(doc.lines) + 1)
        return (
            [(n, t) for n, t in lines if no <= n < end],
            [r for r in rows if no <= r["first_line"] < end],
        )
    raise _unknown(f"section {name!r}", stage)


def _items(pkg: Package, stage: str, items: list[str], statuses_all: dict[str, Any]) -> dict[str, Any]:
    order = [stage, *reversed([s for s in STAGES[: STAGES.index(stage)] if pkg.exists(s)])]
    out: list[str] = []
    rows: list[dict[str, Any]] = []
    last_heading: tuple[str, str] | None = None
    for item in items:
        found = None
        for owner in order:
            block = next((b for b in blocks_of(pkg.doc(owner)) if b.key == item), None)
            if block is not None:
                found = (owner, block)
                break
        if found is None:
            raise _unknown(item, stage)
        owner, block = found
        statuses = statuses_all.get(owner, {})
        doc = pkg.doc(owner)
        cues, fence_cues = _cues([block], statuses)
        shown = view_lines(pkg, owner, doc, cues, fence_cues, reopen_notes(pkg, owner, [block]))
        heading = (owner, block.section)
        if heading != last_heading:
            if out:
                out.append("")
            prefix = f"({owner}) " if owner != stage else ""
            out += [f"## {prefix}{block.section}" if block.section else f"## ({owner})", ""]
            last_heading = heading
        else:
            out.append("")
        out += [t for n, t in shown if block.first_line <= n <= block.last_line]
        rows.append(_row(block, statuses))
    return {"ok": True, "stage": stage, "text": "\n".join(out).rstrip("\n"), "blocks": rows}


__all__ = ["CUE", "view", "view_lines"]

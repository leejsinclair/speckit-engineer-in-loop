"""Content blocks: the unit of review and of staleness (FR-039, research D-31).

``blocks_of(doc)`` walks a stage document outside marked regions, ``eil:`` record blocks, HTML
comments and administrative sections, and returns its blocks in document order:

* a heading ends the current block and is not itself a block;
* an item line, a task line, or a plan heading carrying ``(traces: ...)`` is a numbered block (an
  item with its continuation lines, an ART with its attachment; a plan heading with its section);
* a fence not attached to an ART is one block, and so is a table;
* any other run of non-blank lines is one block.

A block's hash (a task's ignores its checkbox and code references) is the text with ``[ai-draft]`` and ``[pending-clarification]`` removed and whitespace
normalised. For a numbered item it equals ``trace.item_hash``. Its key is its id, ``§`` plus a plan
heading, or ``<section>#<first 12 hex digits of the hash>``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .blocks import Doc, Line
from .fingerprint import hash_fragment
from .trace import (
    _CLAUSE,
    _HEADING,
    _ID,
    _ITEM_PREFIX,
    _TAG,
    ADMINISTRATIVE_SECTIONS,
    Item,
    item_hash,
    parse_document,
)

_HEADING_TITLE = re.compile(r"^\s{0,3}(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")


@dataclass
class Block:
    key: str
    hash: str
    kind: str  # item | task | plan | fence | table | prose
    section: str
    first_line: int
    last_line: int
    text: str
    id: str | None = None  # the item or task id of a numbered block
    traces: list[str] = field(default_factory=list)  # an item's traces, or a prose block's citation
    item: Item | None = None

    @property
    def numbered(self) -> bool:
        return self.kind in ("item", "task", "plan")


_CHECKBOX = re.compile(r"^(\s*-\s+\[)[ xX](\])")


def task_hash(line: str) -> str:
    """A task's identity ignores its checkbox and its code references: ticking a task, or recording the
    commit that carries it, is not a change to what the task says."""
    plain = _CHECKBOX.sub(r"\1 \2", line)
    plain = _CLAUSE.sub(lambda m: "" if m["name"] == "code" else m[0], plain)
    return hash_fragment(_TAG.sub("", plain))


def cited_ids(text: str) -> list[str]:
    """The ids in the ``(traces: ...)`` clause on the last line of ``text`` (a prose block's citation)."""
    last = next((row for row in reversed(text.splitlines()) if row.strip()), "")
    for match in _CLAUSE.finditer(last):
        if match["name"] == "traces":
            return [p for p in (part.strip() for part in match["value"].split(",")) if _ID.match(p)]
    return []


def blocks_of(doc: Doc) -> list[Block]:
    """The blocks of ``doc``, in document order. Computed once per ``Doc``."""
    cached = doc.__dict__.get("_eil_blocks")
    if cached is None:
        cached = _walk(doc)
        doc.__dict__["_eil_blocks"] = cached
    return cached


def _skipped(doc: Doc) -> set[int]:
    skip: set[int] = set()
    for region in doc.regions.values():
        skip.update(range(region.begin_no, region.end_no + 1))
    for fence in doc.fences:
        if fence.info.startswith("eil:"):
            skip.update(range(fence.open_no, (fence.close_no or fence.open_no) + 1))
    administrative = False
    for line in doc.lines:
        heading = _HEADING_TITLE.match(line.live) if line.kind == "text" else None
        if heading and len(heading["hashes"]) <= 2:
            administrative = (
                len(heading["hashes"]) == 2
                and " ".join(heading["title"].split()).casefold() in ADMINISTRATIVE_SECTIONS
            )
        if administrative:
            skip.add(line.no)
    return skip


def _attached_fences(doc: Doc, items: dict[int, Item], task_lines: set[int]) -> set[int]:
    """Open lines of the fences that are an ART's attachment; also sets ``Item.attachment``."""
    attached: set[int] = set()
    fences = {f.open_no: f for f in doc.fences}
    current: Item | None = None
    taken = False
    for line in doc.lines:
        if line.no in items:
            current, taken = (items[line.no] if items[line.no].kind == "ART" else None), False
        elif line.no in task_lines or (
            line.kind == "text" and (_HEADING.match(line.live) or _ITEM_PREFIX.match(line.live))
        ):
            current = None
        elif line.no in fences:
            fence = fences[line.no]
            if (
                (fence.language == "mermaid" or fence.info.split()[:1] == ["eil:artifact"])
                and current
                and not taken
            ):
                current.attachment = "\n".join(fence.body)
                attached.add(line.no)
                taken = True
    return attached


def _make(
    kind: str,
    lines: list[Line],
    section: str,
    *,
    key: str | None = None,
    text: str | None = None,
    hashed: str | None = None,
    id: str | None = None,
    traces: list[str] | None = None,
    item: Item | None = None,
) -> Block:
    body = text if text is not None else "\n".join(line.live for line in lines).strip("\n")
    digest = hashed if hashed is not None else hash_fragment(_TAG.sub("", body))
    return Block(
        key=key or f"{section}#{digest[len('sha256:') : len('sha256:') + 12]}",
        hash=digest,
        kind=kind,
        section=section,
        first_line=lines[0].no,
        last_line=lines[-1].no,
        text=body,
        id=id,
        traces=traces if traces is not None else cited_ids(body),
        item=item,
    )


def _walk(doc: Doc) -> list[Block]:
    parsed = parse_document(doc)
    items = {item.line: item for item in parsed.items}
    tasks = {task.line: task for task in parsed.tasks}
    skip = _skipped(doc)
    attached = _attached_fences(doc, items, set(tasks))
    fences = {f.open_no: f for f in doc.fences}
    lines = doc.lines
    out: list[Block] = []
    run: list[Line] = []
    section = ""

    def flush() -> None:
        if run:
            out.append(_make("prose", list(run), section))
            run.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.no in skip or line.kind == "comment":
            flush()
            continue
        if line.kind == "fence-open":
            flush()
            fence = fences[line.no]
            end = fence.close_no or lines[-1].no
            span = lines[line.no - 1 : end]
            i = end
            if line.no not in attached:
                out.append(_make("fence", span, section, text="\n".join(x.raw for x in span)))
            continue
        if line.kind != "text":
            continue
        text = line.live
        heading = _HEADING_TITLE.match(text)
        if heading:
            flush()
            if len(heading["hashes"]) <= 2:
                section = " ".join(_TAG.sub("", _CLAUSE.sub("", heading["title"])).split())
            if any(m["name"] == "traces" for m in _CLAUSE.finditer(text)) and len(heading["hashes"]) >= 2:
                body = [line]
                while i < len(lines) and not (
                    lines[i].kind == "text" and _HEADING_TITLE.match(lines[i].live)
                ):
                    if lines[i].no not in skip:
                        body.append(lines[i])
                    i += 1
                while len(body) > 1 and not body[-1].live.strip():
                    body.pop()
                title = " ".join(_TAG.sub("", _CLAUSE.sub("", heading["title"])).split())
                out.append(_make("plan", body, title, key=f"§{title}", traces=cited_ids(text)))
            continue
        if line.no in items:
            flush()
            item = items[line.no]
            span = lines[line.no - 1 : item.end_line]
            i = item.end_line
            out.append(
                _make(
                    "item", span, section, key=item.id, text=item.text, hashed=item_hash(item), id=item.id,
                    traces=list(item.traces), item=item,
                )
            )  # fmt: skip
            continue
        if line.no in tasks:
            flush()
            task = tasks[line.no]
            out.append(
                _make(
                    "task",
                    [line],
                    section,
                    key=task.id,
                    id=task.id,
                    traces=list(task.traces),
                    hashed=task_hash(line.live),
                )  # fmt: skip
            )
            continue
        if not text.strip():
            flush()
            continue
        if text.lstrip().startswith("|"):
            flush()
            table = [line]
            while (
                i < len(lines)
                and lines[i].kind == "text"
                and lines[i].no not in skip
                and lines[i].live.lstrip().startswith("|")
            ):
                table.append(lines[i])
                i += 1
            out.append(_make("table", table, section))
            continue
        run.append(line)
    flush()
    return out

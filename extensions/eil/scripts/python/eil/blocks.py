"""Read and write the machine-readable parts of a stage document (task T020).

A stage document is ordinary Markdown. Only four things in it are interpreted (contracts/
document-format.md): item lines (see ``trace``), record blocks (```` ```eil:<kind> ````), marked
regions (``<!-- eil:begin <name> -->`` ... ``<!-- eil:end <name> -->``) and tags.

``Doc`` scans a document once, in a single pass that tracks code fences and HTML comments together
(which one wins depends on which opens first). Fences inside comments are ignored, which is what
lets the templates carry commented example items. Comment markers inside a fence are literal text.

Edits are byte preserving: unchanged lines are never touched, and a rewrite uses the document's
own newline style.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .results import Finding

REGION_NAMES = ("approval", "assessment", "comprehension")

_FENCE_OPEN = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_FENCE_CLOSE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})\s*$")
_MARKER = re.compile(r"^\s*<!--\s*eil:(?P<edge>begin|end)\s+(?P<name>[a-z]+)\s*-->\s*$")


class RegionError(Exception):
    """A marked region is malformed, so it cannot be safely rewritten."""


def dumps(obj: Any) -> str:
    """The one JSON layout the helper writes: two-space indent, non-ASCII kept readable."""
    return json.dumps(obj, indent=2, ensure_ascii=False)


@dataclass
class Line:
    no: int  # 1-based
    raw: str  # without the line ending
    live: str  # raw with HTML comments blanked out (fence lines are unchanged)
    kind: str  # text | comment | fence-open | fence-body | fence-close


@dataclass
class Fence:
    info: str
    open_no: int
    close_no: int | None
    body: list[str]
    body_start: int

    @property
    def language(self) -> str:
        return self.info.split()[0] if self.info.split() else ""


@dataclass
class Record:
    kind: str
    obj: dict[str, Any] | None
    error: str | None
    open_no: int
    close_no: int | None
    body_start: int


@dataclass
class Region:
    name: str
    begin_no: int
    end_no: int


@dataclass
class RegionRead:
    obj: dict[str, Any] | None
    error: str | None = None


@dataclass
class Doc:
    text: str
    path: str = ""
    lines: list[Line] = field(default_factory=list)
    fences: list[Fence] = field(default_factory=list)
    regions: dict[str, Region] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    _region_problem: bool = False

    def __post_init__(self) -> None:
        self._scan_lines()
        self._scan_regions()
        self._check_records()

    # ---- location helper

    def where(self, line_no: int) -> str:
        return f"{self.path}:{line_no}" if self.path else f"line:{line_no}"

    # ---- scanning

    def _scan_lines(self) -> None:
        in_comment = False
        open_fence: tuple[str, int, Fence] | None = None
        for no, piece in enumerate(self.text.split("\n"), start=1):
            raw = piece.rstrip("\r")
            if open_fence is not None:
                char, length, fence = open_fence
                close = _FENCE_CLOSE.match(raw)
                if close and close["fence"][0] == char and len(close["fence"]) >= length:
                    fence.close_no = no
                    self.lines.append(Line(no, raw, raw, "fence-close"))
                    open_fence = None
                else:
                    fence.body.append(raw)
                    self.lines.append(Line(no, raw, raw, "fence-body"))
                continue
            if not in_comment:
                opened = _FENCE_OPEN.match(raw)
                if opened and not (opened["fence"][0] == "`" and "`" in opened["info"]):
                    fence = Fence(opened["info"].strip(), no, None, [], no + 1)
                    self.fences.append(fence)
                    open_fence = (opened["fence"][0], len(opened["fence"]), fence)
                    self.lines.append(Line(no, raw, raw, "fence-open"))
                    continue
                if _MARKER.match(raw):
                    self.lines.append(Line(no, raw, raw, "text"))
                    continue
            live, in_comment, was_all_comment = self._blank_comments(raw, in_comment)
            self.lines.append(Line(no, raw, live, "comment" if was_all_comment else "text"))
        for fence in self.fences:
            if fence.close_no is None:
                self.findings.append(
                    Finding("malformed-fence", self.where(fence.open_no), "code fence is never closed")
                )

    @staticmethod
    def _blank_comments(raw: str, in_comment: bool) -> tuple[str, bool, bool]:
        out: list[str] = []
        i = 0
        saw_live = False
        while i < len(raw):
            if in_comment:
                j = raw.find("-->", i)
                if j == -1:
                    i = len(raw)
                    break
                in_comment = False
                i = j + 3
                out.append(" ")
            else:
                j = raw.find("<!--", i)
                if j == -1:
                    chunk = raw[i:]
                    saw_live = saw_live or bool(chunk.strip())
                    out.append(chunk)
                    break
                chunk = raw[i:j]
                saw_live = saw_live or bool(chunk.strip())
                out.append(chunk)
                in_comment = True
                i = j + 4
        return "".join(out), in_comment, (not saw_live and (in_comment or "<!--" in raw or "-->" in raw))

    def _scan_regions(self) -> None:
        current: tuple[str, int] | None = None
        for line in self.lines:
            m = _MARKER.match(line.raw)
            if not m or m["name"] not in REGION_NAMES:
                continue
            name, edge = m["name"], m["edge"]
            if edge == "begin":
                if current is not None:
                    self._region_finding(line.no, f"region '{name}' begins inside region '{current[0]}'")
                    continue
                if name in self.regions:
                    self._region_finding(line.no, f"region '{name}' is defined more than once")
                current = (name, line.no)
            else:
                if current is None:
                    self._region_finding(line.no, f"end marker for '{name}' has no begin marker")
                elif current[0] != name:
                    self._region_finding(line.no, f"end marker for '{name}' closes region '{current[0]}'")
                    current = None
                else:
                    self.regions.setdefault(name, Region(name, current[1], line.no))
                    current = None
        if current is not None:
            self._region_finding(current[1], f"region '{current[0]}' is never closed")

    def _region_finding(self, line_no: int, message: str) -> None:
        self._region_problem = True
        self.findings.append(Finding("malformed-region", self.where(line_no), message))

    def _check_records(self) -> None:
        for record in self.records():
            if record.error:
                self.findings.append(
                    Finding(
                        "malformed-record",
                        self.where(record.open_no),
                        f"eil:{record.kind} block: {record.error}",
                    )
                )

    # ---- fences and records

    def fences_with_info(self, language: str) -> list[Fence]:
        return [f for f in self.fences if f.language == language]

    def records(self) -> list[Record]:
        found: list[Record] = []
        for fence in self.fences:
            if not fence.info.startswith("eil:"):
                continue
            kind = fence.info[4:].split()[0] if fence.info[4:].split() else ""
            obj, error = _parse_object("\n".join(fence.body))
            found.append(Record(kind, obj, error, fence.open_no, fence.close_no, fence.body_start))
        return found

    # ---- regions

    def read_region(self, name: str) -> RegionRead:
        region = self.regions.get(name)
        if region is None:
            if self._region_problem and self._marker_present(name):
                return RegionRead(None, f"region '{name}' is malformed")
            return RegionRead(None)
        for fence in self.fences:
            if (
                fence.language == "json"
                and region.begin_no < fence.open_no
                and (fence.close_no or 10**9) < region.end_no
            ):
                obj, error = _parse_object("\n".join(fence.body))
                return RegionRead(obj, error)
        return RegionRead(None)

    def _marker_present(self, name: str) -> bool:
        return any((m := _MARKER.match(line.raw)) and m["name"] == name for line in self.lines)


def _parse_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    if not text.strip():
        return None, "empty JSON"
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON ({exc.msg} at line {exc.lineno})"
    if not isinstance(value, dict):
        return None, "JSON must be an object"
    return value, None


# ---- editing


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def write_region(text: str, name: str, obj: Any, heading: str | None = None) -> str:
    """Replace the body of region ``name`` (or append the region), changing nothing else."""
    doc = Doc(text)
    if doc._region_problem:
        raise RegionError("the document has a malformed region; fix it before writing")
    body = ["```json", *dumps(obj).split("\n"), "```"]
    region = doc.regions.get(name)
    nl = _newline(text)
    if region is None:
        lines = [] if text == "" else ([text] if text.endswith("\n") else [text + nl])
        lead = ["", heading] if heading else [""]
        block = [*lead, f"<!-- eil:begin {name} -->", *body, f"<!-- eil:end {name} -->"]
        return "".join(lines) + nl.join(block) + nl
    pieces = text.split("\n")
    suffix = "\r" if nl == "\r\n" else ""
    pieces[region.begin_no : region.end_no - 1] = [line + suffix for line in body]
    return "\n".join(pieces)


def replace_record(text: str, record: Record, obj: Any) -> str:
    """Rewrite one record block's JSON in place, changing nothing else."""
    if record.close_no is None:
        raise ValueError("cannot rewrite a record block that is never closed")
    pieces = text.split("\n")
    suffix = "\r" if _newline(text) == "\r\n" else ""
    pieces[record.body_start - 1 : record.close_no - 1] = [line + suffix for line in dumps(obj).split("\n")]
    return "\n".join(pieces)


_HEADING_LINE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")


def append_record(text: str, heading: str, kind: str, obj: Any, default_level: int = 2) -> str:
    """Add an ``eil:<kind>`` record block at the end of the section titled ``heading``.

    The section is created at the end of the document if it does not exist. Every other byte of
    the document is left as it was.
    """
    doc = Doc(text)
    nl = _newline(text)
    suffix = "\r" if nl == "\r\n" else ""
    block = ["", f"```eil:{kind}", *dumps(obj).split("\n"), "```"]
    block = [line + suffix if line else suffix for line in block]
    wanted = " ".join(heading.split()).casefold()
    heads = []
    for index, line in enumerate(doc.lines):
        match = _HEADING_LINE.match(line.live) if line.kind == "text" else None
        if match:
            heads.append((index, len(match["hashes"]), " ".join(match["title"].split()).casefold()))
    pieces = text.split("\n")
    for position, (index, level, title) in enumerate(heads):
        if title != wanted:
            continue
        end = len(pieces)
        for later_index, later_level, _ in heads[position + 1 :]:
            if later_level <= level:
                end = later_index
                break
        last = max((i for i in range(index, end) if pieces[i].strip()), default=index)
        pieces[last + 1 : last + 1] = block
        return "\n".join(pieces)
    tail = "" if text.endswith("\n") or text == "" else nl
    heading_line = "#" * default_level + " " + heading
    return text + tail + nl + heading_line + nl + nl.join(line.rstrip("\r") for line in block[1:]) + nl


def insert_record_after(text: str, line_no: int, kind: str, obj: Any) -> str:
    """Insert an ``eil:<kind>`` block directly after line ``line_no`` (1-based), changing nothing else."""
    nl = _newline(text)
    suffix = "\r" if nl == "\r\n" else ""
    block = ["", f"```eil:{kind}", *dumps(obj).split("\n"), "```"]
    pieces = text.split("\n")
    pieces[line_no:line_no] = [line + suffix for line in block]
    return "\n".join(pieces)

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

REGION_NAMES = ("approval", "assessment", "comprehension", "provenance", "changelog")

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
        self._check_provenance()

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

    def _check_provenance(self) -> None:
        if "provenance" not in self.regions:
            return
        problem = self.read_provenance().error
        if problem:
            self.findings.append(
                Finding("malformed-provenance", self.where(self.regions["provenance"].begin_no), problem)
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

    def read_provenance(self) -> RegionRead:
        """The provenance record, checked against the allowed keys (contracts/document-format.md).
        An unreadable or non-conforming region has ``obj`` ``None`` and an ``error`` (``malformed-provenance``)."""
        read = self.read_region("provenance")
        if read.error or read.obj is None:
            return read
        problems = provenance_problems(read.obj)
        if problems:
            return RegionRead(None, "; ".join(problems[:3]))
        return read

    def region_lines(self, name: str) -> list[str]:
        """The non-blank lines of region ``name``'s body (its rendered line, or a 002 JSON body)."""
        region = self.regions.get(name)
        if region is None:
            return []
        return [line.raw for line in self.lines[region.begin_no : region.end_no - 1] if line.raw.strip()]

    def region_is_json(self, name: str) -> bool:
        """Whether region ``name`` still holds a JSON body (a document not yet migrated, D-48)."""
        read = self.read_region(name)
        return read.obj is not None or read.error is not None and name in self.regions

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


# ---- the provenance record: allowed keys only

PROVENANCE_KEYS = frozenset(
    {"version", "currency", "blocks", "acceptances", "corrections", "changes", "conflicts"}
)
BLOCK_KEYS = frozenset(
    {
        "hash", "class", "cites", "adds", "reviewed", "sources", "completed_against", "blocked_at_completion", "basis",
        "reopened",  # 004 D-65: a person commented on the settled block; it needs review again
    }
)  # fmt: skip
REVIEWED_KEYS = frozenset({"by", "at", "list", "reply"})
REOPENED_KEYS = frozenset({"by", "at", "list", "comment", "via"})
ACCEPTANCE_KEYS = frozenset(
    {
        "id", "stage", "kind", "digest", "by", "at", "reply", "accepted", "except", "questioned",
        "reopened", "deferred", "reason", "resolved_conflict", "hashes", "summaries", "mode", "unseen",
        # 004 D-63, D-70: answered on the page, with the fixed questions, comments and sections accepted together
        "via", "questions", "comments", "together",
    }
)  # fmt: skip
CORRECTION_KEYS = frozenset(
    {
        "id", "item", "owner", "found_in", "problem", "wording", "impact", "opened_by", "at", "status",
        "closed_by_approval", "closed_by", "closed_at",
    }
)  # fmt: skip
FOUND_IN_KEYS = frozenset({"stage", "item"})
CHANGE_KEYS = frozenset({"at", "item", "summary", "summary_by", "origin", "accepted_by"})
CONFLICT_KEYS = frozenset({"key", "hash", "answers"})
BLOCK_CLASSES = ("restated", "decided", "inferred", "adopted", "adopted-pending")


def _extra(where: str, obj: Any, allowed: frozenset[str]) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{where} must be an object"]
    return [f"{where} has unknown key {key!r}" for key in obj if key not in allowed]


def provenance_problems(obj: Any) -> list[str]:
    """Every way ``obj`` departs from the provenance grammar; empty means it conforms."""
    problems = _extra("provenance", obj, PROVENANCE_KEYS)
    if not isinstance(obj, dict):
        return problems
    blocks = obj.get("blocks", {})
    if not isinstance(blocks, dict):
        problems.append("blocks must be an object")
        blocks = {}
    for key, entry in blocks.items():
        where = f"blocks.{key}"
        problems += _extra(where, entry, BLOCK_KEYS)
        if not isinstance(entry, dict):
            continue
        if "class" in entry and entry["class"] not in BLOCK_CLASSES:
            problems.append(f"{where}.class {entry['class']!r} is not one of {', '.join(BLOCK_CLASSES)}")
        if entry.get("reviewed") is not None:
            problems += _extra(f"{where}.reviewed", entry["reviewed"], REVIEWED_KEYS)
        if entry.get("reopened") is not None:
            problems += _extra(f"{where}.reopened", entry["reopened"], REOPENED_KEYS)
    for name, allowed in (
        ("acceptances", ACCEPTANCE_KEYS),
        ("corrections", CORRECTION_KEYS),
        ("changes", CHANGE_KEYS),
        ("conflicts", CONFLICT_KEYS),
    ):
        rows = obj.get(name, [])
        if not isinstance(rows, list):
            problems.append(f"{name} must be a list")
            continue
        for index, row in enumerate(rows):
            problems += _extra(f"{name}[{index}]", row, allowed)
            if name == "corrections" and isinstance(row, dict) and row.get("found_in") is not None:
                problems += _extra(f"{name}[{index}].found_in", row["found_in"], FOUND_IN_KEYS)
    return problems


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


# Where a record's region goes when a document does not have it yet.
REGION_HEADINGS = {
    "approval": "## Approval",
    "assessment": "## Quality Assessment",
    "comprehension": "## Comprehension Check",
}


def ensure_region(text: str, name: str) -> str:
    """``text`` with an empty region ``name`` added under its usual heading if it has none."""
    if name == "provenance":
        return ensure_record_sections(text)
    doc = Doc(text)
    if doc._region_problem:
        raise RegionError("the document has a malformed region; fix it before writing")
    if name in doc.regions:
        return text
    nl = _newline(text)
    lines = [] if text == "" else ([text] if text.endswith("\n") else [text + nl])
    block = ["", REGION_HEADINGS[name], f"<!-- eil:begin {name} -->", f"<!-- eil:end {name} -->"]
    return "".join(lines) + nl.join(block) + nl


def set_region_lines(text: str, name: str, body: list[str]) -> str:
    """Replace the body of region ``name`` with ``body`` (rendered Markdown lines), changing nothing else.
    The region must exist."""
    doc = Doc(text)
    if doc._region_problem:
        raise RegionError("the document has a malformed region; fix it before writing")
    region = doc.regions[name]
    suffix = "\r" if _newline(text) == "\r\n" else ""
    pieces = text.split("\n")
    pieces[region.begin_no : region.end_no - 1] = [line + suffix for line in body]
    return "\n".join(pieces)


_AI_DRAFT = re.compile(r"[ \t]*\[ai-draft\]")


def strip_ai_draft(text: str) -> str:
    """``text`` with every ``[ai-draft]`` tag outside HTML comments removed (003 D-50). The tag is
    fingerprint- and hash-neutral (002 D-23), so removing it changes no approval and no status."""
    out: list[str] = []
    in_comment = False
    for piece in text.split("\n"):
        kept: list[str] = []
        i = 0
        while i < len(piece):
            if in_comment:
                end = piece.find("-->", i)
                if end == -1:
                    kept.append(piece[i:])
                    break
                kept.append(piece[i : end + 3])
                i, in_comment = end + 3, False
                continue
            start = piece.find("<!--", i)
            if start == -1:
                kept.append(_AI_DRAFT.sub("", piece[i:]))
                break
            kept.append(_AI_DRAFT.sub("", piece[i:start]) + "<!--")
            i, in_comment = start + 4, True
        out.append("".join(kept))
    return "\n".join(out)


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


# ---- the Change Log and Record sections (contracts/document-format.md §Marked regions)

_CHANGELOG_HEAD = (
    "| Date | Item | Change (AI-drafted, accepted as shown) | Found in | Accepted by |",
    "|---|---|---|---|---|",
)


def _cell(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).replace("|", "\\|")


def render_changelog(changes: list[dict[str, Any]], corrections: list[dict[str, Any]] | None = None) -> list[str]:
    """The table lines for ``changes``, oldest first, or no lines when there are none."""
    if not changes:
        return []
    by_id = {c.get("id"): c for c in corrections or [] if isinstance(c, dict)}
    rows = list(_CHANGELOG_HEAD)
    for change in changes:
        origin = str(change.get("origin") or "")
        found = by_id.get(origin, {}).get("found_in") if origin.startswith("CR-") else None
        where = (
            f"{found.get('stage')} ({found.get('item')}), {origin}"
            if isinstance(found, dict)
            else origin
        )
        cells = [
            str(change.get("at") or "")[:10],
            change.get("item"),
            change.get("summary"),
            where,
            change.get("accepted_by"),
        ]
        rows.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return rows


def _h2_index(doc: Doc, titles: tuple[str, ...]) -> int | None:
    """0-based index of the first ``##`` heading whose title is in ``titles`` (compared casefolded)."""
    for index, line in enumerate(doc.lines):
        match = _HEADING_LINE.match(line.live) if line.kind == "text" else None
        if match and len(match["hashes"]) == 2 and " ".join(match["title"].split()).casefold() in titles:
            return index
    return None


def ensure_record_sections(text: str) -> str:
    """Add ``## Change Log`` (with its empty region) just before ``## Record`` (with its empty
    provenance region), and ``## Record`` just before ``## Comprehension Check`` or ``## Quality
    Assessment``, whichever comes first, or at the end. Whatever already exists is left alone."""
    doc = Doc(text)
    if doc._region_problem:
        raise RegionError("the document has a malformed region; fix it before writing")
    has_log, has_record = "changelog" in doc.regions, "provenance" in doc.regions
    if has_log and has_record:
        return text
    nl = _newline(text)
    suffix = "\r" if nl == "\r\n" else ""
    log = ["## Change Log", "", "<!-- eil:begin changelog -->", "<!-- eil:end changelog -->", ""]
    record = ["## Record", "", "<!-- eil:begin provenance -->", "<!-- eil:end provenance -->", ""]
    pieces = text.split("\n")
    if has_record:  # the log goes just above the Record heading, or above the provenance marker
        at = doc.regions["provenance"].begin_no - 1
        heading = _h2_index(doc, ("record",))
        if heading is not None and heading < at:
            at = heading
        pieces[at:at] = [line + suffix for line in log]
        return "\n".join(pieces)
    if has_log:  # the Record goes just below the log region
        at = doc.regions["changelog"].end_no
        pieces[at:at] = [line + suffix for line in ["", *record[:-1]]]
        return "\n".join(pieces)
    block = [*log, *record]
    at = _h2_index(doc, ("comprehension check", "quality assessment"))
    if at is None:
        tail = "" if text == "" or text.endswith("\n") else nl
        return text + tail + ("" if text == "" else nl) + nl.join(block) + nl
    pieces[at:at] = [line + suffix for line in block]
    return "\n".join(pieces)


def write_provenance(text: str, obj: dict[str, Any]) -> str:
    """Write the provenance record, placing the Change Log and Record sections on first write.
    Refuses an ``obj`` that would itself be ``malformed-provenance``."""
    problems = provenance_problems(obj)
    if problems:
        raise RegionError("; ".join(problems[:3]))
    return write_region(ensure_record_sections(text), "provenance", obj)


def write_changelog(text: str, changes: list[dict[str, Any]], corrections: list[dict[str, Any]] | None = None) -> str:
    """Rewrite the ``changelog`` region from ``changes`` (a generated table, never parsed)."""
    text = ensure_record_sections(text)
    doc = Doc(text)
    region = doc.regions["changelog"]
    nl = _newline(text)
    suffix = "\r" if nl == "\r\n" else ""
    pieces = text.split("\n")
    pieces[region.begin_no : region.end_no - 1] = [line + suffix for line in render_changelog(changes, corrections)]
    return "\n".join(pieces)

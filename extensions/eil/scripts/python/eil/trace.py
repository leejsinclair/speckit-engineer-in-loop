"""Item parsing and item hashing (task T022).

An item is a line defining an id (research D-10). This module parses them, their trailing clauses
and tags, and Spec Kit task lines; it reports every line that looks like an item but does not
parse as a finding, never silently (risk R-5). Chain traversal, coverage and impact come later.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .blocks import Doc
from .fingerprint import hash_fragment
from .results import Finding

KINDS = ("REQ", "UC", "FR", "NFR", "DEC", "AIS", "EVD", "OQ", "OVR", "CH", "ART")
_KIND_ALT = "|".join(KINDS)

ITEM_LINE = re.compile(
    rf"^\s*(?:[-*]\s+)?\*\*(?P<kind>{_KIND_ALT})-(?P<num>\d{{3}})\*\*\s*[:.]\s*(?P<rest>.+)$"
)
_ITEM_PREFIX = re.compile(rf"^\s*(?:[-*]\s+)?\*\*(?:{_KIND_ALT})-")
TASK_LINE = re.compile(r"^\s*-\s+\[(?P<done>[ xX])\]\s+(?P<id>T\d{3,})\b(?P<rest>.*)$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")

DECISION_FIELDS = ("decision", "reason", "rejected alternative", "trade-off", "owner")
_DEC_LABEL = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?(?P<label>Decision|Reason|Rejected alternatives?|Trade-?offs?|Owner)"
    r"(?:\*\*)?\s*:\s*(?:\*\*)?\s*(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
EVIDENCE_FIELDS = ("kind", "evidence", "accepted by", "reason")
_EVD_LABEL = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?(?P<label>Kind|Evidence|Accepted by|Reason)"
    r"(?:\*\*)?\s*:\s*(?:\*\*)?\s*(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
_CLAUSE = re.compile(r"\((?P<name>traces|code|status|material|store|accepted-by):\s*(?P<value>[^)]*)\)")
_TAG = re.compile(r"\s*\[(?P<tag>ai-draft|pending-clarification)\]")
_ID = re.compile(r"^(?:[A-Z]{2,3}-\d{3}|T\d{3,})$")  # an item id, or a task id (evidence traces to tasks)
_CODE_REF = re.compile(r"^(?:[0-9a-f]{7,40}|PR#\d+)$")
_STATUSES = ("open", "resolved", "accepted", "verified", "failed", "unverified", "excepted")


@dataclass
class Item:
    id: str
    kind: str
    number: int
    title: str
    line: int
    end_line: int
    text: str  # the defining line and its continuation lines, raw
    traces: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
    status: str | None = None
    material: bool | None = None
    store: str | None = None
    accepted_by: str | None = None
    tags: set[str] = field(default_factory=set)
    attachment: str | None = None  # an ART's diagram or export record, set by ``artifacts``


@dataclass
class Task:
    id: str
    line: int
    done: bool
    text: str
    traces: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)  # the commits and pull requests that carry it


@dataclass
class ParseResult:
    items: list[Item] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def _clauses(text: str) -> dict[str, str]:
    return {m["name"]: m["value"].strip() for m in _CLAUSE.finditer(text)}


def _code_refs(value: str, where: str, findings: list[Finding]) -> list[str]:
    refs: list[str] = []
    for ref in (p.strip() for p in value.split(",")):
        if _CODE_REF.match(ref):
            refs.append(ref)
        else:
            findings.append(Finding("malformed-item", where, f"code reference {ref!r} is not a sha or PR#n"))
    return refs


def code_matches(ref: str, wanted: str) -> bool:
    """A commit matches by prefix in either direction (at least seven digits); a pull request only exactly."""
    if ref.startswith("PR#") or wanted.startswith("PR#"):
        return ref == wanted
    a, b = ref.lower(), wanted.lower()
    return a.startswith(b) or b.startswith(a)


def _split_ids(value: str, where: str, label: str, findings: list[Finding]) -> list[str]:
    ids: list[str] = []
    for part in (p.strip() for p in value.split(",")):
        if _ID.match(part):
            ids.append(part)
        else:
            findings.append(Finding("malformed-item", where, f"{label} reference {part!r} is not an item id"))
    return ids


def parse_document(doc: Doc) -> ParseResult:
    """The items, tasks and findings of a document. Parsed once per ``Doc``; callers read the result."""
    cached = doc.__dict__.get("_eil_parsed")
    if cached is not None:
        return cached
    result = _parse(doc)
    doc.__dict__["_eil_parsed"] = result
    return result


def _parse(doc: Doc) -> ParseResult:
    result = ParseResult()
    lines = doc.lines
    seen: dict[str, int] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.kind != "text":
            continue
        text = line.live
        where = doc.where(line.no)
        task = TASK_LINE.match(text)
        if task:
            clauses = _clauses(text)
            traces = (
                _split_ids(clauses["traces"], where, "traces", result.findings) if "traces" in clauses else []
            )
            entry = Task(task["id"], line.no, task["done"] != " ", text.strip(), traces)
            if "code" in clauses:
                entry.code = _code_refs(clauses["code"], where, result.findings)
            result.tasks.append(entry)
            continue
        match = ITEM_LINE.match(text)
        if not match:
            if _ITEM_PREFIX.match(text):
                result.findings.append(
                    Finding(
                        "malformed-item",
                        where,
                        f"line starts like an item but is not **KIND-000**: text ({text.strip()[:60]!r})",
                    )
                )
            continue
        item_id = f"{match['kind']}-{match['num']}"
        block = [text]
        end_line = line.no
        while i < len(lines):
            nxt = lines[i]
            if nxt.kind != "text" or _ends_item(nxt.live):
                break
            if not nxt.live.strip():
                if match["kind"] == "DEC" and _decision_continues(block, lines, i):
                    block.append("")
                    i += 1
                    continue
                break
            block.append(nxt.live)
            end_line = nxt.no
            i += 1
        joined = "\n".join(block)
        item = _build_item(
            item_id, match["kind"], int(match["num"]), match["rest"], joined, line.no, end_line, where, result
        )
        if item_id in seen:
            result.findings.append(
                Finding(
                    "duplicate-id", item_id, f"{item_id} is defined at lines {seen[item_id]} and {line.no}"
                )
            )
        else:
            seen[item_id] = line.no
        result.items.append(item)
    return result


def _ends_item(text: str) -> bool:
    return bool(_HEADING.match(text) or _ITEM_PREFIX.match(text) or TASK_LINE.match(text))


def _decision_continues(block: list[str], lines: list[Any], index: int) -> bool:
    """A decision's fields may be separated by blank lines, as in the standard's own example: the
    item goes on if the next text is another field, or the value of a label that is still empty."""
    j = index
    while j < len(lines) and lines[j].kind == "text" and not lines[j].live.strip():
        j += 1
    if j >= len(lines) or lines[j].kind != "text" or _ends_item(lines[j].live):
        return False
    if _DEC_LABEL.match(lines[j].live):
        return True
    last = next((row for row in reversed(block) if row.strip()), "")
    labelled = _DEC_LABEL.match(last)
    return bool(labelled and not labelled["value"])


def evidence_fields(item: Item) -> dict[str, str]:
    """The labelled lines of an ``EVD`` row (FR-059 to FR-061): kind, evidence, accepted by and reason."""
    fields: dict[str, str] = {}
    for row in item.text.splitlines()[1:]:
        labelled = _EVD_LABEL.match(row)
        if labelled:
            fields[labelled["label"].lower()] = labelled["value"]
    return fields


def decision_fields(item: Item) -> dict[str, str]:
    """The labelled fields of a ``DEC`` item (FR-032, FR-033): decision, reason, rejected alternative,
    trade-off and owner. A field whose label is present but has no text is returned empty."""
    fields: dict[str, str] = {}
    current: str | None = None
    for row in item.text.splitlines()[1:]:
        labelled = _DEC_LABEL.match(row)
        if labelled:
            label = labelled["label"].lower()
            current = (
                "rejected alternative"
                if label.startswith("rejected")
                else "trade-off"
                if label.startswith("trade")
                else label
            )
            fields[current] = labelled["value"]
        elif current is not None and row.strip():
            fields[current] = (fields[current] + " " + row.strip()).strip()
    return fields


def _build_item(
    item_id: str,
    kind: str,
    number: int,
    rest: str,
    joined: str,
    line: int,
    end_line: int,
    where: str,
    result: ParseResult,
) -> Item:
    clauses = _clauses(joined)
    findings = result.findings
    tags = {m["tag"] for m in _TAG.finditer(joined)}
    item = Item(item_id, kind, number, "", line, end_line, joined, tags=tags)
    if "traces" in clauses:
        item.traces = _split_ids(clauses["traces"], where, "traces", findings)
    if "code" in clauses:
        item.code = _code_refs(clauses["code"], where, findings)
    if "status" in clauses:
        if clauses["status"] in _STATUSES:
            item.status = clauses["status"]
        else:
            findings.append(
                Finding("malformed-item", where, f"status {clauses['status']!r} is not one of {_STATUSES}")
            )
    if "material" in clauses:
        if clauses["material"] in ("yes", "no"):
            item.material = clauses["material"] == "yes"
        else:
            findings.append(
                Finding("malformed-item", where, f"material {clauses['material']!r} is not yes or no")
            )
    if "store" in clauses:
        item.store = clauses["store"]
    if "accepted-by" in clauses:
        item.accepted_by = clauses["accepted-by"] or None
    title = _CLAUSE.sub("", rest)
    title = _TAG.sub("", title)
    item.title = re.sub(r"\s+", " ", title).strip()
    return item


def parse_text(text: str, stage: str | None = None, path: str = "") -> ParseResult:
    return parse_document(Doc(text, path=path))


def item_hash(item: Item) -> str:
    """Hash of the item's normalised text (document-format.md §Item hash).

    Includes the traces clause and, for an artifact, its attachment; excludes the tags.
    """
    body = _TAG.sub("", item.text)
    if item.attachment:
        body += "\n" + item.attachment
    return hash_fragment(body)


def story_findings(parsed: dict[str, ParseResult]) -> list[Finding]:
    """``duplicate-id`` across documents and ``dangling-trace`` (a trace to an id nothing defines)."""
    defined: dict[str, str] = {}
    findings: list[Finding] = []
    for stage, result in parsed.items():
        for item in result.items:
            if item.id in defined and defined[item.id] != stage:
                findings.append(
                    Finding(
                        "duplicate-id", item.id, f"{item.id} is defined in {defined[item.id]} and {stage}"
                    )
                )
            defined.setdefault(item.id, stage)
        for task in result.tasks:
            defined.setdefault(task.id, stage)
    for result in parsed.values():
        for owner in (*result.items, *result.tasks):
            for ref in owner.traces:
                if ref not in defined:
                    findings.append(
                        Finding(
                            "dangling-trace", owner.id, f"{owner.id} traces to {ref}, which nothing defines"
                        )
                    )
    return findings


@dataclass
class Gaps:
    """Where the chain from requirements to functional requirements has holes (FR-025, FR-028)."""

    untraceable: list[str] = field(default_factory=list)  # FR/NFR with no trace to a REQ or UC
    uncovered_requirements: list[str] = field(default_factory=list)  # REQ that no FR/NFR traces to
    uncovered_use_cases: list[str] = field(
        default_factory=list
    )  # UC that no FR/NFR traces to (information only)


def coverage_gaps(requirements: ParseResult, functional: ParseResult) -> Gaps:
    """Gaps in both directions between the requirements and the functional requirements."""
    roots = {i.id for i in requirements.items if i.kind in ("REQ", "UC")}
    derived = [i for i in functional.items if i.kind in ("FR", "NFR")]
    covered = {ref for item in derived for ref in item.traces}
    return Gaps(
        untraceable=[i.id for i in derived if not any(ref in roots for ref in i.traces)],
        uncovered_requirements=[i.id for i in requirements.items if i.kind == "REQ" and i.id not in covered],
        uncovered_use_cases=[i.id for i in requirements.items if i.kind == "UC" and i.id not in covered],
    )


# ---- the chain as a graph (FR-029)


@dataclass
class Node:
    id: str
    kind: str  # an item kind, or ``T`` for a task
    stage: str
    title: str
    traces: list[str]
    code: list[str]


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)  # id -> ids that trace to it

    def downstream(self, starts: list[str]) -> list[str]:
        """Everything that traces to ``starts``, directly or not, in discovery order (excluding them)."""
        return self._walk(starts, lambda i: self.children.get(i, []))

    def upstream(self, starts: list[str]) -> list[str]:
        """Everything ``starts`` trace to, directly or not, that is defined (excluding them)."""
        found = self._walk(starts, lambda i: self.nodes[i].traces if i in self.nodes else [])
        return [i for i in found if i in self.nodes]

    @staticmethod
    def _walk(starts: list[str], step: Callable[[str], list[str]]) -> list[str]:
        seen = set(starts)
        order: list[str] = []
        queue = list(starts)
        while queue:
            for nxt in step(queue.pop(0)):
                if nxt not in seen:
                    seen.add(nxt)
                    order.append(nxt)
                    queue.append(nxt)
        return order

    def with_code(self, wanted: str) -> list[str]:
        return [n.id for n in self.nodes.values() if any(code_matches(c, wanted) for c in n.code)]


def build_graph(parsed: dict[str, ParseResult]) -> Graph:
    """The graph of every item and task; ``parsed`` is in stage order."""
    graph = Graph()
    for stage, result in parsed.items():
        for item in result.items:
            graph.nodes.setdefault(
                item.id, Node(item.id, item.kind, stage, item.title, item.traces, item.code)
            )
        for task in result.tasks:
            graph.nodes.setdefault(task.id, Node(task.id, "T", stage, task.text, task.traces, task.code))
    for node in graph.nodes.values():
        for ref in node.traces:
            graph.children.setdefault(ref, []).append(node.id)
    return graph

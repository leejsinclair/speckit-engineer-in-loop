"""Tracing the chain in both directions, and checking it (task T103; FR-024, FR-028 to FR-030,
FR-040, FR-045, FR-068).

Requirement -> functional requirement -> decision -> AI Specification item -> task -> code change ->
verification evidence, with artefacts as a side branch. Nothing here writes a file.
"""

from __future__ import annotations

from typing import Any

from . import corrections, overview
from .gates import PENDING
from .package import Package
from .trace import Graph, ParseResult, build_graph, coverage_gaps, parse_document, story_findings

# Kinds in the order the chain runs; a chain gap is a rank that nothing reaches.
RANK = {"REQ": 0, "UC": 0, "FR": 1, "NFR": 1, "DEC": 2, "AIS": 3, "T": 4, "EVD": 5}
NEXT_LINK = {
    1: "no functional requirement traces to {id}",
    2: "no technical decision traces to a functional requirement of {id}",
    3: "no AI Specification item traces to {id}",
    4: "no task traces to {id}",
}
NO_CODE = "no code change is linked (code: <sha or PR#n>)"
NO_EVIDENCE = "no verification evidence (FR-030)"


class UnknownReference(ValueError):
    """The id, commit or pull request named is not in the story."""


def _parsed(pkg: Package) -> dict[str, ParseResult]:
    found: dict[str, ParseResult] = {}
    for stage in pkg.existing_stages():
        try:
            found[stage] = parse_document(pkg.doc(stage))
        except UnicodeDecodeError:
            continue
    return found


def _resolve(graph: Graph, ref: str) -> list[str]:
    if ref in graph.nodes:
        return [ref]
    carriers = graph.with_code(ref)
    if not carriers:
        raise UnknownReference(
            f"{ref!r} is neither an item of this story nor a commit or pull request on a task"
        )
    return carriers


def _row(graph: Graph, node_id: str) -> dict[str, Any]:
    node = graph.nodes[node_id]
    row = {"id": node.id, "kind": node.kind, "stage": node.stage, "title": node.title}
    if node.code:
        row["code"] = node.code
    return row


def _context(pkg: Package) -> dict[str, Any]:
    from .package import reached_of

    model = overview.collect(pkg)
    approvals = [
        {"stage": stage, "by": state.approval.get("by"), "at": state.approval.get("at"), "reached": reached_of(state.approval)}
        for stage, state in model.states.items()
        if state.state == "approved" and state.approval
    ]
    return {
        "profile": model.profile,
        "approvals": approvals,
        "overrides": model.overrides,
        "abbreviated": model.abbreviated,
        "accepted_risks": model.accepted_risks,
    }


def _forward_gaps(graph: Graph, start: str, reached: list[str]) -> list[str]:
    node = graph.nodes[start]
    rank = RANK.get(node.kind, 0)
    members = [start, *reached]
    kinds = {RANK[graph.nodes[i].kind] for i in members if graph.nodes[i].kind in RANK}
    gaps: list[str] = []
    for level in range(rank + 1, 5):
        if level not in kinds:
            gaps.append(NEXT_LINK[level].format(id=start))
            return gaps  # what follows cannot exist either; report the first break
    if not any(graph.nodes[i].code for i in members):
        gaps.append(NO_CODE)
    if 5 not in kinds:
        gaps.append(NO_EVIDENCE)
    return gaps


def _reverse_gaps(graph: Graph, start: str, reached: list[str]) -> list[str]:
    if any(graph.nodes[i].kind in ("REQ", "UC") for i in [start, *reached]):
        return []
    if not graph.nodes[start].traces:
        return [f"{start} traces to nothing, so no requirement is reached"]
    return [f"the chain from {start} does not reach a requirement"]


def trace(pkg: Package, from_id: str | None = None, to_ref: str | None = None) -> dict[str, Any]:
    """The chain forward from an item or a change (``from_id``) or back from one (``to_ref``)."""
    graph = build_graph(_parsed(pkg))
    forward = from_id is not None
    starts = _resolve(graph, from_id if forward else to_ref or "")
    reached: list[str] = []
    gaps: list[str] = []
    for start in starts:
        steps = graph.downstream([start]) if forward else graph.upstream([start])
        reached += [i for i in steps if i not in reached and i not in starts]
        for gap in _forward_gaps(graph, start, steps) if forward else _reverse_gaps(graph, start, steps):
            if gap not in gaps:
                gaps.append(gap)
    result: dict[str, Any] = {
        "ok": True,
        "direction": "forward" if forward else "reverse",
        "start": starts,
        "chain": [_row(graph, i) for i in reached],
        "gaps": gaps,
        **_context(pkg),
    }
    on_chain = {*starts, *reached}
    result["corrections"] = [
        {k: cr.get(k) for k in ("id", "item", "owner", "found_in", "problem", "status")}
        for _, cr in corrections.all_crs(pkg)
        if cr.get("item") in on_chain
    ]
    result["text"] = _render(result)
    return result


def _render(result: dict[str, Any]) -> str:
    lines = [f"{result['direction'].capitalize()} chain from {', '.join(result['start'])}:"]
    lines += [f"  {r['id']:<8} {r['stage']:<13} {r['title'][:70]}" for r in result["chain"]] or [
        "  (nothing)"
    ]
    lines += [f"Gap: {g}" for g in result["gaps"]]
    for c in result.get("corrections", []):
        found = c.get("found_in") or {}
        origin = ", ".join(str(v) for v in (found.get("stage"), found.get("item")) if v)
        lines.append(f"Correction {c['id']} of {c['item']} ({c['status']}, found in {origin})")
    lines += [
        f"Override {o['id']}: {o['criterion']} in {o['stage']} by {o['by']}" for o in result["overrides"]
    ]
    lines += [f"Abbreviated: {a['stage']} (authorised by {a['by']})" for a in result["abbreviated"]]
    lines += [f"Accepted risk {r['id']} ({r['by']}, {r['stage']})" for r in result["accepted_risks"]]
    return "\n".join(lines)


# ---- the whole story, one row per requirement

LINKS = (
    ("functional", ("FR", "NFR"), "functional"),
    ("decisions", ("DEC",), "technical"),
    ("ai_spec", ("AIS",), "ai-spec"),
    ("tasks", ("T",), "tasks"),
)


def report(pkg: Package) -> dict[str, Any]:
    parsed = _parsed(pkg)
    graph = build_graph(parsed)
    rows: list[dict[str, Any]] = []
    for item in parsed["requirements"].items if "requirements" in parsed else []:
        if item.kind != "REQ":
            continue
        reached = graph.downstream([item.id])
        members = [graph.nodes[i] for i in reached]
        row: dict[str, Any] = {"id": item.id, "title": item.title}
        ends_at: str | None = None
        for key, kinds, stage in LINKS:
            row[key] = [n.id for n in members if n.kind in kinds]
            if not row[key] and ends_at is None:
                ends_at = stage
        row["artifacts"] = [n.id for n in members if n.kind == "ART"]
        row["code"] = sorted({c for n in members for c in n.code})
        row["evidence"] = [n.id for n in members if n.kind == "EVD"]
        if ends_at is None and not row["code"]:
            ends_at = "tasks"
        if ends_at is None and not row["evidence"]:
            ends_at = "verification"
        row["complete"] = ends_at is None
        row["ends_at"] = ends_at
        rows.append(row)
    return {"ok": True, "requirements": rows, **_context(pkg)}


# ---- the chain check (FR-068)


def check(pkg: Package) -> dict[str, Any]:
    """Gaps across the whole chain, in the order the chain runs, with ``T-`` ids for ``analyze``."""
    parsed = _parsed(pkg)
    found: list[tuple[str, str, str]] = []  # (severity, where, message)
    if "requirements" in parsed and "functional" in parsed:
        gaps = coverage_gaps(parsed["requirements"], parsed["functional"])
        found += [("HIGH", i, f"{i} traces to no requirement or use case") for i in gaps.untraceable]
        found += [("HIGH", i, f"{i} has no functional requirement") for i in gaps.uncovered_requirements]
    for stage, result in parsed.items():
        for item in result.items:
            if item.kind == "DEC" and not any(r.startswith(("FR-", "NFR-")) for r in item.traces):
                found.append(("HIGH", item.id, f"{item.id} traces to no FR or NFR"))
            elif item.kind == "AIS" and PENDING in item.tags:
                found.append(
                    ("HIGH", item.id, f"{item.id} is a pending clarification and has no approved source")
                )
            elif item.kind == "AIS" and not item.traces:
                found.append(("HIGH", item.id, f"{item.id} traces to no approved source"))
            elif item.kind == "ART" and not item.traces:
                found.append(
                    ("MEDIUM", item.id, f"{item.id} traces to nothing (artefacts trace like any item)")
                )
        for task in result.tasks:
            if not any(r.startswith(("AIS-", "DEC-")) for r in task.traces):
                found.append(("MEDIUM", task.id, f"{task.id} traces to no AIS item or approved decision"))
        del stage
    found += [("HIGH", f.where, f.message) for f in story_findings(parsed) if f.code == "dangling-trace"]
    rows = [
        {"id": f"T-{n:03d}", "severity": severity, "where": where, "message": message}
        for n, (severity, where, message) in enumerate(dict.fromkeys(found), 1)
    ]
    text = (
        "\n".join(f"{r['id']} {r['severity']} {r['where']}: {r['message']}" for r in rows)
        or "The chain is complete."
    )
    return {"ok": not rows, "gaps": rows, "text": text}

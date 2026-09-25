"""What an upstream change reaches (task T103; FR-043, FR-044).

An approval records the hash of every item it covered. An item whose current hash differs from the
recorded one, or that is new or gone, is *changed*; everything that traces to it, directly or through
other items, is *affected*. The stage-level rule (any upstream change makes a later approval need
review) is derived in ``package``; this names the items, so a reviewer knows where to look.

Formatting is not a change (the fingerprint and the item hash ignore it), and nothing here reads a
clock or a path, so a clone elsewhere reports the same.
"""

from __future__ import annotations

from .artifacts import scan_document
from .package import Package
from .trace import ParseResult, build_graph, item_hash, parse_document

DEFINITION = ("requirements", "functional", "technical")


def _parsed(pkg: Package) -> dict[str, ParseResult]:
    parsed: dict[str, ParseResult] = {}
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        parsed[stage] = parse_document(doc)
        scan_document(doc, stage, parsed[stage])  # attaches diagrams and exports so hashes cover them
    return parsed


def changed_items(pkg: Package, parsed: dict[str, ParseResult]) -> list[str]:
    """Ids whose text differs from what an approval covered, that were added since, or were removed."""
    changed: list[str] = []
    for stage in DEFINITION:
        approval = pkg.state(stage).approval if stage in parsed else None
        recorded = approval.get("items") if approval else None
        if not isinstance(recorded, dict):
            continue
        current = {item.id: item_hash(item) for item in parsed[stage].items}
        changed += [i for i, h in current.items() if recorded.get(i) != h]
        changed += [i for i in recorded if i not in current]
    return changed


def affected(pkg: Package) -> dict[str, list[str]]:
    """``stage -> ids`` of the items that changed or depend on one that did, in document order."""
    parsed = _parsed(pkg)
    changed = changed_items(pkg, parsed)
    if not changed:
        return {}
    graph = build_graph(parsed)
    hit = set(changed) | set(graph.downstream(changed))
    result: dict[str, list[str]] = {}
    for stage, doc in parsed.items():
        ids = [i.id for i in doc.items if i.id in hit] + [t.id for t in doc.tasks if t.id in hit]
        if ids:
            result[stage] = ids
    return result

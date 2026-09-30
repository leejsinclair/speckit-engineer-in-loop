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


def parsed_story(pkg: Package) -> dict[str, ParseResult]:
    """Every existing stage's document, parsed and scanned (diagrams and exports attached)."""
    parsed: dict[str, ParseResult] = {}
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        parsed[stage] = parse_document(doc)
        scan_document(doc, stage, parsed[stage])  # attaches diagrams and exports so hashes cover them
    return parsed


def _approval(pkg: Package, stage: str) -> dict | None:
    """The stage's raw recorded approval, read directly (never through ``Package.state``, which
    this module itself feeds — D-26)."""
    try:
        doc = pkg.doc(stage)
    except (OSError, UnicodeDecodeError):
        return None
    read = doc.read_region("approval")
    return read.obj if not read.error and isinstance(read.obj, dict) else None


def changed_items(pkg: Package, parsed: dict[str, ParseResult]) -> list[str]:
    """Ids whose text differs from what an approval covered, that were added since, or were removed."""
    changed: list[str] = []
    for stage in DEFINITION:
        approval = _approval(pkg, stage) if stage in parsed else None
        recorded = approval.get("items") if approval else None
        if not isinstance(recorded, dict):
            continue
        current = {item.id: item_hash(item) for item in parsed[stage].items}
        changed += [i for i, h in current.items() if recorded.get(i) != h]
        changed += [i for i in recorded if i not in current]
    return changed


def current_item_hashes(pkg: Package, parsed: dict[str, ParseResult] | None = None) -> dict[str, str]:
    """A flat ``{id: item_hash}`` over every item and task of every existing stage, current on disk.

    Used to check a stage's own recorded ``upstream_items`` (D-26): a per-consumer snapshot is
    stage-pairwise correct even across an upstream stage's later, unrelated re-approval, which a
    check against only upstream's *latest* approval baseline (``changed_items`` above) is not.
    ``parsed`` lets a caller that already parsed the story (``Package.parsed_story``, cached) skip
    doing it again.
    """
    parsed = parsed if parsed is not None else parsed_story(pkg)
    hashes: dict[str, str] = {}
    for result in parsed.values():
        hashes.update({item.id: item_hash(item) for item in result.items})
    return hashes


def upstream_item_hashes(pkg: Package, stage: str, parsed: dict[str, ParseResult]) -> dict[str, str]:
    """The current hash of every id that ``stage``'s own items trace to, directly or not, anywhere
    upstream (D-26). Recorded in that stage's approval so a later check is stage-pairwise, not
    dependent on whatever an upstream stage's own approval history says."""
    graph = build_graph(parsed)
    own_ids = [item.id for item in parsed.get(stage, ParseResult()).items]
    closure = set(graph.upstream(own_ids)) - set(own_ids)
    current = current_item_hashes(pkg)
    return {i: current[i] for i in closure if i in current}


def affected(pkg: Package, parsed: dict[str, ParseResult] | None = None) -> dict[str, list[str]]:
    """``stage -> ids`` of the items that changed or depend on one that did, in document order.
    ``parsed`` lets a caller that already parsed the story skip doing it again."""
    parsed = parsed if parsed is not None else parsed_story(pkg)
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

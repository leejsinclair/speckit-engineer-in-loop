"""What the Verification document says about each item (task T112; FR-059 to FR-061, FR-065).

A row is an ``EVD`` item: ``**EVD-001**: summary (traces: FR-001) (status: verified)`` followed by the
labelled lines ``Kind`` (automated or manual), ``Evidence``, and for an exception ``Accepted by`` and
``Reason``. A row covers every id it traces to; a target takes the worst status of its rows.
"""

from __future__ import annotations

from .identity import is_ai_actor
from .package import Package
from .trace import Item, evidence_fields, item_hash, parse_document, review_finding_fields

KINDS = ("automated", "manual")
STATUSES = ("verified", "failed", "unverified", "excepted")
# The worse a status, the higher it ranks when a target has several rows.
_WORST = {"verified": 0, "excepted": 1, "unverified": 2, "failed": 3}
DEFINITION_STAGES = ("requirements", "functional", "technical")


def evidence_rows(pkg: Package) -> list[Item]:
    if not pkg.exists("verification"):
        return []
    try:
        return [i for i in parse_document(pkg.doc("verification")).items if i.kind == "EVD"]
    except UnicodeDecodeError:
        return []


def review_findings(pkg: Package) -> list[Item]:
    if not pkg.exists("verification"):
        return []
    try:
        return [i for i in parse_document(pkg.doc("verification")).items if i.kind == "RF"]
    except UnicodeDecodeError:
        return []


def finding_hashes(pkg: Package) -> dict[str, str]:
    return {i.id: item_hash(i) for i in review_findings(pkg)}


def finding_problems(item: Item, *, needs_correction: bool = False, pkg: Package | None = None) -> list[str]:
    """Why a review finding is still open: it says so, or it is excepted by nobody, or (with
    ``needs_correction``) it is rooted upstream and no correction names it as its origin."""
    fields = review_finding_fields(item)
    problems: list[str] = []
    if item.status == "excepted":
        who = fields.get("accepted by", "")
        if not who:
            problems.append(f"{item.id} is excepted and names no 'Accepted by'")
        elif is_ai_actor(who):
            problems.append(f"{item.id} is accepted by {who!r}, who is the AI; a person accepts an exception")
        if not fields.get("reason"):
            problems.append(f"{item.id} is excepted and gives no 'Reason'")
    elif item.status != "resolved":
        problems.append(f"{item.id} is {item.status or 'open'}")
    root = fields.get("root", "")
    if needs_correction and pkg is not None and root and root.lower() != "implementation":
        from .corrections import all_crs

        if not any((cr.get("found_in") or {}).get("item") == item.id for _, cr in all_crs(pkg)):
            problems.append(
                f"{item.id} is rooted at {root} but no correction names it as its origin "
                f"(eil correct open --found-in code-review:{item.id})"
            )
    return problems


def exception_problems(row: Item) -> list[str]:
    """Why an excepted row does not count: it must say who accepted it, and why (FR-061)."""
    fields = evidence_fields(row)
    who = fields.get("accepted by", "")
    problems = []
    if not who:
        problems.append(f"{row.id} is excepted and names no 'Accepted by'")
    elif is_ai_actor(who):
        problems.append(f"{row.id} is accepted by {who!r}, who is the AI; a person accepts an exception")
    if not fields.get("reason"):
        problems.append(f"{row.id} is excepted and gives no 'Reason'")
    return problems


def effective_status(row: Item) -> str | None:
    """The row's status as it counts: an exception nobody owns is unverified."""
    if row.status not in STATUSES:
        return None
    if row.status == "excepted" and exception_problems(row):
        return "unverified"
    return row.status


def requirement_ids(pkg: Package) -> list[str]:
    if not pkg.exists("requirements"):
        return []
    return [i.id for i in parse_document(pkg.doc("requirements")).items if i.kind == "REQ"]


def functional_ids(pkg: Package) -> list[str]:
    if not pkg.exists("functional"):
        return []
    return [i.id for i in parse_document(pkg.doc("functional")).items if i.kind in ("FR", "NFR")]


def approved_artifact_ids(pkg: Package) -> list[str]:
    """Every ``ART`` of a stage whose approval is current (FR-059)."""
    found: list[str] = []
    for stage in DEFINITION_STAGES:
        if pkg.exists(stage) and pkg.state(stage).state == "approved":
            found += [i.id for i in parse_document(pkg.doc(stage)).items if i.kind == "ART"]
    return found


def statuses(pkg: Package) -> dict[str, str]:
    """``target -> status`` for every requirement, functional requirement and approved artefact.
    A target with no row is ``unverified``."""
    rows = evidence_rows(pkg)
    result: dict[str, str] = {}
    for target in [*requirement_ids(pkg), *functional_ids(pkg), *approved_artifact_ids(pkg)]:
        seen = [s for row in rows if target in row.traces and (s := effective_status(row)) is not None]
        result[target] = max(seen, key=_WORST.__getitem__) if seen else "unverified"
    return result

"""The comprehension check (task T067; FR-087 to FR-094, research D-22).

Before the developer approves Functional or Technical they answer five questions of rising
difficulty about the document's own content. The AI writes and judges the questions; this module
does the parts that must be deterministic and checkable:

* it chooses the *target items* for each level from the document and its approved upstream, by a
  fixed formula, so the same version always gives the same targets on every machine (FR-089);
* it writes and validates the record, which holds outcomes, attempts, item ids, the taker and the
  document fingerprint, and never a question, an answer, a hint or a score (FR-092);
* it says whether the record is current and complete. Approval needs that, not a pass (FR-093).

Whether the AI asks a good question, or the human understood, is beyond what code can verify; the
counts of skipped and revealed levels are carried into the approval record so review can see them.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

from .blocks import Doc, write_region
from .clock import utc_now
from .fingerprint import fingerprint_text
from .identity import Config, confirmer_refusal, is_ai_actor
from .package import DOC_FILES, STAGES, Package
from .results import Refusal, refuse
from .trace import Item, ParseResult, parse_document

if TYPE_CHECKING:
    from .gates import Sections

LEVELS = ("recognise", "explain", "apply", "trace", "evaluate")
OUTCOMES = ("understood", "coached", "revealed", "skipped", "not-applicable")
COUNT_KEYS = ("understood", "coached", "revealed", "skipped", "not_applicable")
ELIGIBLE_STAGES = ("functional", "technical")
CRITERION_FOR = {"functional": "FUN-G16", "technical": "TEC-G19"}
# The stage documents a stage's items may be drawn from besides its own (approved upstream).
UPSTREAM = {"functional": ("requirements",), "technical": ("requirements", "functional")}

_RECORD_KEYS = {"stage", "fingerprint", "taken_by", "started_at", "updated_at", "levels"}
_REQUIRED_KEYS = {"stage", "fingerprint", "taken_by", "levels"}
_LEVEL_KEYS = {"level", "outcome", "attempts", "items", "reason"}
_LIMIT = re.compile(
    r"\d|\b(at most|at least|no more than|no fewer than|within|maximum|minimum|limit|exceed|exceeds|"
    r"less than|greater than|per)\b",
    re.IGNORECASE,
)


# ---- reading a record


def counts(record: dict[str, Any]) -> dict[str, int]:
    """Outcome counts over a record's levels, in the keys the approval record uses."""
    found = dict.fromkeys(COUNT_KEYS, 0)
    for level in record.get("levels", []):
        outcome = str(level.get("outcome", "")).replace("-", "_")
        if outcome in found:
            found[outcome] += 1
    return found


def validate_record(record: Any, stage: str | None = None) -> str | None:
    """Why a comprehension region is malformed, or ``None``. Only the allowed keys pass (FR-092)."""
    if not isinstance(record, dict):
        return "the comprehension record must be a JSON object"
    unknown = set(record) - _RECORD_KEYS
    if unknown:
        return f"unknown key(s) {sorted(unknown)}: a record holds no question, answer, hint or score"
    missing = _REQUIRED_KEYS - set(record)
    if missing:
        return f"missing key(s) {sorted(missing)}"
    if stage is not None and record["stage"] != stage:
        return f"the record is for stage {record['stage']!r}, not {stage!r}"
    if not isinstance(record["levels"], list):
        return "'levels' must be a list"
    for entry in record["levels"]:
        if not isinstance(entry, dict):
            return "each level must be an object"
        extra = set(entry) - _LEVEL_KEYS
        if extra:
            return f"unknown key(s) {sorted(extra)} in a level: a record holds no question, answer, hint or score"
        if entry.get("level") not in LEVELS:
            return f"unknown level {entry.get('level')!r}"
        if entry.get("outcome") not in OUTCOMES:
            return f"unknown outcome {entry.get('outcome')!r}"
        if entry["outcome"] == "not-applicable":
            if not str(entry.get("reason", "")).strip():
                return f"level {entry['level']} is not-applicable and needs a reason"
        elif "reason" in entry:
            return f"level {entry['level']} has a reason but is not not-applicable"
        attempts = entry.get("attempts", 1)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
            return f"level {entry['level']}: attempts must be a whole number"
        items = entry.get("items", [])
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            return f"level {entry['level']}: items must be a list of ids"
    return None


def summarise(record: dict[str, Any] | None, fingerprint: str) -> dict[str, Any]:
    """``missing`` (no record), ``malformed``, ``stale`` (another version), ``incomplete`` or ``complete``."""
    if not record:
        return {"state": "missing"}
    if validate_record(record) is not None:
        return {"state": "malformed"}
    if record.get("fingerprint") != fingerprint:
        return {"state": "stale", "counts": counts(record)}
    present = {level.get("level") for level in record.get("levels", [])}
    state = "complete" if present >= set(LEVELS) else "incomplete"
    return {"state": state, "counts": counts(record)}


# ---- choosing targets (FR-089)


def _pick(fingerprint: str, level: str, attempt: int, eligible: list[str], taken: set[str]) -> str:
    """One id from ``eligible`` (sorted ascending), skipping those already chosen unless none remain."""
    pool = [i for i in eligible if i not in taken] or eligible
    digest = hashlib.sha256(f"{fingerprint}|{level}|{attempt}".encode()).hexdigest()
    return pool[int(digest[:8], 16) % len(pool)]


def eligible_ids(
    stage: str, own: ParseResult, upstream: list[ParseResult], kinds: dict[str, str]
) -> dict[str, list[str]]:
    """The ids each level may ask about (contracts/document-format.md §Question targets)."""
    items = own.items
    up = [i for result in upstream for i in result.items]

    def ids(found: list[Item]) -> list[str]:
        return sorted({i.id for i in found})

    if stage == "functional":
        return {
            "recognise": ids(
                [i for i in items if i.kind in ("FR", "NFR")] + [i for i in up if i.kind == "UC"]
            ),
            "explain": ids([i for i in items if i.kind in ("FR", "NFR")]),
            "apply": ids([i for i in items if i.kind == "FR"] + [i for i in up if i.kind == "UC"]),
            "trace": ids([i for i in items if i.traces]),
            "evaluate": ids(
                [i for i in items if i.kind == "NFR" or (i.kind == "FR" and _LIMIT.search(i.title))]
            ),
        }
    return {
        "recognise": ids([i for i in items if i.kind in ("DEC", "ART")]),
        "explain": ids([i for i in items if i.kind == "DEC"]),
        "apply": ids(
            [
                i
                for i in items
                if i.kind == "DEC" or (i.kind == "ART" and kinds.get(i.id) in ("sequence", "c4-container"))
            ]
        ),
        "trace": ids([i for i in items if i.traces]),
        "evaluate": ids([i for i in items if i.kind == "DEC"]),
    }


def _section_title(sections: Sections, line: int) -> str:
    enclosing = [s for s in sections.sections if s.line < line]
    return enclosing[-1].title if enclosing else ""


class _World:
    """The items of a stage and of its approved upstream, with where each is defined."""

    def __init__(self, pkg: Package, stage: str) -> None:
        from .artifacts import scan_document
        from .gates import Sections

        self.pkg, self.stage = pkg, stage
        self.docs: dict[str, Doc] = {}
        self.parsed: dict[str, ParseResult] = {}
        self.sections: dict[str, Any] = {}
        self.kinds: dict[str, str] = {}
        for name in (*UPSTREAM[stage], stage):
            if not pkg.exists(name):
                continue
            doc = pkg.doc(name)
            self.docs[name] = doc
            self.parsed[name] = parse_document(doc)
            self.sections[name] = Sections(doc)
            for art in scan_document(doc, name, self.parsed[name]).artifacts:
                if art.kind:
                    self.kinds[art.id] = art.kind
        self.home: dict[str, tuple[str, Item]] = {}
        for name, parsed in self.parsed.items():
            for item in parsed.items:
                self.home.setdefault(item.id, (name, item))

    @property
    def own(self) -> ParseResult:
        return self.parsed[self.stage]

    def upstream(self) -> list[ParseResult]:
        return [self.parsed[n] for n in UPSTREAM[self.stage] if n in self.parsed]

    def section_of(self, item_id: str) -> str:
        name, item = self.home[item_id]
        return _section_title(self.sections[name], item.line)

    def chain(self, item_id: str) -> list[str]:
        seen: list[str] = []

        def walk(current: str) -> None:
            if current in seen or current not in self.home:
                return
            seen.append(current)
            for ref in self.home[current][1].traces:
                walk(ref)

        walk(item_id)
        return seen

    def artifacts_tracing(self, item_id: str) -> list[str]:
        return sorted(
            i.id for _, i in self.home.values() if i.kind == "ART" and item_id in i.traces and i.id != item_id
        )


# ---- the operations


def _require_eligible(pkg: Package, stage: str) -> None:
    if stage not in ELIGIBLE_STAGES:
        raise refuse(
            Refusal(
                "stage-not-eligible",
                f"{stage} has no comprehension check; only {' and '.join(ELIGIBLE_STAGES)} do",
                "The check is taken before approving the Functional or Technical Specification",
            )
        )
    if not pkg.exists(stage):
        raise refuse(
            Refusal(
                "stage-not-eligible", f"{stage} has no document yet", f"Start it with: eil stage-init {stage}"
            )
        )


def _require_prerequisites(pkg: Package, stage: str) -> None:
    """Every other criterion met or overridden, and no open challenge (FR-088)."""
    from .gates import check_stage

    problems: list[str] = []
    try:
        result = check_stage(pkg, stage, write=False)
    except NotImplementedError:
        raise refuse(
            Refusal(
                "stage-not-eligible",
                f"no quality gate is defined for {stage} in this version",
                "The check needs the gate",
            )
        ) from None
    ours = CRITERION_FOR[stage]
    problems += [f"{c.id}: {c.reason}" for c in result.unmet() if c.id != ours]
    for record in pkg.doc(stage).records():
        if record.kind == "challenge" and record.obj and record.obj.get("status", "open") != "closed":
            problems.append(f"challenge {record.obj.get('id', '?')} is open")
    if problems:
        raise refuse(
            Refusal(
                "comprehension-prerequisites",
                "the check cannot start yet:\n  " + "\n  ".join(problems),
                "Meet or override the other criteria and answer every open challenge first, so the check is taken on the version to be approved",
            )
        )


def plan(pkg: Package, stage: str, level: str | None = None, attempt: int = 1) -> dict[str, Any]:
    """The target items for each level (or one). Ids and sections only, never a question or answer."""
    _require_eligible(pkg, stage)
    if level is not None and level not in LEVELS:
        raise refuse(
            Refusal("unknown-level", f"{level!r} is not a level", f"Use one of: {', '.join(LEVELS)}")
        )
    _require_prerequisites(pkg, stage)
    fingerprint = pkg.fingerprint(stage) or ""
    world = _World(pkg, stage)
    eligible = eligible_ids(stage, world.own, world.upstream(), world.kinds)
    rows: list[dict[str, Any]] = []
    taken: set[str] = set()
    for name in LEVELS:
        ids = eligible[name]
        if level is not None and name != level:
            continue
        if not ids:
            rows.append({"level": name, "status": "no-material"})
            continue
        target = _pick(fingerprint, name, attempt, ids, taken if level is None else set())
        taken.add(target)
        row: dict[str, Any] = {
            "level": name,
            "status": "ok",
            "target": target,
            "section": world.section_of(target),
        }
        if name == "trace":
            row["chain"] = world.chain(target)
            row["artifacts"] = world.artifacts_tracing(target)
        rows.append(row)
    return {"ok": True, "stage": stage, "fingerprint": fingerprint, "attempt": attempt, "levels": rows}


def record(
    pkg: Package,
    config: Config,
    stage: str,
    level: str,
    outcome: str,
    by: str,
    attempts: int = 1,
    items: list[str] | tuple[str, ...] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    """Write one level's outcome into the ``comprehension`` region, or refuse and write nothing."""
    from .records import approvers_for

    _require_eligible(pkg, stage)
    if level not in LEVELS:
        raise refuse(
            Refusal("unknown-level", f"{level!r} is not a level", f"Use one of: {', '.join(LEVELS)}")
        )
    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(
            Refusal(
                "ai-approval",
                f"{by!r} is the AI; the check must be taken by a person",
                "Only the developer's own answers are recorded",
            )
        )
    problem = confirmer_refusal(by, approvers_for(pkg, config, stage), stage)
    if problem:
        refusals.append(problem)
    if outcome == "not-applicable" and not (reason or "").strip():
        refusals.append(
            Refusal(
                "reason-required",
                "a level recorded as not-applicable needs a reason",
                "Say why the level does not apply (for example: one screen, no trade-off)",
            )
        )
    world = _World(pkg, stage)
    unknown = [i for i in items if i not in world.home]
    if unknown:
        refusals.append(
            Refusal(
                "unknown-item",
                f"not in the document or its approved upstream: {', '.join(unknown)}",
                "Use ids from `eil comprehension plan`",
            )
        )
    if refusals:
        raise refuse(*refusals)
    _require_prerequisites(pkg, stage)

    text = pkg.read(stage)
    if "comprehension" not in Doc(text).regions:
        text = write_region(text, "comprehension", {}, heading="## Comprehension Check")
    fingerprint = fingerprint_text(text)
    now = utc_now()
    existing = Doc(text).read_region("comprehension").obj
    current = (
        bool(existing)
        and validate_record(existing, stage) is None
        and existing.get("fingerprint") == fingerprint
    )
    levels = [dict(entry) for entry in existing["levels"]] if current else []  # type: ignore[index]
    entry: dict[str, Any] = {
        "level": level,
        "outcome": outcome,
        "attempts": int(attempts),
        "items": list(items),
    }
    if outcome == "not-applicable":
        entry["reason"] = (reason or "").strip()
    levels = [e for e in levels if e["level"] != level] + [entry]
    levels.sort(key=lambda e: LEVELS.index(e["level"]))
    saved = {
        "stage": stage,
        "fingerprint": fingerprint,
        "taken_by": by.strip(),
        "started_at": existing["started_at"] if current and "started_at" in existing else now,  # type: ignore[index]
        "updated_at": now,
        "levels": levels,
    }
    error = validate_record(saved, stage)
    if error:  # only reachable through a bug or an out-of-range argument
        raise refuse(Refusal("reason-required", error, "Correct the arguments"))
    pkg.doc_path(stage).write_bytes(write_region(text, "comprehension", saved).encode("utf-8"))
    state = summarise(saved, fingerprint)
    return {
        "ok": True,
        "stage": stage,
        "level": level,
        "record": saved,
        "state": state["state"],
        "counts": state["counts"],
        "text": f"Recorded {level} as {outcome} ({state['state']}).",
    }


__all__ = ["DOC_FILES", "STAGES", "counts", "plan", "record", "summarise", "validate_record"]

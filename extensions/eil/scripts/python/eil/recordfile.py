"""The story's record file, ``eil-record.json`` (research D-48; data-model §Record file).

One file per story directory holds every machine record the helper keeps: per stage, the
``approval``, ``assessment``, ``comprehension`` and ``provenance`` records; per story, how it was
started, its profile and any open review sessions. The stage documents keep only a rendered line
in each region, so a person or an agent reading a document reads content, not bookkeeping.

The file is written with sorted keys and two-space indentation so that a change stays local in a
diff. Only the keys below are allowed: a file that does not conform is ``malformed-record-file``
and is never trusted (FR-011). People do not edit it; a hand edit is detectable, not prevented
(Principle II, R-25).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILE = "eil-record.json"
VERSION = 1
RECORD_NAMES = ("approval", "assessment", "comprehension", "provenance")
TOP_KEYS = frozenset({"version", "story", "stages"})
STORY_KEYS = frozenset({"start", "profile", "review_sessions"})
START_KEYS = frozenset(
    {"at", "branch", "branch_confirmed_by", "previous_pointer", "reply", "question", "note"}
)


@dataclass
class Loaded:
    """The parsed file. ``error`` is set when it exists but cannot be trusted; ``data`` is then empty."""

    data: dict[str, Any]
    error: str | None = None
    exists: bool = False


def path(root: Path) -> Path:
    return Path(root) / FILE


def empty() -> dict[str, Any]:
    return {"version": VERSION, "story": {}, "stages": {}}


def stage_problems(stage: str, name: str, obj: Any) -> list[str]:
    where = f"stages.{stage}.{name}"
    if not isinstance(obj, dict):
        return [f"{where} must be an object"]
    if name == "provenance":
        from .blocks import provenance_problems

        return [f"{where}: {p}" for p in provenance_problems(obj)]
    if name == "comprehension":
        from .comprehension import validate_record

        problem = validate_record(obj, stage)
        return [f"{where}: {problem}"] if problem else []
    if name == "approval" and not isinstance(obj.get("fingerprint"), str):
        return [f"{where} has no fingerprint"]
    return []


def problems(data: Any) -> list[str]:
    """Every way ``data`` departs from the record file's grammar; empty means it conforms."""
    from .package import STAGES

    if not isinstance(data, dict):
        return ["the record file must hold a JSON object"]
    found = [f"unknown key {k!r}" for k in data if k not in TOP_KEYS]
    if data.get("version") != VERSION:
        found.append(f"version must be {VERSION}")
    story = data.get("story", {})
    if not isinstance(story, dict):
        found.append("story must be an object")
    else:
        found += [f"story has unknown key {k!r}" for k in story if k not in STORY_KEYS]
        start = story.get("start")
        if start is not None:
            if not isinstance(start, dict):
                found.append("story.start must be an object")
            else:
                found += [f"story.start has unknown key {k!r}" for k in start if k not in START_KEYS]
        for key in ("profile", "review_sessions"):
            if key in story and not isinstance(story[key], dict):
                found.append(f"story.{key} must be an object")
    stages = data.get("stages", {})
    if not isinstance(stages, dict):
        found.append("stages must be an object")
        return found
    for stage, records in stages.items():
        if stage not in STAGES:
            found.append(f"stages has unknown stage {stage!r}")
            continue
        if not isinstance(records, dict):
            found.append(f"stages.{stage} must be an object")
            continue
        for name, obj in records.items():
            if name not in RECORD_NAMES:
                found.append(f"stages.{stage} has unknown record {name!r}")
            else:
                found += stage_problems(stage, name, obj)
    return found


def load(root: Path) -> Loaded:
    """Read and check the file. A missing file is an empty record; a malformed one is an error."""
    target = path(root)
    try:
        raw = target.read_bytes()
    except FileNotFoundError:
        return Loaded(empty())
    except OSError as exc:
        return Loaded(empty(), f"{FILE} cannot be read: {exc.strerror or exc}", True)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return Loaded(empty(), f"{FILE} is not valid JSON: {exc}", True)
    found = problems(data)
    if found:
        return Loaded(empty(), f"{FILE}: " + "; ".join(found[:3]), True)
    data.setdefault("story", {})
    data.setdefault("stages", {})
    return Loaded(data, None, True)


def _pruned(data: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(data)
    out["version"] = VERSION
    out["story"] = {k: v for k, v in (out.get("story") or {}).items() if v not in (None, {}, [])}
    stages = {}
    for stage, records in (out.get("stages") or {}).items():
        kept = {k: v for k, v in records.items() if v not in (None, {})}
        if kept:
            stages[stage] = kept
    out["stages"] = stages
    return out


def dumps(data: dict[str, Any]) -> str:
    """The one layout written: sorted keys, two-space indentation, non-ASCII kept, final newline."""
    return json.dumps(_pruned(data), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def save(root: Path, data: dict[str, Any]) -> bool:
    """Write ``data`` (refusing a non-conforming one). Returns whether the file changed."""
    found = problems(_pruned(data))
    if found:
        raise ValueError("; ".join(found[:3]))
    text = dumps(data).encode("utf-8")
    target = path(root)
    if target.is_file() and target.read_bytes() == text:
        return False
    target.write_bytes(text)
    return True


# ---- the rendered line each region keeps (data-model §Marked regions)

REACHED_TEXT = {
    "first": "first approval",
    "carried-forward": "carried forward",
    "reviewed": "reviewed change by change",
}


def _plain(value: Any) -> str:
    """A value safe inside a region line: one line, no fence and no comment marker."""
    text = " ".join(str(value or "").split())
    return text.replace("```", "'''").replace("<!--", "<!-").replace("-->", "->")


def approval_line(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    reached = record.get("reached") if record.get("reached") in REACHED_TEXT else "first"
    line = f"Approved by {_plain(record.get('by'))} on {_plain(str(record.get('at', ''))[:10])} ({REACHED_TEXT[reached]})"
    reply = record.get("attestation") or record.get("sign_off")
    if reply and record.get("question"):
        line += f': "{_plain(reply)}" to "{_plain(record["question"])}"'
    elif reply:
        line += f': "{_plain(reply)}"'
    line += "."
    if record.get("rests_on"):
        line += f" Rests on {_plain(', '.join(map(str, record['rests_on'])))}."
    if record.get("overrides_used"):
        line += f" Overrides used: {_plain(', '.join(map(str, record['overrides_used'])))}."
    return [line]


def comprehension_line(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    from .comprehension import COUNT_KEYS, counts

    found = counts(record)
    parts = [f"{found[k]} {k.replace('_', '-')}" for k in COUNT_KEYS if found.get(k)]
    taker = f" Taken by {_plain(record.get('taken_by'))}." if record.get("taken_by") else ""
    return [f"Comprehension: {', '.join(parts) or 'no level recorded'}.{taker}"]


def assessment_line(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    criteria = [c for c in record.get("criteria") or [] if isinstance(c, dict)]
    met = [c for c in criteria if c.get("status") == "met"]
    overridden = [c for c in criteria if c.get("status") == "overridden"]
    unmet = [str(c.get("id")) for c in criteria if c.get("status") not in ("met", "overridden")]
    line = f"Gate: {len(met) + len(overridden)} of {len(criteria)} criteria met"
    if overridden:
        line += f" ({len(overridden)} overridden: {', '.join(str(c.get('id')) for c in overridden)})"
    line += f"; not met: {', '.join(unmet)}." if unmet else "."
    noted = [c for c in met if "profile" in str(c.get("reason", ""))]
    for c in noted:
        line += f" {c.get('id')} met by {_plain(c.get('reason'))}."
    return [line]


def provenance_line(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    blocks = [b for b in (record.get("blocks") or {}).values() if isinstance(b, dict)]
    classes: dict[str, int] = {}
    for block in blocks:
        classes[str(block.get("class"))] = classes.get(str(block.get("class")), 0) + 1
    listing = ", ".join(f"{n} {k}" for k, n in sorted(classes.items()))
    reviewed = sum(1 for b in blocks if b.get("reviewed"))
    line = f"Blocks: {len(blocks)}" + (f" ({listing})" if listing else "") + f", {reviewed} reviewed by a person."
    changes = len(record.get("changes") or [])
    if changes:
        line += f" {changes} accepted change(s)."
    return [line]


RENDERERS = {
    "approval": approval_line,
    "assessment": assessment_line,
    "comprehension": comprehension_line,
    "provenance": provenance_line,
}


def render(name: str, record: dict[str, Any] | None) -> list[str]:
    return RENDERERS[name](record)


__all__ = ["FILE", "Loaded", "RECORD_NAMES", "dumps", "empty", "load", "path", "problems", "save"]

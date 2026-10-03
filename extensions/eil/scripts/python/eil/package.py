"""The story package: discovery, the governed test, document paths and derived stage state
(task T024; FR-043, FR-044, FR-069, FR-070, data-model.md §Stage).

Nothing here is stored. A stage's state is always derived from its document: the approval region,
the assessment region and the current fingerprints.
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import recordfile
from .blocks import Doc, RegionError, RegionRead, ensure_region, provenance_problems, set_region_lines
from .fingerprint import fingerprint_text
from .results import Finding

# The JSON records a stage can hold (T007). Every read and write of one goes through
# ``Package.record`` and ``Package.write_record``; nothing else reaches into the regions.
RECORD_NAMES = ("approval", "assessment", "comprehension", "provenance")

OVERVIEW = "s00-README.md"

STAGES = ("requirements", "functional", "technical", "ai-spec", "plan", "tasks", "verification", "completion")

DOC_FILES = {
    "requirements": "s01-requirements.md",
    "functional": "s02-functional-spec.md",
    "technical": "s03-technical-spec.md",
    "ai-spec": "s04-ai-spec.md",
    "plan": "s05-plan.md",
    "tasks": "s06-tasks.md",
    "verification": "s07-verification.md",
    "completion": "s08-completion.md",
}

# Exactly three aliases exist, each only while its target exists (FR-049, FR-050).
ALIASES = {"spec.md": "s04-ai-spec.md", "plan.md": "s05-plan.md", "tasks.md": "s06-tasks.md"}

APPROVABLE = ("requirements", "functional", "technical", "completion")

REACHED = ("first", "carried-forward", "reviewed", "re-signed-without-comparison")
MISSING_APPROVAL = "approval record missing or unreadable"


def reached_of(approval: dict[str, Any] | None) -> str | None:
    """How an approval was reached; a record from before `reached` existed was a first approval."""
    if not approval:
        return None
    value = approval.get("reached")
    return value if value in REACHED else "first"


STAGE_STATES = ("not-started", "draft", "in-review", "reviewed", "approved", "needs-re-review")
# The stages nobody approves; they end in ``reviewed`` (D-58).
REVIEWABLE = ("ai-spec", "plan", "tasks", "verification")


def resolve_feature_dir(
    cwd: Path, feature_dir: str | None = None, env: Mapping[str, str] | None = None
) -> Path | None:
    """The feature directory as Spec Kit resolves it: argument, then environment, then feature.json."""
    environment = os.environ if env is None else env

    def absolute(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else cwd / path

    if feature_dir:
        return absolute(feature_dir)
    from_env = environment.get("SPECIFY_FEATURE_DIRECTORY", "").strip()
    if from_env:
        return absolute(from_env)
    try:
        data = json.loads((cwd / ".specify" / "feature.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("feature_directory") if isinstance(data, dict) else None
    return absolute(value) if isinstance(value, str) and value.strip() else None


@dataclass
class StageState:
    stage: str
    state: str
    reason: str = ""
    approval: dict[str, Any] | None = None
    abbreviated: bool = False
    fingerprint: str | None = None
    findings: list[Finding] = field(default_factory=list)
    note: str = ""  # non-blocking: upstream moved but nothing traced in this stage is affected (D-26)


_SHARED_DOCS: dict[tuple[str, str], Doc] = {}


class Package:
    """A feature directory. It is *governed* iff it contains ``s00-README.md`` (FR-069)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        # Parsing a large document is the cost of every command, and one command asks for the same
        # document many times. Each entry is keyed on the text it was made from, so a document that
        # changes on disk is simply read again.
        self._docs: dict[str, tuple[str, Doc]] = {}
        self._fingerprints: dict[str, tuple[str, str]] = {}
        self._texts: dict[str, tuple[tuple[int, int], str]] = {}
        self._parsed_story: tuple[tuple[str, ...], dict[str, Any]] | None = None

    def parsed_story(self) -> dict[str, Any]:
        """Every existing stage's document, parsed and scanned (``impact.parsed_story``), cached
        against every stage's current fingerprint. A full parse-and-scan of every document is real
        cost (performance budget, D-26); this is what lets one pass over all eight stages'
        ``state()`` do it once instead of once per stage, while a real edit is still picked up
        immediately, the same content-keyed idea as ``doc()``/``fingerprint()`` above."""
        from . import impact

        key = tuple(self.fingerprint(s) or "" for s in self.existing_stages())
        if self._parsed_story is None or self._parsed_story[0] != key:
            self._parsed_story = (key, impact.parsed_story(self))
        return self._parsed_story[1]

    def affected_items(self) -> dict[str, list[str]]:
        """``impact.affected(self)`` (FR-043, FR-044; informational, shown in ``status``/overview).
        Built from ``parsed_story()`` above, so it is cheap to call once per stage."""
        from . import impact

        return impact.affected(self, self.parsed_story())

    def current_item_hashes(self) -> dict[str, str]:
        """``impact.current_item_hashes(self)``, used to check a stage's own recorded
        ``upstream_items`` (D-26). Built from ``parsed_story()`` above."""
        from . import impact

        return impact.current_item_hashes(self, self.parsed_story())

    @property
    def project_root(self) -> Path | None:
        """The Spec Kit project containing this feature (the nearest parent with ``.specify``)."""
        for parent in (self.root.resolve(), *self.root.resolve().parents):
            if (parent / ".specify").is_dir():
                return parent
        return None

    @property
    def overview_path(self) -> Path:
        return self.root / OVERVIEW

    @property
    def governed(self) -> bool:
        return self.overview_path.is_file()

    def doc_path(self, stage: str) -> Path:
        return self.root / DOC_FILES[stage]

    def exists(self, stage: str) -> bool:
        return self.doc_path(stage).is_file()

    def existing_stages(self) -> list[str]:
        return [stage for stage in STAGES if self.exists(stage)]

    def read(self, stage: str) -> str:
        path = self.doc_path(stage)
        info = path.stat()
        key = (info.st_mtime_ns, info.st_size)
        held = self._texts.get(stage)
        if held is not None and held[0] == key:
            return held[1]
        text = path.read_bytes().decode("utf-8")
        self._texts[stage] = (key, text)
        return text

    def doc(self, stage: str) -> Doc:
        text = self.read(stage)
        cached = self._docs.get(stage)
        if cached is None or cached[0] != text:
            shared = _SHARED_DOCS.get((stage, text))
            if shared is None:
                if len(_SHARED_DOCS) >= 24:
                    _SHARED_DOCS.clear()
                shared = _SHARED_DOCS[(stage, text)] = Doc(text, path=DOC_FILES[stage])
            cached = (text, shared)
            self._docs[stage] = cached
        return cached[1]

    def fingerprint(self, stage: str) -> str | None:
        """Current fingerprint of a stage document, or ``None`` if it is absent or not UTF-8."""
        try:
            text = self.read(stage)
        except (OSError, UnicodeDecodeError):
            return None
        cached = self._fingerprints.get(stage)
        if cached is None or cached[0] != text:
            cached = (text, fingerprint_text(text))
            self._fingerprints[stage] = cached
        return cached[1]

    # ---- the record file (D-48)

    def record_file(self) -> recordfile.Loaded:
        """``eil-record.json``, parsed and checked, cached against its size and modification time."""
        target = recordfile.path(self.root)
        try:
            info = target.stat()
            key: tuple[int, int] | None = (info.st_mtime_ns, info.st_size)
        except OSError:
            key = None
        held = self.__dict__.get("_record_file")
        if held is None or held[0] != key or key is None:
            held = (key, recordfile.load(self.root))
            self.__dict__["_record_file"] = held
        return held[1]

    def story_record(self) -> dict[str, Any]:
        """The story-level records (``start``, ``profile``, ``review_sessions``); empty when unreadable."""
        loaded = self.record_file()
        return dict(loaded.data.get("story") or {}) if loaded.error is None else {}

    def write_story_record(self, key: str, value: Any) -> None:
        """Set (or, with ``None``, remove) one story-level record. Refuses to overwrite a malformed file."""
        loaded = self.record_file()
        if loaded.error is not None:
            raise RegionError(loaded.error)
        data = copy.deepcopy(loaded.data)
        story = data.setdefault("story", {})
        if value is None:
            story.pop(key, None)
        else:
            story[key] = value
        self.root.mkdir(parents=True, exist_ok=True)
        recordfile.save(self.root, data)

    # ---- records (T007): the one seam for reading and writing a stage's JSON records

    def record_read(self, stage: str, name: str) -> RegionRead:
        """A stage's ``name`` record with any error that makes it unreadable.

        The record lives in ``eil-record.json`` (D-48). A region that still holds a JSON body belongs to
        a document not yet migrated: it is read as before, and wins, since the helper only ever writes a
        rendered line there. The provenance record is also checked against its allowed keys."""
        if name not in RECORD_NAMES:
            raise ValueError(f"{name!r} is not a record")
        read = self.doc(stage).read_region(name)
        if read.obj is None and read.error is None:
            loaded = self.record_file()
            if loaded.error is not None:
                return RegionRead(None, loaded.error)
            obj = (loaded.data.get("stages", {}).get(stage) or {}).get(name)
            read = RegionRead(copy.deepcopy(obj) if obj else None)
        if name == "provenance" and read.obj is not None and not read.error:
            problems = provenance_problems(read.obj)
            if problems:
                return RegionRead(None, "; ".join(problems[:3]))
        return read

    def record(self, stage: str, name: str) -> dict[str, Any] | None:
        """A stage's ``name`` record, or ``None`` when it is absent or unreadable."""
        read = self.record_read(stage, name)
        return None if read.error else read.obj

    def write_record(self, stage: str, name: str, obj: dict[str, Any] | None, text: str | None = None) -> str:
        """Record ``obj`` as the stage's ``name`` record and return the document text.

        The record goes to ``eil-record.json``; the region keeps one rendered line. Any other record of
        the stage still held as JSON in its region moves to the file in the same write, so the next
        write on a stage completes its migration. ``text`` is the document as the caller has already
        edited it (the file on disk when omitted). Raises ``RegionError`` when the document or the
        record file cannot take it; then nothing is written."""
        if name not in RECORD_NAMES:
            raise ValueError(f"{name!r} is not a record")
        if name == "provenance" and obj:
            problems = provenance_problems(obj)
            if problems:
                raise RegionError("; ".join(problems[:3]))
        return self._store(stage, {name: obj}, text)

    def migrate(self, stage: str) -> bool:
        """Move every JSON region body of ``stage`` into the record file (``sync``). Idempotent;
        returns whether anything moved."""
        doc = self.doc(stage)
        if not any(doc.region_is_json(n) for n in RECORD_NAMES):
            return False
        self._store(stage, {}, None)
        return True

    def _store(self, stage: str, changes: dict[str, dict[str, Any] | None], text: str | None) -> str:
        base = self.read(stage) if text is None else text
        loaded = self.record_file()
        if loaded.error is not None:
            raise RegionError(f"cannot record: {loaded.error}; repair or remove it first")
        data = copy.deepcopy(loaded.data)
        held = data.setdefault("stages", {}).setdefault(stage, {})
        doc = Doc(base)
        for other in RECORD_NAMES:
            read = doc.read_region(other)
            if read.obj is not None and not read.error and other not in changes:
                if recordfile.stage_problems(stage, other, read.obj):
                    continue  # a malformed record stays where it is, reported, to be repaired by a person
                held[other] = read.obj
        for name, obj in changes.items():
            if obj:
                held[name] = obj
            else:
                held.pop(name, None)
        problems = recordfile.problems(data)
        if problems:
            raise RegionError("; ".join(problems[:3]))
        updated = base
        for name in changes:
            if changes[name]:
                updated = ensure_region(updated, name)
        rendered = Doc(updated)
        for name in RECORD_NAMES:
            if name in rendered.regions and (name in held or name in changes or rendered.region_is_json(name)):
                if rendered.region_is_json(name) and name not in held:
                    continue  # an unreadable JSON body is left for a person to repair
                updated = set_region_lines(updated, name, recordfile.render(name, held.get(name)))
        self.root.mkdir(parents=True, exist_ok=True)
        recordfile.save(self.root, data)
        path = self.doc_path(stage)
        if not path.is_file() or path.read_bytes() != updated.encode("utf-8"):
            path.write_bytes(updated.encode("utf-8"))
        return updated

    def approval_line_without_record(self, stage: str) -> Finding | None:
        """D-48 integrity: the document says it was approved but the record file holds no readable
        approval for it (``approval-record-missing``, or ``malformed-record-file``)."""
        doc = self.doc(stage)
        if doc.region_is_json("approval") or not doc.region_lines("approval"):
            return None
        loaded = self.record_file()
        if loaded.error is not None:
            return Finding("malformed-record-file", recordfile.FILE, loaded.error)
        if (loaded.data.get("stages", {}).get(stage) or {}).get("approval"):
            return None
        return Finding(
            "approval-record-missing",
            DOC_FILES[stage],
            f"the document shows an approval but {recordfile.FILE} holds no approval record for {stage}",
        )

    def state(self, stage: str) -> StageState:
        path = self.doc_path(stage)
        if not path.is_file():
            return StageState(stage, "not-started")
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            return StageState(
                stage,
                "draft",
                "not-utf8",
                findings=[Finding("not-utf8", path.name, "document is not valid UTF-8")],
            )
        doc = self.doc(stage)
        fingerprint = self.fingerprint(stage) or fingerprint_text(text)
        findings = [f for f in doc.findings if f.code == "malformed-region"]
        abbreviated = any(r.kind == "abbreviation" and r.obj for r in doc.records())

        approval = None
        missing = self.approval_line_without_record(stage)
        if missing is not None:
            findings.append(missing)
            return StageState(
                stage,
                "needs-re-review",
                MISSING_APPROVAL,
                abbreviated=abbreviated,
                fingerprint=fingerprint,
                findings=findings,
            )
        read = self.record_read(stage, "approval")
        if read.error and read.error == self.record_file().error:
            findings.append(Finding("malformed-record-file", recordfile.FILE, read.error))
        elif read.error:
            findings.append(Finding("malformed-approval", path.name, f"approval region: {read.error}"))
        elif read.obj is not None:
            if isinstance(read.obj.get("fingerprint"), str):
                approval = read.obj
            else:
                findings.append(Finding("malformed-approval", path.name, "approval has no fingerprint"))

        base = {"abbreviated": abbreviated, "fingerprint": fingerprint, "findings": findings}
        if approval is not None:
            if approval["fingerprint"] != fingerprint:
                return StageState(
                    stage, "needs-re-review", "content changed since approval", approval, **base
                )
            moved = [
                name
                for name, then in (approval.get("upstream") or {}).items()
                if self.fingerprint(name) != then
            ]
            recorded_items = approval.get("upstream_items")
            if isinstance(recorded_items, dict):
                current = self.current_item_hashes()
                changed = sorted(i for i, h in recorded_items.items() if current.get(i) != h)
            else:
                # An approval from before D-26 (or with nothing upstream to trace) has no snapshot
                # to compare against; fall back to the whole-document signal so it is not silently
                # treated as unaffected.
                changed = list(moved)
            if changed:
                return StageState(
                    stage,
                    "needs-re-review",
                    f"traces to changed upstream item(s): {', '.join(changed)}"
                    if isinstance(recorded_items, dict)
                    else f"upstream {', '.join(moved)} changed since approval",
                    approval,
                    **base,
                )
            recorded_findings = approval.get("review_findings") if stage == "completion" else None
            if isinstance(recorded_findings, dict):
                from .verification import finding_hashes

                fresh = sorted(i for i, h in finding_hashes(self).items() if recorded_findings.get(i) != h)
                if fresh:
                    return StageState(
                        stage,
                        "needs-re-review",
                        f"review finding recorded after completion: {', '.join(fresh)}",
                        approval,
                        **base,
                    )
            if moved:
                return StageState(
                    stage,
                    "approved",
                    "",
                    approval,
                    note=f"upstream {', '.join(moved)} changed since approval; no traced item is affected",
                    **base,
                )
            return StageState(stage, "approved", "", approval, **base)

        assessment = self.record(stage, "assessment")
        if stage in REVIEWABLE and self._reviewed(stage, assessment, fingerprint):
            return StageState(stage, "reviewed", **base)
        if _gate_is_met(assessment, fingerprint):
            return StageState(stage, "in-review", **base)
        return StageState(stage, "draft", **base)

    def _reviewed(self, stage: str, assessment: dict[str, Any] | None, fingerprint: str) -> bool:
        """D-58: the document exists, its code-decided criteria are met (as last checked, at this
        version), and no block needs review or is stale."""
        if not assessment or assessment.get("fingerprint") != fingerprint:
            return False
        criteria = [c for c in assessment.get("criteria") or [] if isinstance(c, dict)]
        decided = [c for c in criteria if c.get("kind") != "judgment"]
        if not decided or any(c.get("status") not in ("met", "overridden") for c in decided):
            return False
        from .blockstatus import NEEDS_REVIEW, SOURCE_CHANGED, block_statuses

        infos = block_statuses(self).get(stage, {}).values()
        return not any(i.status in (NEEDS_REVIEW, SOURCE_CHANGED) or i.stale for i in infos)

    def states(self) -> dict[str, StageState]:
        return {stage: self.state(stage) for stage in STAGES}

    def current_stage(self) -> str | None:
        """The first stage that is not yet done. An approvable stage is done when approved; the
        others are done when their gate is met (they are never approved, spec Assumptions)."""
        if self.exists("completion") and self.state("completion").state == "approved":
            return None  # an approved completion ends the story, whatever a derived stage says (D-58)
        for stage in STAGES:
            state = self.state(stage).state
            done = state == "approved" if stage in APPROVABLE else state in ("in-review", "reviewed")
            if not done:
                return stage
        return None


def _gate_is_met(assessment: dict[str, Any] | None, fingerprint: str) -> bool:
    if not assessment or assessment.get("fingerprint") != fingerprint:
        return False
    criteria = assessment.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return False
    return all(isinstance(c, dict) and c.get("status") in ("met", "overridden") for c in criteria)

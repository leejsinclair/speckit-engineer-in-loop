"""The story package: discovery, the governed test, document paths and derived stage state
(task T024; FR-043, FR-044, FR-069, FR-070, data-model.md §Stage).

Nothing here is stored. A stage's state is always derived from its document: the approval region,
the assessment region and the current fingerprints.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blocks import Doc
from .fingerprint import fingerprint_text
from .results import Finding

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

STAGE_STATES = ("not-started", "draft", "in-review", "approved", "needs-re-review")


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


class Package:
    """A feature directory. It is *governed* iff it contains ``s00-README.md`` (FR-069)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        # Parsing a large document is the cost of every command, and one command asks for the same
        # document many times. Each entry is keyed on the text it was made from, so a document that
        # changes on disk is simply read again.
        self._docs: dict[str, tuple[str, Doc]] = {}
        self._fingerprints: dict[str, tuple[str, str]] = {}

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
        return self.doc_path(stage).read_bytes().decode("utf-8")

    def doc(self, stage: str) -> Doc:
        text = self.read(stage)
        cached = self._docs.get(stage)
        if cached is None or cached[0] != text:
            cached = (text, Doc(text, path=DOC_FILES[stage]))
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
        read = doc.read_region("approval")
        if read.error:
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
            if moved:
                return StageState(
                    stage,
                    "needs-re-review",
                    f"upstream {', '.join(moved)} changed since approval",
                    approval,
                    **base,
                )
            return StageState(stage, "approved", "", approval, **base)

        assessment = doc.read_region("assessment").obj
        if _gate_is_met(assessment, fingerprint):
            return StageState(stage, "in-review", **base)
        return StageState(stage, "draft", **base)

    def states(self) -> dict[str, StageState]:
        return {stage: self.state(stage) for stage in STAGES}

    def current_stage(self) -> str | None:
        """The first stage that is not yet done. An approvable stage is done when approved; the
        others are done when their gate is met (they are never approved, spec Assumptions)."""
        for stage in STAGES:
            state = self.state(stage).state
            done = state == "approved" if stage in APPROVABLE else state == "in-review"
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

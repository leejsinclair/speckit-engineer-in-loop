"""Result types shared by every module: refusals, findings, exit codes, JSON output (task T016)."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

EXIT_OK = 0
EXIT_REFUSAL = 1
EXIT_USAGE = 2
EXIT_NOT_GOVERNED = 3
EXIT_INTERNAL = 4

# Stable refusal codes (contracts/cli.md). A refusal stops an action; it is never a finding.
REFUSAL_CODES = frozenset(
    {
        "stage-not-approved",
        "unmet-criteria",
        "open-challenge",
        "open-question",
        "unreviewed-ai-content",
        "not-restated",
        "pending-clarification",
        "ai-spec-not-traceable",
        "ai-spec-missing",
        "plan-missing",
        "unverified-requirement",
        "unverified-artifact",
        "verification-missing",
        "artifact-missing",
        "artifact-format-not-allowed",
        "artifact-no-provenance",
        "artifact-wrong-level",
        "path-outside-package",
        "comprehension-prerequisites",
        "unknown-level",
        "not-a-confirmer",
        "not-an-authoriser",
        "reason-required",
        "attestation-required",
        "ai-approval",
        "already-governed",
        "already-exists",
        "alias-fault-strict",
        "directory-has-spec-md",
        "duplicate-of-closed",
        "conflict",
        "cannot-skip",
        "unknown-stage",
        "unknown-item",
        "unknown-criterion",
        "not-approvable",
        "stage-not-eligible",
        "tasks-missing",
        "not-amendable",
        "amend-not-covered",
        "changes-unanswered",
        "confirmation-required",
        "acceptance-conflict",
        "list-changed",
        "digest-required",
        "reply-required",
        "reply-mismatch",
        "task-completed-against-earlier-version",
        "evidence-for-earlier-version",
        "work-blocked",
        "amend-not-covering",
        "owner-ambiguous",
        "owner-not-candidate",
        "summary-missing",
        "review-finding-open",
    }
)

# Finding codes reported by `check` and `status`. A finding is information, never a refusal.
FINDING_CODES = frozenset(
    {
        # item grammar and trace
        "malformed-item",
        "duplicate-id",
        "dangling-trace",
        "trace-cycle",
        "completed-while-blocked",
        # documents
        "malformed-region",
        "malformed-record",
        "malformed-fence",
        "malformed-approval",
        "malformed-provenance",
        "malformed-comprehension",
        "not-utf8",
        # artifacts and diagrams (document-format.md)
        "artifact-unregistered",
        "artifact-untraced",
        "artifact-wrong-level",
        "diagram-unparseable",
        "diagram-inconsistent",
        "artifact-missing-file",
        "artifact-hash-mismatch",
        "artifact-no-provenance",
        "artifact-format-not-allowed",
        "artifact-changed-since-approval",
        "artifact-uncovered",
        "orphan-asset",
        # AI Specification, plan and tasks
        "ai-spec-not-traceable",
        "pending-clarification",
        "plan-not-derivable",
        "task-untraced",
        # comprehension
        "comprehension-missing",
        "comprehension-stale",
        "comprehension-incomplete",
        # human-decided provenance
        "decided-source-invalid",
        "correction-wording-mismatch",
    }
)


@dataclass(frozen=True)
class Refusal:
    """A rule stopped the action (exit 1). ``code`` is a stable identifier."""

    code: str
    message: str
    fix: str = ""
    existing: str = ""

    def __post_init__(self) -> None:
        if self.code not in REFUSAL_CODES:
            raise ValueError(f"unregistered refusal code: {self.code!r}")

    def to_json(self) -> dict[str, str]:
        out = asdict(self)
        if not out["existing"]:
            del out["existing"]
        return out


@dataclass(frozen=True)
class Finding:
    """Something a check noticed. ``where`` is an item id, a file or ``path:line``."""

    code: str
    where: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in FINDING_CODES:
            raise ValueError(f"unregistered finding code: {self.code!r}")

    def to_json(self) -> dict[str, str]:
        return asdict(self)


class EilExit(Exception):
    """Raised anywhere to end the run with a specific exit code and JSON payload."""

    def __init__(self, code: int, payload: dict[str, Any] | None = None, message: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}
        self.message = message


def usage_error(message: str) -> EilExit:
    return EilExit(EXIT_USAGE, {"ok": False, "error": message}, message)


def not_governed() -> EilExit:
    return EilExit(EXIT_NOT_GOVERNED, {"governed": False}, "not a governed feature (no s00-README.md)")


def refuse(*refusals: Refusal) -> EilExit:
    return EilExit(
        EXIT_REFUSAL,
        {"ok": False, "refusals": [r.to_json() for r in refusals]},
        "; ".join(f"{r.code}: {r.message}" for r in refusals),
    )


def emit_json(payload: dict[str, Any], stream: Any = None) -> None:
    """Print exactly one JSON object and nothing else."""
    stream = stream or sys.stdout
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=False) + "\n")

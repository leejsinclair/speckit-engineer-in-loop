"""Prompt guidance contract test (task T072; constitution Principle I, tier 2).

A behavioural rule that lives only in a prompt cannot be enforced by code, so it must be written as
guidance and be covered by a text check like this one or by a probe in ``docs/trials.md``. This
file is the text half: it proves each rule is *written*, in the prompt, in the words the trials
probe for. Whether the AI then follows it is measured by the human probes, never by this test.

Adapted from Know Your Spec's ``test-no-persistence.sh``. Each entry is skipped while its prompt
file does not exist yet and runs at every later checkpoint.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EXT = REPO / "extensions" / "eil" / "commands"
WRAPS = REPO / "commands"

HELPER = ".specify/extensions/eil/scripts/python/eil"
GUARD = (
    f"If `{HELPER}` does not exist, STOP. Tell the user to run `specify extension add eil` and then "
    "`specify preset add engineer-in-the-loop`"
)

EXTENSION_PROMPTS = [
    "requirements",
    "functional",
    "technical",
    "ai-spec",
    "verify",
    "complete",
    "comprehend",
    "artifact",
    "challenge",
    "approve",
    "override",
    "next",
    "abbreviate",
    "resolve",
    "trace",
    "status",
    "amend",
    "review",
]
WRAP_PROMPTS = ["specify", "clarify", "plan", "tasks", "analyze", "checklist", "implement"]
ALL_PROMPTS = [EXT / f"speckit.eil.{n}.md" for n in EXTENSION_PROMPTS] + [
    WRAPS / f"speckit.{n}.md" for n in WRAP_PROMPTS
]

# (prompt file, rule, regular expressions that must all match, case-insensitively)
RULES: list[tuple[Path, str, list[str]]] = [
    # comprehension check (FR-087 to FR-094, SC-016)
    (
        EXT / "speckit.eil.comprehend.md",
        "never persists a question, answer or hint",
        [r"never write any question, answer or hint"],
    ),
    (
        EXT / "speckit.eil.comprehend.md",
        "passing is not required but the check is",
        [r"passing is not required", r"the check is required"],
    ),
    (
        EXT / "speckit.eil.comprehend.md",
        "rewords each retry",
        [r"newly worded", r"never the same wording twice"],
    ),
    (
        EXT / "speckit.eil.comprehend.md",
        "reveals the answer only on request",
        [r"only (when|on) .*(asks|request|reveal)"],
    ),
    # approval and attestation (FR-012)
    (EXT / "speckit.eil.approve.md", "asks the human directly", [r"ask the human directly"]),
    (EXT / "speckit.eil.approve.md", "never supplies the attestation", [r"never supply the attestation"]),
    (
        EXT / "speckit.eil.override.md",
        "asks the human for the criterion and the reason",
        [r"ask the human directly", r"never .*write the reason"],
    ),
    # requirements (FR-022, D-16)
    (
        EXT / "speckit.eil.requirements.md",
        "never turns an open question into an assumption",
        [r"never turn an open question into an assumption"],
    ),
    (
        EXT / "speckit.eil.requirements.md",
        "tags AI text ai-draft",
        [r"tag every passage you write with `\[ai-draft\]`"],
    ),
    # functional and artifacts (FR-085)
    (
        EXT / "speckit.eil.functional.md",
        "never draws a wireframe or export",
        [r"never (draw|create|convert|edit)"],
    ),
    (
        EXT / "speckit.eil.artifact.md",
        "never draws, converts or edits an export",
        [r"do not create, convert or edit"],
    ),
    # technical (US4-3)
    (
        EXT / "speckit.eil.technical.md",
        "records the developer's choice; the AI only proposes",
        [r"developer'?s choice", r"propose"],
    ),
    (
        EXT / "speckit.eil.technical.md",
        "the owner is a person, never the AI",
        [r"the owner is the developer", r"never write an owner that is you"],
    ),
    (
        EXT / "speckit.eil.technical.md",
        "never writes a decision the developer has not made; never hides an inconsistency",
        [r"never write a decision the developer has not made", r"never by hiding it"],
    ),
    # abbreviation (FR-040)
    (
        EXT / "speckit.eil.abbreviate.md",
        "asks the human and never skips a stage",
        [r"ask the human directly", r"never authorise an abbreviation yourself", r"never skipped"],
    ),
    # challenges (FR-034 to FR-038)
    (
        EXT / "speckit.eil.challenge.md",
        "never answers for the human",
        [r"never answer a challenge on the human's behalf"],
    ),
    (
        EXT / "speckit.eil.requirements.md",
        "the shared challenge pass keeps recorded answers as constraints",
        [r"standing constraint", r"never answer a challenge yourself"],
    ),
    # verification and completion (FR-062, FR-064)
    (
        EXT / "speckit.eil.verify.md",
        "never invents evidence or declares completion",
        [r"never invent evidence", r"never declare completion"],
    ),
    (
        EXT / "speckit.eil.complete.md",
        "never supplies the confirmation",
        [r"never supply the confirmation yourself", r"verbatim"],
    ),
    # resolve (FR-067)
    (
        EXT / "speckit.eil.resolve.md",
        "never removes the pending tag or writes a decision the human did not make",
        [r"never remove a `\[pending-clarification\]` tag by hand", r"did not make"],
    ),
    (EXT / "speckit.eil.resolve.md", "asks the human which stage", [r"ask; do not choose for them"]),
    # human-decided provenance (D-24): text that is the human's own words is (decided: ID), not [ai-draft]
    (
        EXT / "speckit.eil.requirements.md",
        "human-decided provenance uses (decided: ID) instead of [ai-draft]",
        [r"human-decided provenance", r"\(decided: "],
    ),
    (
        EXT / "speckit.eil.functional.md",
        "human-decided provenance uses (decided: ID) instead of [ai-draft]",
        [r"human-decided provenance", r"\(decided: "],
    ),
    (
        EXT / "speckit.eil.technical.md",
        "human-decided provenance uses (decided: ID) instead of [ai-draft]",
        [r"human-decided provenance", r"\(decided: "],
    ),
    (
        EXT / "speckit.eil.challenge.md",
        "an accepted challenge's dictated fix is (decided: CH-id), not [ai-draft]",
        [r"\(decided: CH-id\)"],
    ),
    (
        EXT / "speckit.eil.resolve.md",
        "shows the human the recorded text and writes a verbatim carry untagged",
        [r"verbatim carry", r"\(decided: AIS-###\)"],
    ),
    # eil amend (D-25): re-signs an approval covered by cited human decisions
    (EXT / "speckit.eil.amend.md", "asks the human directly", [r"ask the human directly"]),
    (EXT / "speckit.eil.amend.md", "never supplies the attestation", [r"never supply the attestation"]),
    (
        EXT / "speckit.eil.amend.md",
        "never chooses the cited decisions for the human",
        [r"never choose the decisions"],
    ),
    # eil review (D-28): walks the human through each change and records their "ok" as the decision
    (
        EXT / "speckit.eil.review.md",
        "never accepts a change on the human's behalf",
        [r"never accept a change on the human's behalf"],
    ),
    (
        EXT / "speckit.eil.review.md",
        "never supplies the attestation for eil review finish",
        [r"never supply the attestation"],
    ),
    # conversational friction (D-24, D-25, D-27): reuse a known name; batch challenge answers
    *[
        (
            EXT / f"speckit.eil.{name}.md",
            "reuses the confirmer's name without re-asking",
            [r"reuse it for every `--by`"],
        )
        for name in (
            "approve",
            "override",
            "abbreviate",
            "challenge",
            "resolve",
            "comprehend",
            "amend",
            "review",
        )
    ],
    (
        EXT / "speckit.eil.challenge.md",
        "accepts a batched reply covering several challenges at once",
        [r"accept all", r"record each with its own"],
    ),
    (
        EXT / "speckit.eil.approve.md",
        "an attestation already given inline is used without re-asking",
        [r"already carries their confirmation"],
    ),
    # challenge, verify, complete, ai-spec
    (EXT / "speckit.eil.challenge.md", "never answers a challenge for the human", [r"never answer"]),
    (EXT / "speckit.eil.verify.md", "never declares completion", [r"never declare completion"]),
    (EXT / "speckit.eil.complete.md", "passes the human's verbatim confirmation", [r"verbatim"]),
    (
        EXT / "speckit.eil.ai-spec.md",
        "introduces nothing without a source",
        [r"without a source", r"challenge"],
    ),
    # next
    (
        EXT / "speckit.eil.next.md",
        "runs only what the helper names, and stops at every human step",
        [
            r"do not choose a different step",
            r"`human`: \*\*stop",
            r"never run a command the helper did not name",
        ],
    ),
    (
        EXT / "speckit.eil.next.md",
        "never takes a human decision and runs one step",
        [r"never approve a stage, record an override", r"after one step, stop", r"never start a second step"],
    ),
    # preset wraps
    (WRAPS / "speckit.specify.md", "never writes spec.md", [r"never creates or writes `spec\.md`"]),
    (WRAPS / "speckit.clarify.md", "tags pending answers", [r"\[pending-clarification\]", r"AIS-###"]),
    (
        WRAPS / "speckit.plan.md",
        "flags content not derivable from an approved decision",
        [r"not derivable", r"DEC"],
    ),
    (WRAPS / "speckit.tasks.md", "flags architecture and cites the ART", [r"architecture", r"`ART`"]),
    (WRAPS / "speckit.implement.md", "surfaces ambiguities, never assumes", [r"ambigu", r"never assum"]),
    (
        WRAPS / "speckit.checklist.md",
        "reads s01 and s02 as read-only context",
        [r"s01", r"s02", r"read-only"],
    ),
]

HELPER_CALL = re.compile(
    r"\beil (sync|start|check|approve|override|stage-init|enter|challenge|artifact|comprehension|trace|status|"
    r"resolve|abbreviate|overview|amend|review)\b"
)
FORBIDDEN_MECHANICS = re.compile(r"\b(points?|score|scores|streak|timer|rank|reward)\b", re.IGNORECASE)
NEGATION = re.compile(r"\b(no|never|not|without|nor)\b", re.IGNORECASE)
OVERSTATEMENT = re.compile(
    r"tamper[- ]?proof|cannot be bypassed|impossible to bypass|guarantee[sd]?\b", re.IGNORECASE
)


def read(path: Path) -> str:
    if not path.is_file():
        pytest.skip(f"{path.relative_to(REPO)} does not exist yet")
    return path.read_text(encoding="utf-8")


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def ids(entries: list[tuple[Path, str, list[str]]]) -> list[str]:
    return [f"{path.stem}: {rule}" for path, rule, _ in entries]


@pytest.mark.parametrize(("path", "rule", "patterns"), RULES, ids=ids(RULES))
def test_the_rule_is_written_in_the_prompt(path: Path, rule: str, patterns: list[str]) -> None:
    text = read(path)
    for pattern in patterns:
        assert re.search(pattern, text, re.IGNORECASE | re.DOTALL), (
            f"{path.name}: rule '{rule}' needs /{pattern}/"
        )


@pytest.mark.parametrize("path", ALL_PROMPTS, ids=lambda p: p.stem)
def test_every_prompt_begins_with_the_guard(path: Path) -> None:
    """The guard comes before the first call to the helper (research D-08)."""
    text = read(path)
    assert GUARD in text, f"{path.name} has no guard"
    call = HELPER_CALL.search(text)
    assert call is None or text.index(GUARD) < call.start(), f"{path.name} calls the helper before its guard"


@pytest.mark.parametrize("path", ALL_PROMPTS, ids=lambda p: p.stem)
def test_every_prompt_calls_the_helper_for_gates_rather_than_deciding_them(path: Path) -> None:
    assert HELPER_CALL.search(read(path)), f"{path.name} never calls the helper"


@pytest.mark.parametrize("path", ALL_PROMPTS, ids=lambda p: p.stem)
def test_no_prompt_overstates_what_the_gates_guarantee(path: Path) -> None:
    """Principle II: gates make a bypass detectable, they are not tamper-proof."""
    text = read(path)
    hits = [s.strip() for s in sentences(text) if OVERSTATEMENT.search(s) and not NEGATION.search(s)]
    assert not hits, hits


def test_the_comprehension_prompt_forbids_gamification_and_never_uses_it() -> None:
    """SC-016, FR-094: the words appear only in the sentence that forbids them."""
    text = read(EXT / "speckit.eil.comprehend.md")
    offenders = [
        s.strip() for s in sentences(text) if FORBIDDEN_MECHANICS.search(s) and not NEGATION.search(s)
    ]
    assert not offenders, offenders


@pytest.mark.parametrize(("name", "core"), [("5-plan", "plan"), ("6-tasks", "tasks")])
def test_the_numbered_plan_and_tasks_commands_only_delegate(name: str, core: str) -> None:
    text = read(EXT / f"speckit.eil.{name}.md")
    assert GUARD in text
    assert f"Run `/speckit-{core}`" in text and "adds no behaviour of its own" in text
    assert not HELPER_CALL.search(text), "a delegating command must leave every check to the wrapped one"

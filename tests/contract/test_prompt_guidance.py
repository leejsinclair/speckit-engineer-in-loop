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
        "leaves the ai-draft cue to the helper",
        [r"never write `\[ai-draft\]` by hand"],
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
        "never writes an observable decision the developer has not made; never hides an inconsistency",
        [r"never write a decision with an observable effect, scope or trade-off that the developer has not made", r"never by hiding it"],
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
    # accept (FR-015): covered changes take a short sign-off; the person's words are never supplied
    (EXT / "speckit.eil.accept.md", "never supplies the sign-off", [r"never supply the sign-off"]),
    (EXT / "speckit.eil.accept.md", "labels its own summaries as drafts", [r"draft by the AI and must be labelled"]),
    (EXT / "speckit.eil.accept.md", "asks once for the uncovered changes", [r"ask once", r"one reply"]),
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
            "accept",
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


DRAFTING = [EXT / f"speckit.eil.{n}.md" for n in ("requirements", "functional", "technical", "ai-spec")]
WRAPPED = [WRAPS / f"speckit.{n}.md" for n in ("plan", "tasks")]


@pytest.mark.parametrize("path", DRAFTING, ids=lambda p: p.stem)
def test_no_manual_ai_draft(path: Path) -> None:
    """D-33: the cue is helper-rendered; a drafting prompt never tells the AI to write it."""
    text = read(path)
    assert re.search(r"never write `\[ai-draft\]` by hand", text, re.I)
    assert not re.search(r"tag every (passage|row)", text, re.I)


@pytest.mark.parametrize("path", [*DRAFTING, EXT / "speckit.eil.approve.md"], ids=lambda p: p.stem)
def test_one_reply_lists(path: Path) -> None:
    """FR-009, FR-010: one `inferred` list answered in one reply, before any attestation."""
    text = read(path)
    assert "--kind inferred" in text
    if path.stem.endswith("approve"):
        assert text.index("--kind inferred") < text.index("--attestation")


@pytest.mark.parametrize("path", DRAFTING, ids=lambda p: p.stem)
def test_reply_verbatim(path: Path) -> None:
    """The human's reply is passed as they gave it; the AI never answers for them."""
    text = read(path)
    assert "verbatim" in text and re.search(r"never answer for them", text, re.I)
    assert "eil blocks classify" in text


@pytest.mark.parametrize("path", WRAPPED, ids=lambda p: p.stem)
def test_wrapped_prompts_list_inferred_once_and_never_hand_tag(path: Path) -> None:
    text = read(path)
    assert "--kind inferred" in text and re.search(r"never write `\[ai-draft\]` by hand", text, re.I)


CORRECT = EXT / "speckit.eil.correct.md"
SUMMARISING = [EXT / "speckit.eil.accept.md", CORRECT]
DECIDED_CLAUSE = [CORRECT, EXT / "speckit.eil.accept.md", *DRAFTING, *WRAPPED]


def test_correct_shows_before_apply() -> None:
    """FR-021: propose, show the owner, edit and impact, and get agreement before anything is written."""
    text = read(CORRECT)
    assert text.index("correct propose") < text.index("Get agreement") < text.index("correct open")
    assert re.search(r"show before applying", text, re.I) and re.search(r"only\*\* if `ambiguous`", text)
    assert re.search(r"never (supply|pass text you wrote)", text, re.I) and "verbatim" in text


@pytest.mark.parametrize("path", [CORRECT, *WRAPPED, WRAPS / "speckit.implement.md"], ids=lambda p: p.stem)
def test_rederive_only_listed(path: Path) -> None:
    text = read(path)
    assert "rederive" in text or "rederive[]" in text
    assert re.search(r"only\*{0,2} (the )?(sections|tasks|stages)|Never implement a task", text)


@pytest.mark.parametrize("path", DECIDED_CLAUSE, ids=lambda p: p.stem)
def test_decided_clause_removed_on_reedit(path: Path) -> None:
    assert re.search(r"\(decided: CR-###\)", read(path)) and re.search(r"remove", read(path), re.I)


@pytest.mark.parametrize("path", SUMMARISING, ids=lambda p: p.stem)
def test_summaries_passed(path: Path) -> None:
    text = read(path)
    assert "--summaries" in text and re.search(r"draft by the AI", text)


PURPOSE_STATED = [EXT / f"speckit.eil.{n}.md" for n in ("status", "next", "approve", "challenge")]


@pytest.mark.parametrize("path", PURPOSE_STATED, ids=lambda p: p.stem)
def test_purpose_stated(path: Path) -> None:
    """Principle IV, FR-032: each request to a person says its purpose, from the helper's `purpose`."""
    text = read(path)
    assert "purpose" in text and re.search(r"awareness.*understanding.*decision.*validation.*approval", text, re.S)


def test_challenge_prompt_rates_severity_and_leads_with_the_highest() -> None:
    text = read(EXT / "speckit.eil.challenge.md")
    assert "--severity" in text and "challenge severity" in text
    assert re.search(r"high.{0,40}first", text, re.I | re.S) and re.search(r"label.{0,40}AI", text, re.I | re.S)


def test_approve_prompt_shows_the_focused_gate_and_outstanding_lows() -> None:
    text = read(EXT / "speckit.eil.approve.md")
    assert "outstanding" in text and re.search(r"unmet.{0,60}first|focused", text, re.I | re.S)


def test_complete_prompt_asks_only_what_implementation_touched() -> None:
    """FR-033, FR-040, FR-045: one reply per non-empty list, untouched artefacts listed without a question."""
    text = read(EXT / "speckit.eil.complete.md")
    for kind in ("low-challenges", "evidence", "tasks", "diagram-currency"):
        assert f"--kind {kind}" in text
    assert re.search(r"only.{0,40}non-empty|non-empty.{0,60}only|skip.{0,40}empty", text, re.I | re.S)
    assert "untouched" in text and re.search(r"without (?:a|any) question", text, re.I)
    assert "--defer-reason" in text and re.search(r"purpose", text)
    assert "--found-in completion" in text and re.search(r"correct.{0,80}not.{0,40}(?:annotat|deviation)", text, re.I | re.S)
    assert re.search(r"exists; result attested", text)


# ---- 003 Proportionate Effort: Tier 2 rules (contracts/commands.md, last table)

STARTING = [WRAPS / "speckit.specify.md", EXT / "speckit.eil.requirements.md"]


@pytest.mark.parametrize("path", STARTING, ids=lambda p: p.stem)
def test_pointer_not_reused(path: Path) -> None:
    """FR-005, FR-006 (probe P-30): a governed story's pointer is never reused for a new story,
    `--feature-dir` is always passed, and an unexpected branch is put to a person."""
    text = read(path)
    assert re.search(r"never reuse `\.specify/feature\.json` when it names a governed story", text, re.I)
    assert re.search(r"always pass `--feature-dir`", text, re.I)
    assert "unexpected-branch" in text and "--on-branch" in text
    assert re.search(r"ask the (developer|person) to switch branch or confirm", text, re.I)
    assert re.search(r"never (pass|supply) `--on-branch` (yourself|without)", text, re.I)


STAGE_COMMANDS = [
    EXT / f"speckit.eil.{n}.md"
    for n in (
        "requirements", "functional", "technical", "ai-spec", "verify", "complete", "comprehend", "approve",
        "accept", "correct", "challenge", "resolve", "trace", "status", "next",
    )
] + [WRAPS / f"speckit.{n}.md" for n in WRAP_PROMPTS]


@pytest.mark.parametrize("path", STAGE_COMMANDS, ids=lambda p: p.stem)
def test_show_not_raw(path: Path) -> None:
    """FR-012 (probe P-29): stages are read with `eil show`, never by opening the document, and the
    record file is never read."""
    text = read(path)
    assert "eil show" in text, f"{path.name} does not read stages with eil show"
    assert re.search(r"never read `eil-record\.json`", text, re.I), path.name
    assert not re.search(r"\*\*Read\*\* `s0\d", text), f"{path.name} still opens a stage document"


LIST_PRESENTERS = [
    EXT / f"speckit.eil.{n}.md"
    for n in ("requirements", "functional", "technical", "ai-spec", "accept", "verify", "complete", "correct", "approve")
] + [WRAPS / f"speckit.{n}.md" for n in ("plan", "tasks")]


@pytest.mark.parametrize("path", LIST_PRESENTERS, ids=lambda p: p.stem)
def test_list_mode_no_tally(path: Path) -> None:
    """FR-014 to FR-016 (probe P-28): a list is presented in the helper's mode, each answer is stored as
    it is given, "ok to the rest" is offered, and no tally is kept in chat."""
    text = read(path)
    assert re.search(r"in the helper'?s `mode`", text, re.I)
    assert "--entry" in text and "--rest" in text and re.search(r"ok to the rest", text, re.I)
    assert re.search(r"never keep a tally", text, re.I)
    assert re.search(r"never list a block the helper did not return", text, re.I)


def test_accept_resigns_a_legacy_approval_in_one_reply() -> None:
    """FR-025: the legacy statement is shown and one reply re-signs; a full re-approval is never asked."""
    text = read(EXT / "speckit.eil.accept.md")
    assert "legacy:<stage>" in text and re.search(r"one reply", text, re.I)
    assert re.search(r"never point the person to a full re-approval", text, re.I)
    assert "re-signed without comparison" in text


CHALLENGE_PROMPTS = [p for p in ALL_PROMPTS + [EXT / "speckit.eil.correct.md", EXT / "speckit.eil.accept.md"] if p.is_file() and "challenge add" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("path", CHALLENGE_PROMPTS, ids=lambda p: p.stem)
def test_challenge_severity_written(path: Path) -> None:
    """FR-039: every `challenge add` shows `--severity` and says it is required."""
    text = read(path)
    for line in [ln for ln in text.splitlines() if "challenge add" in ln]:
        assert "--severity" in line, f"{path.name}: {line.strip()[:80]}"
    assert re.search(r"severity[^.]{0,80}required|required[^.]{0,40}severity", text, re.I), path.name


def test_mechanism_not_asked() -> None:
    """FR-026 to FR-029 (probe P-24): only observable, scope or trade-off choices are asked, each with a
    recommended option; the rest are `Owner: ai-decided` with a `Reason:`; when unsure, ask; they are named
    in the summary. The Functional prompt never asks about mechanism."""
    technical = read(EXT / "speckit.eil.technical.md")
    assert re.search(r"observable effect, (the )?scope or a trade-off", technical, re.I)
    assert re.search(r"recommended option", technical, re.I)
    assert "Owner: ai-decided" in technical and "Reason:" in technical
    assert re.search(r"when (you are )?unsure, ask", technical, re.I)
    assert re.search(r"name every `ai-decided` (DEC|decision)", technical, re.I)
    assert re.search(r"a technical decision with an observable effect is the developer'?s, never yours", technical, re.I)
    functional = read(EXT / "speckit.eil.functional.md")
    assert re.search(r"never ask (the developer )?about mechanism", functional, re.I)


COMPREHEND = EXT / "speckit.eil.comprehend.md"


def test_item_shown_before_question() -> None:
    """FR-031 (probe P-25): the item is shown, with `eil show --items`, before each question; `--by` is
    passed to the plan; an `own-decision` level is never asked; the waiver is offered."""
    text = read(COMPREHEND)
    assert re.search(r"eil show <stage> --items", text) and re.search(r"before (each|every) question", text, re.I)
    assert "comprehension plan --stage <stage> --by" in text
    assert re.search(r"never ask an `own-decision` level", text, re.I)
    assert "comprehension waive" in text and re.search(r"waive", text, re.I)


def test_behaviour_questions_and_reread() -> None:
    """FR-030, FR-034 (probe P-26): questions are about behaviour; answers are judged on meaning and
    re-read against the item before any hint."""
    text = read(COMPREHEND)
    assert re.search(r"ask about behaviour", text, re.I) and re.search(r"not (about )?mechanism", text, re.I)
    assert re.search(r"judge (each|the) answer on (its )?meaning", text, re.I)
    assert re.search(r"re-read the answer against the item before (giving )?(a|any) hint", text, re.I)


@pytest.mark.parametrize("stage", ["functional", "technical"])
def test_gap_scan_while_drafting(stage: str) -> None:
    """FR-035 (probe P-27): before the first inferred list, the drafting command scans the items the
    comprehension check will target, and raises any gap as a challenge first."""
    text = read(EXT / f"speckit.eil.{stage}.md")
    scan = text.find(f"eil comprehension plan --stage {stage}")
    assert scan != -1, "the drafting pass does not run the plan"
    assert scan < text.index("--kind inferred"), "the scan comes before the first inferred list"
    assert re.search(r"silent", text, re.I) and re.search(r"ambiguous", text, re.I) and re.search(r"contradict", text, re.I)
    assert re.search(r"raise (each|every|any) gap as a challenge (first|before)", text, re.I)


PROFILE_PROPOSERS = [WRAPS / "speckit.specify.md", EXT / "speckit.eil.requirements.md", EXT / "speckit.eil.abbreviate.md"]


@pytest.mark.parametrize("path", PROFILE_PROPOSERS, ids=lambda p: p.stem)
def test_profile_proposed_not_authorised(path: Path) -> None:
    """FR-019, FR-020, FR-045 (probe P-23): the AI may propose the small-story profile, naming the signals
    and labelling it as its own assessment; only a person authorises it, in their own words; the AI says
    when the story outgrows it."""
    text = read(path)
    assert re.search(r"small-story profile", text, re.I)
    assert "AI assessment:" in text and re.search(r"nam(e|ing) the signals", text, re.I)
    assert re.search(r"ask who authorises (it )?and why", text, re.I)
    assert re.search(r"never run `(eil )?profile set` without the person'?s own words", text, re.I)
    assert re.search(r"outgrows the profile", text, re.I) and "profile withdraw" in text


DERIVED_PRESENTERS = [EXT / "speckit.eil.ai-spec.md", WRAPS / "speckit.plan.md", WRAPS / "speckit.tasks.md"]


@pytest.mark.parametrize("path", DERIVED_PRESENTERS, ids=lambda p: p.stem)
def test_profile_presents_one_derived_list(path: Path) -> None:
    """FR-021: under the profile, the AI Specification, plan and tasks are reviewed as one list after tasks."""
    text = read(path)
    assert re.search(r"under the small-story profile", text, re.I)
    assert "--stage derived" in text


APPROVERS = [EXT / f"speckit.eil.{n}.md" for n in ("approve", "complete", "accept")]


@pytest.mark.parametrize("path", APPROVERS, ids=lambda p: p.stem)
def test_short_approval_accepted(path: Path) -> None:
    """FR-047 to FR-049 (probe P-31): ask the helper's question; a one-word reply is a complete answer;
    the name is asked once per session; the AI never supplies the reply."""
    text = read(path)
    assert "next_action.question" in text or "question" in text and "helper" in text
    assert re.search(r"\"ok\", \"yes\" or \"approved\"", text)
    assert re.search(r"(do not|never) ask for a longer statement", text, re.I)
    assert re.search(r"name once per session|reuse it for every `--by`", text, re.I)
    assert not re.search(r"\*\"Yes, this is", text), "a full-sentence example reads as required wording"


# ---- 004 Browser Review Page: Tier 2 rules (contracts/commands.md, last table)

PAGE_PROMPTS = [EXT / f"speckit.eil.{n}.md" for n in ("requirements", "functional", "technical", "accept")]


@pytest.mark.parametrize("path", PAGE_PROMPTS, ids=lambda p: p.stem)
def test_review_surface_asked_once(path: Path) -> None:
    """FR-021 (probe P-32): the surface is asked once per session, with its purpose, and not again unless
    the person asks."""
    text = read(path)
    assert "Review on a page in your browser, or here in chat?" in text
    assert re.search(r"ask (this|it) once per session", text, re.I)
    assert re.search(r"how they review, not what they approve", text, re.I)
    assert re.search(r"ask again only if the person asks", text, re.I)


@pytest.mark.parametrize("path", PAGE_PROMPTS, ids=lambda p: p.stem)
def test_page_review_waits_for_done(path: Path) -> None:
    """FR-015, FR-022 (probe P-33): the page is found or started, its address given with what it shows,
    the list is not printed, and nothing is done with the review before the person says "done"."""
    text = read(path)
    assert "review serve --status --json" in text and 'review serve --by "<name>" --json' in text
    assert re.search(r"give (them )?the address", text, re.I) and re.search(r"which stage and list", text, re.I)
    assert re.search(r"do not print the list in chat", text, re.I)
    assert re.search(r"until they say \"?done\"?", text, re.I)
    assert re.search(r"ask (them|the person) to reload", text, re.I)


@pytest.mark.parametrize("path", PAGE_PROMPTS, ids=lambda p: p.stem)
def test_agent_never_uses_page(path: Path) -> None:
    """R-29 (probe P-33, extended): the agent never opens, fetches or posts to the page address; it only
    gives it to the person, and passes `--host` only when the person asks."""
    text = read(path)
    assert re.search(r"never open, fetch or post to the page address", text, re.I)
    assert re.search(r"give it to the person only", text, re.I)
    assert re.search(r"pass `--host` only when the person asks", text, re.I)


@pytest.mark.parametrize("path", PAGE_PROMPTS, ids=lambda p: p.stem)
def test_page_fallback_to_chat(path: Path) -> None:
    """FR-022 (probe P-35): when the page cannot start, say why in one line and review in chat as before."""
    text = read(path)
    assert re.search(r"cannot start", text, re.I)
    assert re.search(r"say why in one line", text, re.I)
    assert re.search(r"review in chat", text, re.I)
    assert re.search(r"never pass the AI'?s (own )?name", text, re.I)


@pytest.mark.parametrize("path", [*PAGE_PROMPTS, EXT / "speckit.eil.approve.md"], ids=lambda p: p.stem)
def test_approval_stays_in_chat(path: Path) -> None:
    """FR-020: approval, overrides, waivers and the comprehension check stay in chat; no prompt sends
    the person to the page for them."""
    text = read(path)
    assert re.search(r"approval, overrides, waivers and the comprehension check stay in chat", text, re.I)
    assert re.search(r"never send the person to the page (for|to) (approve|approval)", text, re.I)


@pytest.mark.parametrize("path", PAGE_PROMPTS, ids=lambda p: p.stem)
def test_page_answers_acted_on(path: Path) -> None:
    """FR-014, FR-016 (probe P-34): after "done", the stored answers come from the helper; each send-back
    is reworked with what changed, each question answered in chat; the person reloads and answers on
    the page; no answer to a page-surface entry is recorded in chat; a reopened block is a send-back."""
    text = read(path)
    assert "review list --current --json" in text and "last_answers" in text
    assert re.search(r"rework the block,? and say what changed", text, re.I)
    assert re.search(r"answer (it|each question) in chat, or raise a challenge", text, re.I)
    assert re.search(r"never record a page-surface entry'?s answer in chat", text, re.I)
    assert re.search(r"a comment on a settled block", text, re.I) and re.search(r"as (on|you would) a send-back", text, re.I)
    assert re.search(r"comprehension check, then approval in chat", text, re.I)


@pytest.mark.parametrize("path", [EXT / "speckit.eil.status.md", EXT / "speckit.eil.next.md"], ids=lambda p: p.stem)
def test_status_mentions_a_running_page(path: Path) -> None:
    """004 contracts/commands.md: when a review page is running, its address is mentioned in one line."""
    text = read(path)
    assert "review serve --status --json" in text and re.search(r"address, in one line|address in one line", text, re.I)
    assert re.search(r"never open, fetch or post to it", text, re.I)

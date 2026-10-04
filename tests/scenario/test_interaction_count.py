"""B-28 (T083): SC-001. Counts the calls that carry a person's name (``--by``) while the reference story
takes the same edits under the 001 helper and the current one, and compares them.

The 001 numbers are captured once from the helper at the git tag ``eil-001-baseline`` and committed to
``tests/fixtures/baseline-001-counts.json``. Regenerate them only on purpose with ``--update-baseline``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import reference_story as reference
from tests.helpers.derived import clear_approval, edit
from tests.helpers.package import Story

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]
CURRENT_HELPER = REPO / "extensions" / "eil" / "scripts" / "python" / "eil"
BASELINE_TAG = "eil-001-baseline"
BASELINE_FILE = REPO / "tests" / "fixtures" / "baseline-001-counts.json"
CLASSES = ("decision", "first-approval", "inferred-review", "other")
REQ1 = "**REQ-001**: The system detects duplicate customers on import."
DEVIATION = {
    "**REQ-002**: Analysts can review each flagged pair.": ("pair.", "pair, with a note."),
    "**REQ-003**: Analysts can merge or dismiss a flagged pair.": ("pair.", "pair in bulk."),
    "**REQ-004**: Every decision on a pair is auditable.": ("auditable.", "auditable and exportable."),
}
CONFIG = (
    "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
    "  technical: [Ada Dev]\n  completion: [Ada Dev]\n"
)


def classify(args: list[str], first_approvals: set[str]) -> str:
    match args:
        case ["challenge", "answer", *_] | ["override", *_]:
            return "decision"
        case ["approve", stage, *_] if stage in first_approvals:
            return "first-approval"
        case ["review", "answer", *_] if "inferred" in args:
            return "inferred-review"
    return "other"


class Session:
    """One replay of the story with one helper; counts every call carrying ``--by``."""

    def __init__(self, helper: Path, root: Path, generation: str) -> None:
        self.helper, self.root, self.generation = helper, root, generation
        self.counts: Counter[str] = Counter()
        self.calls: list[tuple[str, list[str]]] = []
        self.first_approvals: set[str] = set()

    def __call__(self, *args: str, ok: bool = True) -> Any:
        full = [*args, "--feature-dir", str(self.root), "--json"]
        proc = subprocess.run(
            ["python3", str(self.helper), *full], cwd=self.root, capture_output=True, text=True, check=False
        )
        if "--by" in args:
            kind = classify(list(args), self.first_approvals)
            self.counts[kind] += 1
            self.calls.append((kind, list(args)))
        if ok:
            assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None


def prepare(tmp_path: Path, helper: Path, generation: str) -> tuple[Session, Story]:
    story = reference.build(tmp_path / "specs" / "001-story")
    project = tmp_path
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(CONFIG, encoding="utf-8")
    (project / ".specify" / "templates").mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", project / ".specify" / "templates")
    if generation == "002":
        from tests.helpers.derived import settle_derived

        settle_derived(story)
    return Session(helper, story.root, generation), story


OQ1 = "**OQ-001**: Keep history? (status: resolved) (material: yes)"
REQUIREMENTS_JUDGED = ("REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13")


def replay(session: Session, story: Story) -> dict[str, int]:
    """The same story of edits under either helper; only the way each is brought back differs.

    A first approval of requirements, a decision correction, then three rewordings and an edit to a
    resolved question after approval. Not replayed: the functional and technical re-reviews these edits
    cause. Under 001 ``review accept`` refuses an upstream id there, so the only 001 route is a full
    re-approval with a fresh comprehension check, and neither stage's fixture meets those gates."""
    new = session.generation == "002"
    severity = ["--severity", "medium"] if new else []
    scratch = story.root.parent

    def write_summaries(stage: str, *keys: str) -> str:
        rows = [{"key": k, "summary": f"Summary of the change to {k}."} for k in keys]
        path = scratch / "summaries.json"
        path.write_text(json.dumps({"stage": stage, "summaries": rows}), encoding="utf-8")
        return str(path)

    def classify_blocks(*keys: str, adds: str | None = None) -> None:
        """The AI's own step after it edits (no person's name on it): the helper records each class."""
        if not new:
            return
        path = scratch / "classify.json"
        rows = [{"block": k, "adds": adds} for k in keys]
        path.write_text(json.dumps({"stage": "requirements", "blocks": rows}), encoding="utf-8")
        session("blocks", "classify", "--stage", "requirements", "--file", str(path))

    # the first approval, with the AI's judgments supplied as the gate needs
    judged = scratch / "requirements-judgments.json"
    judged.write_text(
        json.dumps({"stage": "requirements", "judgments": [{"id": i, "status": "met", "reason": "assessed"} for i in REQUIREMENTS_JUDGED]}),
        encoding="utf-8",
    )  # fmt: skip
    clear_approval(story, "requirements")
    session.first_approvals.add("requirements")
    session("check", "--stage", "requirements", "--judgments", str(judged))
    session("approve", "requirements", "--by", "Ada Dev", "--attestation", "I confirm the requirements.")

    # a decision correction after approval (mid-implementation)
    session("challenge", "add", "requirements", "--target", "REQ-001", "--text", "Be specific.", *severity)
    session("challenge", "answer", "CH-001", "--response", "accepted", "--by", "Ada Dev")
    edit(story, "requirements", REQ1, REQ1.replace("import.", "import, in real time.") + " (decided: CH-001)")
    classify_blocks("REQ-001")
    if new:
        session("review", "confirm", "--stage", "requirements", "--by", "Ada Dev", "--confirmation", "ok",
                "--summaries", write_summaries("requirements", "REQ-001"))  # fmt: skip
    else:
        session("amend", "requirements", "--from", "CH-001", "--by", "Ada Dev",
                "--attestation", "I confirm the requirements as amended.")  # fmt: skip

    # three rewordings and an edit to a resolved question
    for old, (a, b) in DEVIATION.items():
        edit(story, "requirements", old, old.replace(a, b))
    edit(story, "requirements", OQ1, OQ1.replace("Keep history?", "Keep history for seven years?"))
    keys = [old.split("**")[1] for old in DEVIATION] + ["OQ-001"]
    classify_blocks(*keys, adds="Adds detail the source does not state.")
    if new:
        inferred = session("review", "list", "--stage", "requirements", "--kind", "inferred")
        if inferred["entries"]:
            session("review", "answer", "--stage", "requirements", "--kind", "inferred", "--digest",
                    inferred["digest"], "--by", "Ada Dev", "--reply", "ok", "--all")  # fmt: skip
        listed = session("review", "list", "--stage", "requirements", "--kind", "changes")
        if listed["entries"]:
            session("review", "answer", "--stage", "requirements", "--kind", "changes", "--digest",
                    listed["digest"], "--by", "Ada Dev", "--reply", "ok", "--all")  # fmt: skip
        session("review", "confirm", "--stage", "requirements", "--by", "Ada Dev", "--confirmation", "ok",
                "--summaries", write_summaries("requirements", *keys))  # fmt: skip
    else:
        session("review", "start", "--stage", "requirements")
        for key in keys:
            session("review", "accept", "--stage", "requirements", "--items", key, "--by", "Ada Dev")
        session("review", "finish", "--stage", "requirements", "--by", "Ada Dev",
                "--attestation", "I confirm the requirements after review.")  # fmt: skip

    return {name: session.counts[name] for name in CLASSES}


def test_baseline_capture_is_reproducible_in_shape() -> None:
    assert set(json.loads(BASELINE_FILE.read_text())["counts"]) == set(CLASSES)


def measured(tmp_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    baseline = json.loads(BASELINE_FILE.read_text())["counts"]
    session, story = prepare(tmp_path, CURRENT_HELPER, "002")
    return baseline, replay(session, story)


def test_decisions_and_first_approvals_are_unchanged(tmp_path: Path) -> None:
    baseline, now = measured(tmp_path)
    assert now["decision"] == baseline["decision"] > 0
    assert now["first-approval"] == baseline["first-approval"]


def test_other_interactions_fall_by_at_least_sixty_percent(tmp_path: Path) -> None:
    baseline, now = measured(tmp_path)
    assert baseline["other"] > 0
    assert now["other"] <= baseline["other"] * 0.4, (baseline, now)


def capture_baseline(tmp_path: Path) -> dict[str, Any]:
    worktree = tmp_path / "eil-baseline"
    subprocess.run(["git", "worktree", "add", "--detach", str(worktree), BASELINE_TAG], cwd=REPO, check=True,
                   capture_output=True)  # fmt: skip
    try:
        helper = worktree / "extensions" / "eil" / "scripts" / "python" / "eil"
        session, story = prepare(tmp_path / "run", helper, "001")
        counts = replay(session, story)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=REPO, check=True,
                       capture_output=True)  # fmt: skip
    commit = subprocess.run(
        ["git", "rev-parse", BASELINE_TAG], cwd=REPO, capture_output=True, text=True, check=True
    )
    return {"tag": BASELINE_TAG, "commit": commit.stdout.strip(), "counts": counts,
            "calls": [{"class": k, "args": a} for k, a in session.calls]}  # fmt: skip


@pytest.fixture(scope="session", autouse=True)
def _maybe_update_baseline(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> None:
    if request.config.getoption("--update-baseline", default=False):
        data = capture_baseline(tmp_path_factory.mktemp("baseline"))
        BASELINE_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---- 003 SC-005: developer replies from requirements to implementation, under the small-story profile


def first_pass(tmp_path: Path, generation: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """The replies a developer gives on a first pass from requirements to implementation, measured with
    the helper on the reference story, and counted by this model (one reply per item):

    * the profile's authorisation (003 only) and the three definition approvals;
    * every decision question: under 002 every DEC was asked; under 003 the two with no observable
      effect are recorded `ai-decided` and validated on the review list instead;
    * a wireframe export unless the gate's wireframe criterion is met without one;
    * every comprehension level the helper plans as a question (`status: ok`), after the stage's review
      list has been answered (002 had no `--by`, so no own decision was left out);
    * one reply per review list: three definition lists, then three derived lists (002) or one (003).

    The comprehension check's gate prerequisites are not modelled; nothing else is changed."""
    from eil import blockstatus, comprehension, profile, provenance, reviews
    from eil.gates import check_stage
    from eil.identity import Config
    from eil.package import Package
    from eil.trace import ai_decided_ids, parse_document

    from tests.helpers.package import with_record_sections

    monkeypatch.setattr(comprehension, "_require_prerequisites", lambda pkg, stage: None)
    config = Config(
        default_developer="Ada Dev",
        approvers={s: ["Ada Dev"] for s in ("requirements", "functional", "technical")},
        abbreviation_authorisers=["Ada Dev"],
    )
    story = reference.build(tmp_path / generation / "specs" / "001-story")
    if generation == "003":
        text = story.read("technical")
        for n in (3, 4):  # queue per import file; retry three times: nothing a user observes changes
            text = text.replace(
                f"Trade-off: Trade-off {n}.\nOwner: Ada Dev", f"Trade-off: Trade-off {n}.\nOwner: ai-decided"
            )
        story.write("technical", text)
    for stage in ("functional", "technical"):
        clear_approval(story, stage)
        story.write(stage, with_record_sections(story.read(stage)))
    for stage in ("ai-spec", "plan", "tasks"):
        story.write(stage, with_record_sections(story.read(stage)))
    root = story.root
    counts: dict[str, int] = {}
    if generation == "003":
        profile.set_profile(
            Package(root), config, "small", by="Ada Dev", reason="A detailed request for a small change"
        )
        counts["profile"] = 1
    counts["approvals"] = 3
    decisions = [i for i in parse_document(Package(root).doc("technical")).items if i.kind == "DEC"]
    counts["decisions"] = len(decisions) - len(ai_decided_ids(decisions))
    criterion = next(
        c for c in check_stage(Package(root), "functional", write=False).criteria if c.id == "FUN-G15"
    )
    counts["wireframes"] = 0 if generation == "003" and criterion.status == "met" else 1
    counts["lists"] = 0
    for stage in ("functional", "technical"):
        keys = [b.key for b in blockstatus.blocks_of(Package(root).doc(stage))]
        provenance.classify(
            Package(root), stage, {"stage": stage, "blocks": [{"block": k, "adds": None} for k in keys]}
        )
        listed = reviews.build_list(Package(root), stage, "inferred")
        if listed.entries:
            reviews.answer(
                Package(root),
                config,
                stage,
                "inferred",
                digest=listed.digest,
                by="Ada Dev",
                reply="ok",
                all_=True,
            )
        rows = comprehension.plan(Package(root), stage, by="Ada Dev" if generation == "003" else None)[
            "levels"
        ]
        counts[f"comprehension {stage}"] = sum(1 for r in rows if r["status"] == "ok")
    counts["lists"] = 3
    if generation == "003":
        counts["lists"] += 1 if reviews.build_list(Package(root), "derived", "inferred").entries else 0
    else:
        counts["lists"] += sum(
            1
            for s in ("ai-spec", "plan", "tasks")
            if reviews.build_list(Package(root), s, "inferred").entries
        )
    return counts


def test_sc005_approvals_and_observable_decisions_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before, after = first_pass(tmp_path, "002", monkeypatch), first_pass(tmp_path, "003", monkeypatch)
    assert after["approvals"] == before["approvals"] == 3
    assert after["decisions"] == 3, "the three decisions with an observable effect are still asked"
    assert sum(after.values()) < sum(before.values())


@pytest.mark.xfail(
    strict=True,
    reason="SC-005 target not met: measured 40% fewer replies on the reference story (25 under 002, 15 under "
    "the profile), against a target of 50%; see specs/003-proportionate-effort/research.md, Evidence",
)
def test_sc005_replies_fall_by_at_least_half(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before, after = first_pass(tmp_path, "002", monkeypatch), first_pass(tmp_path, "003", monkeypatch)
    assert sum(after.values()) <= sum(before.values()) * 0.5, (before, after)

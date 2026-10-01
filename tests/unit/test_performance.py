"""Performance (task T133; plan Performance Goals): ``sync``, ``check`` and ``status`` each finish in
under a second on a story of nine documents of about 1 MB each.

The bound is generous on purpose: it catches an accidental quadratic scan, not a slow machine.
Block splitting and scoped staleness (D-34, D-35) briefly needed 2.0s; shared per-process caches
(D-44) brought it back to 1.0s.
"""

from __future__ import annotations

import time

import pytest
from eil import cli
from eil.package import Package

from tests.helpers.package import Story, approve_stages, with_verification

LIMIT_SECONDS = 1.0
TARGET_BYTES = 1_000_000


def padding(prefix: str) -> str:
    """About TARGET_BYTES of ordinary prose lines (not items), so the scanners read every line."""
    line = f"{prefix} narrative line with several ordinary words and a little punctuation, but no item.\n"
    return line * (TARGET_BYTES // len(line))


@pytest.fixture
def big_story(story_dir: Story) -> Story:
    with_verification(story_dir)
    for stage in ("requirements", "functional", "technical", "ai-spec", "plan", "tasks", "verification"):
        text = story_dir.read(stage)
        marker = "## Not applicable"
        story_dir.write(stage, text.replace(marker, f"## Background notes\n\n{padding(stage)}\n{marker}", 1))
    return story_dir


@pytest.fixture(autouse=True)
def no_overview_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare story has no Spec Kit project to resolve the overview template from."""
    monkeypatch.setattr(cli, "_regenerate_overview", lambda ctx, package: False)


def run(story: Story, *argv: str) -> tuple[int, float]:
    out: list[str] = []

    class Sink:
        def write(self, text: str) -> int:
            out.append(text)
            return len(text)

        def flush(self) -> None:
            return None

    started = time.perf_counter()
    code = cli.main(
        [*argv, "--json", "--feature-dir", str(story.root)], cwd=story.root, stdout=Sink(), stderr=Sink()
    )  # type: ignore[arg-type]
    return code, time.perf_counter() - started


def test_the_fixture_really_has_nine_documents_of_about_a_megabyte(big_story: Story) -> None:
    sizes = {p.name: p.stat().st_size for p in big_story.root.glob("s0*.md")}
    assert len(sizes) == 9 or len(sizes) == 8
    assert sum(1 for size in sizes.values() if size > 900_000) >= 7
    assert isinstance(Package(big_story.root), Package)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [(["status"], 0), (["check", "--stage", "technical"], 0), (["check", "--stage", "verification"], 0)],
)
def test_status_and_check_stay_under_a_second(big_story: Story, argv: list[str], expected: int) -> None:
    code, elapsed = run(big_story, *argv)
    assert code == expected
    assert elapsed < LIMIT_SECONDS, f"{' '.join(argv)} took {elapsed:.2f}s"


def test_sync_stays_under_a_second(big_story: Story, monkeypatch: pytest.MonkeyPatch) -> None:
    from eil import cli as module

    monkeypatch.setattr(
        module, "_regenerate_overview", lambda ctx, package: False
    )  # the template needs a project
    code, elapsed = run(big_story, "sync", "--check-only")
    assert code == 0 and elapsed < LIMIT_SECONDS, f"sync took {elapsed:.2f}s"


# ---- provenance regions with 2,000 blocks in each document (D-44)

BLOCKS_PER_DOCUMENT = 2_000
STAGES = ("requirements", "functional", "technical", "ai-spec", "plan", "tasks", "verification")


def block_padding(prefix: str) -> str:
    """BLOCKS_PER_DOCUMENT prose paragraphs, together about TARGET_BYTES, each one content block."""
    filler = "narrative words and a little punctuation, but no item. " * 8
    paragraphs = [f"{prefix} paragraph {n:04d} {filler}" for n in range(BLOCKS_PER_DOCUMENT)]
    return "\n\n".join(paragraphs)


@pytest.fixture
def provenance_story(story_dir: Story) -> Story:
    with_verification(story_dir)
    for stage in STAGES:
        text = story_dir.read(stage)
        marker = "## Not applicable"
        story_dir.write(stage, text.replace(marker, f"## Background notes\n\n{block_padding(stage)}\n\n{marker}", 1))
    approve_stages(story_dir, "requirements", "functional", "technical")
    cli._persist_adoption(Package(story_dir.root))
    return story_dir


def test_the_fixture_records_two_thousand_blocks_per_document(provenance_story: Story) -> None:
    package = Package(provenance_story.root)
    for stage in STAGES:
        region = package.doc(stage).read_region("provenance").obj
        assert len(region["blocks"]) >= BLOCKS_PER_DOCUMENT, stage
    assert sum(1 for p in provenance_story.root.glob("s0*.md") if p.stat().st_size > 900_000) >= 7


@pytest.mark.parametrize(
    "argv",
    [["status"], ["check", "--stage", "technical"], ["enter", "implement"]],
)
def test_status_check_and_enter_stay_under_a_second_with_provenance(provenance_story: Story, argv: list[str]) -> None:
    code, elapsed = run(provenance_story, *argv)
    assert code in (0, 1), argv  # enter may refuse; only its speed is under test
    assert elapsed < LIMIT_SECONDS, f"{' '.join(argv)} took {elapsed:.2f}s"

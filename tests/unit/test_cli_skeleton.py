"""CLI skeleton: governed check, exit codes, JSON shape (task T025; FR-006, FR-069, determinism 8)."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil import cli
from eil.results import Refusal, refuse

from tests.helpers.package import Story

# Minimal valid arguments for each subcommand that requires a governed feature.
GOVERNED_ONLY: list[list[str]] = [
    ["sync"],
    ["enter", "plan"],
    ["check"],
    ["stage-init", "functional"],
    ["challenge", "add", "functional", "--target", "FR-001", "--text", "gap"],
    ["challenge", "answer", "CH-001", "--response", "accepted", "--by", "Ada"],
    ["approve", "requirements", "--by", "Ada", "--attestation", "yes"],
    ["override", "requirements", "--criterion", "REQ-G01", "--by", "Ada", "--reason", "r"],
    ["amend", "requirements", "--from", "CH-001", "--by", "Ada", "--attestation", "yes"],
    ["abbreviate", "requirements", "--by", "Ada", "--reason", "r"],
    ["resolve", "--id", "AIS-001", "--stage", "requirements"],
    [
        "artifact",
        "register",
        "--id",
        "ART-001",
        "--file",
        "x.png",
        "--kind",
        "wireframe",
        "--source-tool",
        "figma",
        "--source-url",
        "https://f.example/?node-id=1-2",
    ],
    ["artifact", "list"],
    ["comprehension", "plan", "--stage", "functional"],
    [
        "comprehension",
        "record",
        "--stage",
        "functional",
        "--level",
        "recognise",
        "--outcome",
        "understood",
        "--by",
        "Ada",
    ],
    ["trace"],
    ["status"],
    ["overview"],
]


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def run_main(argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, cwd=cwd, env=env if env is not None else {}, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def restore_handlers() -> Callable[[], None]:
    saved = dict(cli.HANDLERS)
    yield lambda: None
    cli.HANDLERS.clear()
    cli.HANDLERS.update(saved)


# ---- not governed (determinism 8)


@pytest.mark.parametrize("argv", GOVERNED_ONLY, ids=[" ".join(a[:2]) for a in GOVERNED_ONLY])
def test_every_subcommand_but_start_exits_3_and_changes_nothing_when_not_governed(
    argv: list[str], run_eil: Callable, tmp_path: Path
) -> None:
    (tmp_path / "specs" / "000-legacy").mkdir(parents=True)
    (tmp_path / "specs" / "000-legacy" / "spec.md").write_text("ordinary spec\n")
    before = snapshot(tmp_path)
    result = run_eil([*argv, "--json", "--feature-dir", "specs/000-legacy"], tmp_path)
    assert result.code == 3, result.stderr
    assert result.json == {"governed": False, "story": "000-legacy"}  # every result names its story (003)
    assert snapshot(tmp_path) == before


def test_with_no_feature_directory_at_all_it_is_also_not_governed(run_eil: Callable, tmp_path: Path) -> None:
    result = run_eil(["status", "--json"], tmp_path)
    assert result.code == 3 and result.json == {"governed": False, "story": None}


def test_a_directory_without_the_overview_is_not_governed_even_with_stage_documents(
    run_eil: Callable, tmp_path: Path
) -> None:
    feature = tmp_path / "specs" / "001-x"
    feature.mkdir(parents=True)
    (feature / "s01-requirements.md").write_text("# R\n")
    assert run_eil(["status", "--json", "--feature-dir", "specs/001-x"], tmp_path).code == 3


def test_text_mode_says_why_on_stderr(tmp_path: Path) -> None:
    code, out, err = run_main(["status"], tmp_path)
    assert code == 3 and out == "" and "s00-README.md" in err


# ---- output and exit codes


def test_json_mode_prints_exactly_one_object(restore_handlers: Callable, story_dir: Story) -> None:
    cli.HANDLERS["status"] = lambda ctx, args: {"ok": True, "governed": True}
    code, out, _ = run_main(["status", "--json", "--feature-dir", str(story_dir.root)], story_dir.root)
    assert code == 0
    assert out.count("\n") == 1 and json.loads(out) == {"ok": True, "governed": True, "story": story_dir.root.name}


def test_global_flags_are_accepted_before_or_after_the_subcommand(
    restore_handlers: Callable, story_dir: Story
) -> None:
    cli.HANDLERS["status"] = lambda ctx, args: {"ok": True}
    feature = str(story_dir.root)
    for argv in (
        ["--json", "--feature-dir", feature, "status"],
        ["status", "--json", "--feature-dir", feature],
    ):
        code, out, _ = run_main(argv, story_dir.root)
        assert code == 0 and json.loads(out) == {"ok": True, "story": story_dir.root.name}


def test_a_refusal_exits_1_with_the_documented_shape(restore_handlers: Callable, story_dir: Story) -> None:
    def refusing(ctx: cli.Context, args: object) -> dict:
        raise refuse(Refusal("unmet-criteria", "REQ-G03 is not met", "Fix REQ-G03 then retry"))

    cli.HANDLERS["approve"] = refusing
    argv = ["approve", "requirements", "--by", "Ada", "--attestation", "yes", "--json"]
    code, out, _ = run_main([*argv, "--feature-dir", str(story_dir.root)], story_dir.root)
    assert code == 1
    assert json.loads(out) == {
        "ok": False,
        "refusals": [
            {"code": "unmet-criteria", "message": "REQ-G03 is not met", "fix": "Fix REQ-G03 then retry"}
        ],
        "story": story_dir.root.name,
    }


def test_a_refusal_in_text_mode_goes_to_stderr(restore_handlers: Callable, story_dir: Story) -> None:
    def refusing(ctx: cli.Context, args: object) -> dict:
        raise refuse(Refusal("not-a-confirmer", "Mallory is not a confirmer", "Ask a configured approver"))

    cli.HANDLERS["approve"] = refusing
    code, out, err = run_main(
        ["approve", "requirements", "--by", "M", "--attestation", "y", "--feature-dir", str(story_dir.root)],
        story_dir.root,
    )
    assert code == 1 and out == ""
    assert "not-a-confirmer" in err and "Ask a configured approver" in err


def test_refusal_codes_must_be_registered() -> None:
    with pytest.raises(ValueError):
        Refusal("made-up-code", "x")


def test_an_unexpected_exception_is_exit_4_not_a_traceback(
    restore_handlers: Callable, story_dir: Story
) -> None:
    def broken(ctx: cli.Context, args: object) -> dict:
        raise RuntimeError("boom")

    cli.HANDLERS["status"] = broken
    code, out, err = run_main(["status", "--json", "--feature-dir", str(story_dir.root)], story_dir.root)
    assert code == 4
    payload = json.loads(out)
    assert payload["ok"] is False and "boom" in payload["error"]
    assert "Traceback" not in err


def test_an_unimplemented_handler_is_a_clear_internal_error(story_dir: Story) -> None:
    saved = cli.HANDLERS.pop("trace", None)
    try:
        code, out, _ = run_main(["trace", "--json", "--feature-dir", str(story_dir.root)], story_dir.root)
    finally:
        if saved is not None:
            cli.HANDLERS["trace"] = saved
    assert code == 4 and "not implemented" in json.loads(out)["error"]


# ---- usage errors


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["nonsense"],
        ["approve"],
        ["approve", "requirements", "--by", "Ada"],
        ["enter", "deploy"],
        ["challenge", "answer", "CH-001", "--response", "maybe", "--by", "Ada"],
        [
            "comprehension",
            "record",
            "--stage",
            "functional",
            "--level",
            "recognise",
            "--outcome",
            "passed",
            "--by",
            "A",
        ],
        ["artifact", "register", "--id", "ART-001"],
        ["fingerprint"],
    ],
)
def test_usage_errors_exit_2(argv: list[str], tmp_path: Path) -> None:
    code, _, err = run_main(argv, tmp_path)
    assert code == 2 and err.strip()


def test_usage_errors_under_json_still_print_one_object(tmp_path: Path) -> None:
    code, out, _ = run_main(["approve", "--json"], tmp_path)
    assert code == 2
    payload = json.loads(out)
    assert payload["ok"] is False and payload["error"]


def test_no_subcommand_prints_usage(tmp_path: Path) -> None:
    code, _, err = run_main([], tmp_path)
    assert code == 2 and "usage" in err.lower()


# ---- start is the one command that runs without a governed feature


def test_start_is_not_blocked_by_the_governed_check(restore_handlers: Callable, tmp_path: Path) -> None:
    cli.HANDLERS["start"] = lambda ctx, args: {"ok": True, "started": args.title}
    code, out, _ = run_main(["start", "--title", "Dup", "--json", "--feature-dir", "specs/001-x"], tmp_path)
    assert code == 0 and json.loads(out)["started"] == "Dup"


# ---- fingerprint is a plain utility


def test_fingerprint_works_in_an_ungoverned_project(run_eil: Callable, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_bytes(b"A\r\n\r\nB")
    result = run_eil(["fingerprint", "README.md"], tmp_path)
    expected = "sha256:" + hashlib.sha256(b"A\n\nB\n").hexdigest()
    assert result.code == 0 and result.stdout.strip() == expected


def test_fingerprint_json(run_eil: Callable, tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("A\n")
    result = run_eil(["fingerprint", "a.md", "--json"], tmp_path)
    assert result.json["ok"] is True and result.json["fingerprint"].startswith("sha256:")


def test_fingerprint_of_an_unreadable_file_exits_2(run_eil: Callable, tmp_path: Path) -> None:
    result = run_eil(["fingerprint", "missing.md"], tmp_path)
    assert result.code == 2


def test_fingerprint_of_a_non_utf8_file_exits_2(run_eil: Callable, tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe")
    result = run_eil(["fingerprint", "bad.md", "--json"], tmp_path)
    assert result.code == 2 and result.json["ok"] is False and "not-utf8" in result.json["error"]


# ---- feature directory resolution reaches the handlers


def test_environment_variable_selects_the_feature_directory(
    restore_handlers: Callable, story_dir: Story
) -> None:
    seen: list[Path] = []
    cli.HANDLERS["status"] = lambda ctx, args: seen.append(ctx.package().root) or {"ok": True}
    code, _, _ = run_main(
        ["status", "--json"], story_dir.root.parents[1], env={"SPECIFY_FEATURE_DIRECTORY": "specs/001-story"}
    )
    assert code == 0 and seen == [story_dir.root]


def test_running_as_python3_dir_works_from_any_directory(run_eil: Callable, tmp_path: Path) -> None:
    """C-04 in miniature: the entry point adds its own parent to sys.path."""
    (tmp_path / "f.md").write_text("x\n")
    assert run_eil(["fingerprint", "f.md"], tmp_path).code == 0

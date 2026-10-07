"""Claude Code adapter for behavioural trials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tests.agent.harness import TrialInput, TrialRun

_ENV_ALLOWLIST = frozenset({"LANG", "LC_ALL", "PATH", "SSL_CERT_DIR", "SSL_CERT_FILE", "TZ"})
_HELPER = Path(".specify/extensions/eil/scripts/python/eil")
_DEFAULT_TOOLS = (
    "Bash(python3 .specify/extensions/eil/scripts/python/eil *)",
    "Read",
    "Edit",
    "Skill",
)


@dataclass(frozen=True)
class ClaudeTurn:
    session_id: str
    exit_status: int
    duration_seconds: float
    transcript: str
    payload: dict[str, object]


class ClaudeRunner:
    def __init__(
        self,
        *,
        executable: Path | None = None,
        bubblewrap: Path | None = None,
        agent_home: Path | None = None,
        environ: Mapping[str, str] | None = None,
        model: str | None = None,
        allowed_tools: tuple[str, ...] = _DEFAULT_TOOLS,
    ) -> None:
        self.executable = executable or _which("claude")
        self.bubblewrap = bubblewrap or _which("bwrap")
        self.agent_home = (agent_home or _agent_home()).resolve()
        if self.agent_home == Path.home().resolve():
            raise ValueError("EIL_AGENT_HOME must be a dedicated test home, not the real home")
        self.environ = dict(os.environ if environ is None else environ)
        self.model = model
        self.allowed_tools = allowed_tools

    def invocation(
        self, trial: TrialInput, *, prompt: str | None = None, session_id: str | None = None
    ) -> tuple[list[str], dict[str, str]]:
        workspace = trial.workspace.resolve()
        environment = {key: value for key, value in self.environ.items() if key in _ENV_ALLOWLIST}
        environment["HOME"] = "/home/agent"
        command = [
            str(self.bubblewrap),
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]
        for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
            if Path(system_path).exists():
                command += ["--ro-bind", system_path, system_path]
        command += [
            "--dir",
            "/home",
            "--bind",
            str(self.agent_home),
            "/home/agent",
            "--bind",
            str(workspace),
            "/workspace",
            "--ro-bind",
            str(self.executable.resolve()),
            "/tmp/claude",
            "--chdir",
            "/workspace",
            "/tmp/claude",
            "--print",
            "--output-format",
            "json",
            "--restricted",
            "--strict-mcp-config",
            "--permission-prompts",
            "none",
            "--allowedTools",
            *self.allowed_tools,
        ]
        if self.model:
            command += ["--model", self.model]
        if session_id:
            command += ["--resume", session_id]
        command.append(trial.prompt if prompt is None else prompt)
        return command, environment

    def run_turn(
        self, trial: TrialInput, *, prompt: str | None = None, session_id: str | None = None
    ) -> ClaudeTurn:
        command, environment = self.invocation(trial, prompt=prompt, session_id=session_id)
        started = time.monotonic()
        proc = subprocess.run(
            command,
            cwd=trial.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.monotonic() - started
        payload = _parse_output(proc.stdout)
        transcript = str(payload.get("result", proc.stdout or proc.stderr))
        return ClaudeTurn(
            session_id=_session_id(payload),
            exit_status=proc.returncode,
            duration_seconds=duration,
            transcript=transcript,
            payload=payload,
        )

    def run(self, trial: TrialInput) -> TrialRun:
        state_before = _helper_json(trial.workspace, "status")
        record_before = _read_json(trial.workspace / trial.feature_dir / "eil-record.json")
        command, environment = self.invocation(trial)
        started = time.monotonic()
        proc = subprocess.run(
            command,
            cwd=trial.workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.monotonic() - started
        payload = _parse_output(proc.stdout)
        transcript = str(payload.get("result", proc.stdout or proc.stderr))
        state_after = _helper_json(trial.workspace, "status")
        record_after = _read_json(trial.workspace / trial.feature_dir / "eil-record.json")
        changed_files = tuple(_git(trial.workspace, "status", "--porcelain", "--untracked-files=all"))
        changed_files = tuple(line[3:] for line in changed_files if line.strip())
        return TrialRun(
            trial=trial,
            agent="claude-code",
            model=self.model or _reported_model(payload),
            exit_status=proc.returncode,
            duration_seconds=duration,
            transcript=transcript,
            state_before=state_before,
            state_after=state_after,
            record_before=record_before,
            record_after=record_after,
            changed_files=changed_files,
            workspace_diff=_workspace_diff(trial.workspace),
        )


def _which(name: str) -> Path:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"required executable is unavailable: {name}")
    return Path(found)


def _agent_home() -> Path:
    value = os.environ.get("EIL_AGENT_HOME")
    if not value:
        raise RuntimeError("set EIL_AGENT_HOME to a dedicated Claude test home")
    return Path(value)


def _helper_json(workspace: Path, command: str) -> dict[str, object]:
    proc = subprocess.run(
        ["python3", str(_HELPER), command, "--json"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"collection_error": proc.stderr or proc.stdout, "exit_status": proc.returncode}
    return _decode_json(proc.stdout)


def _read_json(path: Path) -> dict[str, object]:
    try:
        return _decode_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        return {"collection_error": str(error)}


def _decode_json(text: str) -> dict[str, object]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        return {"collection_error": str(error), "raw": text}
    return value if isinstance(value, dict) else {"collection_error": "expected a JSON object", "raw": value}


def _parse_output(text: str) -> dict[str, object]:
    return _decode_json(text) if text.strip() else {}


def _reported_model(payload: dict[str, object]) -> str | None:
    direct = payload.get("model")
    if isinstance(direct, str):
        return direct
    usage = payload.get("modelUsage")
    if isinstance(usage, dict) and usage:
        return str(next(iter(usage)))
    return None


def _session_id(payload: dict[str, object]) -> str:
    value = payload.get("session_id")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Claude structured output did not contain a session_id")
    return value


def _git(workspace: Path, *args: str) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, check=False)
    return proc.stdout.splitlines()


def _workspace_diff(workspace: Path) -> str:
    tracked = "\n".join(_git(workspace, "diff", "--no-ext-diff", "HEAD"))
    untracked = _git(workspace, "ls-files", "--others", "--exclude-standard")
    additions: list[str] = []
    for relative in untracked:
        proc = subprocess.run(
            ["git", "diff", "--no-index", "--", "/dev/null", relative],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        additions.append(proc.stdout)
    return tracked + ("\n" if tracked and additions else "") + "".join(additions)

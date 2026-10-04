"""Who may confirm, and who the story's developer is (task T037; FR-012, FR-013, FR-045, FR-066,
research D-11).

Configuration lives in ``.specify/extensions/eil/eil-config.yml`` with a machine-local
``local-config.yml`` on top. The helper may use only the standard library, so it carries a reader
for the small YAML subset those files use.

These checks are attestation-level (constitution Principle II): they make an approval by an
unlisted person, or by the AI, a mechanical refusal. They cannot prove who is at the keyboard.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .results import Refusal

CONFIG_DIR = Path(".specify") / "extensions" / "eil"
CONFIG_FILES = ("eil-config.yml", "local-config.yml")
CONFIG_STAGES = (
    "requirements",
    "functional",
    "technical",
    "completion",
    "ai-spec",
    "plan",
    "tasks",
    "verification",
)
DERIVED_APPROVER_STAGES = frozenset({"ai-spec", "plan", "tasks", "verification"})

# Names that are the AI, not a person. Matched on the whole name so "Ai Nguyen" is a person.
_AI_NAMES = frozenset(
    {
        "ai",
        "the ai",
        "ai agent",
        "ai assistant",
        "agent",
        "assistant",
        "bot",
        "llm",
        "copilot",
        "chatgpt",
        "gpt",
        "claude",
        "claude code",
    }
)


class ConfigError(Exception):
    """A configuration file cannot be read (reported as a usage error, exit 2)."""


# ---- a small YAML subset

_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w\-]*)\s*:\s*(?P<value>.*)$")


def _strip_comment(text: str) -> str:
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t"):
            return text[:index]
    return text


def _scalar(text: str) -> Any:
    text = text.strip()
    if text in ("", "null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _flow_list(text: str) -> list[Any]:
    inner = text.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        raise ConfigError(f"unclosed list: {text!r}")
    inner = inner[1:-1]
    items: list[str] = []
    current: list[str] = []
    quote = ""
    for char in inner:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    if quote:
        raise ConfigError(f"unclosed quote in list: {text!r}")
    items.append("".join(current))
    return [_scalar(item) for item in items if item.strip()]


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Mappings by indentation, ``key: value``, flow lists ``[a, b]``, block lists ``- item``."""
    rows: list[tuple[int, str, int]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ConfigError(f"line {number}: tabs are not allowed for indentation")
        line = _strip_comment(raw).rstrip()
        if line.strip():
            rows.append((len(line) - len(line.lstrip(" ")), line.strip(), number))

    def block(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(rows):
            level, content, number = rows[index]
            if level < indent:
                break
            if level > indent:
                raise ConfigError(f"line {number}: unexpected indentation")
            match = _KEY.match(content)
            if not match:
                raise ConfigError(f"line {number}: expected 'key: value', got {content!r}")
            key, value = match["key"], match["value"].strip()
            index += 1
            if value:
                result[key] = _flow_list(value) if value.startswith("[") else _scalar(value)
                continue
            if index < len(rows) and rows[index][1].startswith("- ") and rows[index][0] >= indent:
                items: list[Any] = []
                item_indent = rows[index][0]
                while index < len(rows) and rows[index][0] == item_indent and rows[index][1].startswith("- "):
                    items.append(_scalar(rows[index][1][2:]))
                    index += 1
                result[key] = items
            elif index < len(rows) and rows[index][0] > indent:
                result[key], index = block(index, rows[index][0])
            else:
                result[key] = None
        return result, index

    if rows and rows[0][1].startswith("- "):
        raise ConfigError(f"line {rows[0][2]}: a list item needs a key")
    parsed, index = block(0, rows[0][0] if rows else 0)
    if index < len(rows):
        raise ConfigError(f"line {rows[index][2]}: could not read {rows[index][1]!r}")
    return parsed


# ---- configuration


@dataclass
class Config:
    default_developer: str | None = None
    approvers: dict[str, list[str]] = field(default_factory=lambda: {stage: [] for stage in CONFIG_STAGES})
    abbreviation_authorisers: list[str] = field(default_factory=list)
    # Branches a story may be started on without asking (D-47).
    main_branches: list[str] = field(default_factory=lambda: ["main", "master"])
    # The longest review list presented one entry at a time (D-51).
    one_at_a_time_max: int = 8
    # The review page stops after this many minutes without use (004 D-66).
    page_idle_minutes: int = 60
    # The one script a browser may load to draw diagrams on the review page; ``None`` shows source (D-69).
    diagram_script: str | None = None


def _names(value: Any, where: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, (str, int)) for v in value):
        raise ConfigError(f"{where} must be a list of names")
    return [str(v) for v in value]


def load_config(project_root: Path) -> Config:
    """Read ``eil-config.yml`` then ``local-config.yml``; the later file wins per key."""
    config = Config()
    for name in CONFIG_FILES:
        path = Path(project_root) / CONFIG_DIR / name
        if not path.is_file():
            continue
        try:
            data = parse_simple_yaml(path.read_text(encoding="utf-8"))
            _merge(config, data)
        except ConfigError as exc:
            raise ConfigError(f"{name}: {exc}") from exc
    return config


def _merge(config: Config, data: dict[str, Any]) -> None:
    if "default_developer" in data:
        value = data["default_developer"]
        config.default_developer = None if value is None else str(value)
    approvers = data.get("approvers")
    if approvers is not None:
        if not isinstance(approvers, dict):
            raise ConfigError("approvers must be a mapping of stage to names")
        for stage, names in approvers.items():
            if stage not in CONFIG_STAGES:
                raise ConfigError(
                    f"approvers: unknown stage {stage!r} (expected one of {', '.join(CONFIG_STAGES)})"
                )
            config.approvers[stage] = _names(names, f"approvers.{stage}")
    if "abbreviation_authorisers" in data:
        config.abbreviation_authorisers = _names(data["abbreviation_authorisers"], "abbreviation_authorisers")
    if "main_branches" in data:
        branches = _names(data["main_branches"], "main_branches")
        if not branches:
            raise ConfigError("main_branches must name at least one branch")
        config.main_branches = branches
    review = data.get("review")
    if review is not None:
        if not isinstance(review, dict) or set(review) - REVIEW_KEYS:
            raise ConfigError(f"review may only hold {', '.join(sorted(REVIEW_KEYS))}")
        value = review.get("one_at_a_time_max", config.one_at_a_time_max)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ConfigError("review.one_at_a_time_max must be a whole number")
        config.one_at_a_time_max = value
        idle = review.get("page_idle_minutes", config.page_idle_minutes)
        if isinstance(idle, bool) or not isinstance(idle, int) or idle < 1:
            raise ConfigError("review.page_idle_minutes must be a whole number of minutes, at least 1")
        config.page_idle_minutes = idle
        if "diagram_script" in review:
            config.diagram_script = _diagram_script(review["diagram_script"])


REVIEW_KEYS = frozenset({"one_at_a_time_max", "page_idle_minutes", "diagram_script"})


def _diagram_script(value: Any) -> str | None:
    """``review.diagram_script``: one ``https:`` URL the review page's browser may load, or nothing (004 D-69)."""
    if value is None:
        return None
    from urllib.parse import urlsplit

    parts = urlsplit(str(value))
    if (
        not isinstance(value, str)
        or parts.scheme != "https"
        or not parts.netloc
        or any(c in value for c in " \"'<>")
    ):
        raise ConfigError("review.diagram_script must be an https: URL, or null")
    return value


# ---- who is who


def normalise_person(name: str) -> str:
    return " ".join(name.split()).casefold()


def same_person(a: str, b: str) -> bool:
    return normalise_person(a) == normalise_person(b)


def git_identity(cwd: Path) -> tuple[str | None, str | None]:
    """``(user.name, user.email)`` from git, or ``None`` for each that is unavailable."""

    while not cwd.exists() and cwd != cwd.parent:  # a feature directory may not have been created yet
        cwd = cwd.parent

    def read(key: str) -> str | None:
        try:
            proc = subprocess.run(
                ["git", "config", key], cwd=cwd, capture_output=True, text=True, check=False, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = proc.stdout.strip()
        return value if proc.returncode == 0 and value else None

    return read("user.name"), read("user.email")


def story_identities(
    config: Config, owner: str | None, git_name: str | None, git_email: str | None
) -> list[str]:
    """Every name the story's developer is known by."""
    found: list[str] = []
    for candidate in (owner, config.default_developer, git_name, git_email):
        if candidate and not any(same_person(candidate, seen) for seen in found):
            found.append(candidate)
    return found


def resolve_approvers(config: Config, stage: str, developer: list[str]) -> list[str]:
    """The people who may confirm (and override) ``stage``: the configured list, else the developer.
    A derived stage with no list of its own uses the ``technical`` list first (research D-36)."""
    configured = config.approvers.get(stage)
    if not configured and stage in DERIVED_APPROVER_STAGES:
        configured = config.approvers.get("technical")
    return list(configured) if configured else list(developer)


def confirmer_refusal(by: str, approvers: list[str], stage: str, authorising: bool = False) -> Refusal | None:
    """``None`` if ``by`` may confirm ``stage``; otherwise the refusal to raise."""
    if any(same_person(by, person) for person in approvers):
        return None
    code = "not-an-authoriser" if authorising else "not-a-confirmer"
    role = "authorise an abbreviation" if authorising else f"confirm {stage}"
    if approvers:
        fix = f"Ask one of: {', '.join(approvers)}. To change this, edit approvers in .specify/extensions/eil/eil-config.yml."
    else:
        fix = (
            "No developer could be identified. Set `git config user.name`, pass --owner when starting the story, "
            "or set default_developer in .specify/extensions/eil/eil-config.yml."
        )
    return Refusal(code, f"{by!r} is not configured to {role}", fix)


def is_ai_actor(name: str) -> bool:
    """True if ``name`` is the AI (FR-012). Attestation-level: it catches the obvious case."""
    return normalise_person(name) in _AI_NAMES

"""Command line for the ``eil`` helper (task T026; contracts/cli.md).

Global behaviour, in one place:

* ``--json`` prints exactly one JSON object on stdout and nothing else; diagnostics go to stderr.
* Exit codes: 0 ok, 1 refusal, 2 usage or input error, 3 not a governed feature, 4 internal error.
* Every subcommand except ``start`` and ``fingerprint`` exits 3, changing nothing, when the
  feature is not governed (FR-006, FR-069). Wraps read exit 3 as "run the core command unchanged".
* ``--json`` and ``--feature-dir`` are accepted before or after the subcommand.

Handlers live in ``HANDLERS`` keyed by the top-level command. A handler receives a ``Context`` and
the parsed arguments, returns the success payload, and reports a refusal by raising
``refuse(Refusal(...))``. A command whose story has not been built yet is a clear internal error.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from . import (
    aliases,
    blockstatus,
    chain,
    changelog,
    comprehension,
    corrections,
    handoff,
    overview,
    provenance,
    records,
    reviews,
    staleness,
)
from . import fingerprint as fingerprint_module
from . import target as targeting
from .artifacts import list_artifacts, register
from .clock import utc_now
from .gates import JudgmentsError, check_stage
from .identity import Config, ConfigError, is_ai_actor, load_config
from .package import STAGES, Package
from .results import (
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_REFUSAL,
    EilExit,
    Refusal,
    emit_json,
    not_governed,
    refuse,
    usage_error,
)
from .templates import load_template

UNGOVERNED_OK = frozenset({"start", "fingerprint"})

# Every subcommand is declared here as writing records or not (contracts/cli.md delta, D-46). A
# ``writes`` call whose story came from the pointer, or from nothing, is refused ``ambiguous-story``
# before anything is read for modification when that story cannot be told for certain.
READ_ONLY, WRITES = "read-only", "writes"
COMMAND_KINDS: dict[str, str] = {
    "status": READ_ONLY,
    "show": READ_ONLY,
    "trace": READ_ONLY,
    "fingerprint": READ_ONLY,
    "blocks list": READ_ONLY,
    "review list": READ_ONLY,
    "review show": READ_ONLY,
    "review start": READ_ONLY,
    "comprehension plan": READ_ONLY,
    "check": READ_ONLY,
    "enter": READ_ONLY,
    "artifact list": READ_ONLY,
    "correct propose": READ_ONLY,
    "start": WRITES,
    "sync": WRITES,
    "check --judgments": WRITES,
    "stage-init": WRITES,
    "challenge add": WRITES,
    "challenge severity": WRITES,
    "challenge answer": WRITES,
    "approve": WRITES,
    "override": WRITES,
    "amend": WRITES,
    "review accept": WRITES,
    "review finish": WRITES,
    "review confirm": WRITES,
    "review answer": WRITES,
    "correct open": WRITES,
    "blocks classify": WRITES,
    "blocks reclassify": WRITES,
    "abbreviate": WRITES,
    "resolve": WRITES,
    "artifact register": WRITES,
    "comprehension record": WRITES,
    "comprehension waive": WRITES,
    "profile set": WRITES,
    "profile withdraw": WRITES,
    "overview": WRITES,
}


def command_key(args: argparse.Namespace) -> str:
    """The ``COMMAND_KINDS`` entry a parsed call falls under."""
    if args.command == "check" and getattr(args, "judgments", None):
        return "check --judgments"
    action = getattr(args, "action", None)
    return f"{args.command} {action}" if action else args.command
ENTER_COMMANDS = handoff.ENTER_COMMANDS
# Stages whose document has a compatibility alias, created only after the document (FR-049).
ALIAS_STAGES = ("ai-spec", "plan", "tasks")
# The document that must already exist before a later stage may begin.
PREDECESSOR = {"plan": "ai-spec", "tasks": "plan", "verification": "tasks", "completion": "verification"}


@dataclass
class Context:
    cwd: Path
    env: Mapping[str, str]
    json_mode: bool
    feature_dir_arg: str | None
    target: targeting.Target | None = None
    # A read-only call whose story is ambiguous runs, but writes nothing at all (not even s00).
    quiet: bool = False

    def feature_dir(self) -> Path | None:
        if self.target is None:
            self.target = targeting.resolve_target(self.cwd, self.feature_dir_arg, self.env)
        return self.target.directory

    def package(self) -> Package:
        """The governed package, or exit 3."""
        directory = self.feature_dir()
        package = Package(directory) if directory is not None else None
        if package is None or not package.governed:
            raise not_governed()
        return package


Handler = Callable[[Context, argparse.Namespace], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


class _Parser(argparse.ArgumentParser):
    """Reports usage errors as ``EilExit`` (exit 2) instead of exiting the interpreter."""

    stream: TextIO = sys.stderr

    def error(self, message: str) -> Any:  # type: ignore[override]
        self.print_usage(self.stream)
        raise usage_error(message)


def _common() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print one JSON object"
    )
    common.add_argument("--feature-dir", default=argparse.SUPPRESS, help="the feature directory")
    return common


def build_parser(stream: TextIO) -> argparse.ArgumentParser:
    common = _common()
    parser = _Parser(prog="eil", description="Engineer-in-the-loop helper", parents=[common])
    parser.stream = stream
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.required = True

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, parents=[common])
        p.stream = stream  # type: ignore[attr-defined]
        return p

    p = add("start", "create s00 and s01 in the feature directory")
    p.add_argument("--title", required=True)
    p.add_argument("--owner")
    p.add_argument("--on-branch", help="confirm the story is written on this (unexpected) branch")
    p.add_argument("--by", help="the person confirming the branch")
    p.add_argument("--reply", help="their reply, verbatim")

    p = add("sync", "classify and refresh aliases, regenerate the overview")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--strict", action="store_true")

    p = add("enter", "the single gate call used by wraps")
    p.add_argument("target", choices=ENTER_COMMANDS)
    p.add_argument("--task", help="the task about to be implemented (implement only)")

    p = add("check", "evaluate a stage's gate")
    p.add_argument("--stage")
    p.add_argument("--chain", action="store_true")
    p.add_argument("--judgments", metavar="PATH")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--full", action="store_true", help="list every criterion, including the met structural ones")

    p = add("stage-init", "create a stage's document from its template")
    p.add_argument("stage")

    p = add("challenge", "raise or answer a challenge")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("add", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("stage")
    a.add_argument("--target", required=True)
    a.add_argument("--text", required=True)
    a.add_argument("--by")
    a.add_argument("--severity", choices=("high", "medium", "low"))
    a = actions.add_parser("severity", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("id")
    a.add_argument("--to", required=True, choices=("high", "medium", "low"))
    a.add_argument("--by", required=True)
    a = actions.add_parser("answer", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("id")
    a.add_argument("--response", required=True, choices=("accepted", "rejected", "deferred"))
    a.add_argument("--by", required=True)
    a.add_argument("--reason")

    p = add("approve", "record a stage approval")
    p.add_argument("stage")
    p.add_argument("--by", required=True)
    p.add_argument("--attestation", required=True)
    p.add_argument("--played-back-to")

    p = add("override", "record an override for one criterion")
    p.add_argument("stage")
    p.add_argument("--criterion", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--reason", required=True)

    p = add("amend", "re-sign an approval covered entirely by cited human decisions")
    p.add_argument("stage")
    p.add_argument("--from", dest="from_ids", required=True, metavar="IDS")
    p.add_argument("--by", required=True)
    p.add_argument("--attestation", required=True)

    p = add("review", "walk a stage's changes since its last approval one at a time, and re-sign it")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("start", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a = actions.add_parser("accept", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--items", default="")
    a.add_argument("--sections", default="")
    a.add_argument("--by", required=True)
    a.add_argument("--note")
    a = actions.add_parser("finish", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--by", required=True)
    a.add_argument("--attestation", required=True)
    a = actions.add_parser("confirm", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--by", required=True)
    a.add_argument("--confirmation", required=True)
    a.add_argument("--summaries", metavar="FILE")
    a = actions.add_parser("list", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--kind", required=True, choices=REVIEW_KINDS)
    a.add_argument("--views", metavar="FILE")
    a = actions.add_parser("show", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--kind", required=True, choices=REVIEW_KINDS)
    which = a.add_mutually_exclusive_group(required=True)
    which.add_argument("--entry", metavar="KEY")
    which.add_argument("--group", metavar="SECTION")
    which.add_argument("--all", dest="all_", action="store_true")
    a = actions.add_parser("answer", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--kind", required=True, choices=REVIEW_KINDS)
    a.add_argument("--digest")
    a.add_argument("--by", required=True)
    a.add_argument("--reply", required=True)
    mode = a.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", dest="all_", action="store_true")
    mode.add_argument("--all-except", metavar="IDS")
    mode.add_argument("--question", metavar="IDS")
    mode.add_argument("--reopen", metavar="IDS")
    mode.add_argument("--entry", metavar="KEY", help="answer one entry; stored until the list is complete")
    mode.add_argument("--rest", action="store_true", help='"ok to the rest": accept every remaining entry')
    a.add_argument("--disposition", choices=("accept", "except", "question"), default="accept")
    a.add_argument("--defer-reason")
    a.add_argument("--summaries", metavar="FILE")

    p = add("correct", "propose or open a backwards correction")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    for name in ("propose", "open"):
        a = actions.add_parser(name, parents=[common])
        a.stream = stream  # type: ignore[attr-defined]
        a.add_argument("--item", required=True)
        a.add_argument("--found-in", required=True)
        a.add_argument("--problem", required=True)
        if name == "open":
            a.add_argument("--by", required=True)
            a.add_argument("--owner")
            a.add_argument("--wording")

    p = add("blocks", "list the content blocks of a stage with their derived status")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("list", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--status", choices=("settled", "needs-review", "source-changed", "stale", "unknown-currency"))
    a = actions.add_parser("classify", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--file", required=True)
    a = actions.add_parser("reclassify", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--block", required=True)
    a.add_argument("--to", required=True, choices=("inferred",))
    a.add_argument("--by", required=True)
    a.add_argument("--reason")

    p = add("abbreviate", "mark a stage abbreviated")
    p.add_argument("stage")
    p.add_argument("--by", required=True)
    p.add_argument("--reason", required=True)

    p = add("resolve", "carry a pending clarification upstream")
    p.add_argument("--id", required=True)
    p.add_argument("--stage", required=True)

    p = add("artifact", "register or list artifacts")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("register", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--id", required=True)
    a.add_argument("--file", required=True)
    a.add_argument("--kind", required=True, choices=("wireframe", "image"))
    a.add_argument("--depicts")
    a.add_argument("--source-tool", required=True)
    a.add_argument("--source-url", required=True)
    a.add_argument("--exported-on")
    a.add_argument("--exported-by")
    a = actions.add_parser("list", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage")

    p = add("comprehension", "plan or record the comprehension check")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("plan", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--level")
    a.add_argument("--attempt", type=int, default=1)
    a.add_argument("--by", help="the person taking the check: their own decisions are not asked")
    a = actions.add_parser("record", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--level", required=True)
    a.add_argument(
        "--outcome",
        required=True,
        choices=("understood", "coached", "revealed", "skipped", "not-applicable", "own-decision"),
    )
    a.add_argument("--by", required=True)
    a.add_argument("--attempts", type=int, default=1)
    a.add_argument("--items", default="")
    a.add_argument("--reason")
    a = actions.add_parser("waive", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--by", required=True)
    a.add_argument("--reason", required=True)

    p = add("profile", "authorise or withdraw the small-story profile")
    actions = p.add_subparsers(dest="action", metavar="ACTION", parser_class=_Parser)
    actions.required = True
    a = actions.add_parser("set", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("name", choices=("small",))
    a.add_argument("--by", required=True)
    a.add_argument("--reason", required=True)
    a = actions.add_parser("withdraw", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--by", required=True)
    a.add_argument("--reason", required=True)

    p = add("trace", "forward and reverse chains, and gaps")
    p.add_argument("--from", dest="from_id")
    p.add_argument("--to", dest="to_id")
    p.add_argument("--report", action="store_true")

    p = add("show", "print a stage as a person reads it: no records, review cues shown")
    p.add_argument("stage")
    p.add_argument("--items", metavar="IDS", help="only these items, under their section headings")
    p.add_argument("--section", metavar="NAME", help="only this section")

    add("status", "derived state, approvals and the next action")
    add("overview", "regenerate s00-README.md")

    p = add("fingerprint", "print a file's content fingerprint")
    p.add_argument("file")

    return parser


# ---- handlers that need no story


def _fingerprint(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    path = ctx.cwd / args.file
    try:
        value = fingerprint_module.fingerprint_file(path)
    except OSError as exc:
        raise usage_error(f"cannot read {args.file}: {exc.strerror or exc}") from exc
    except fingerprint_module.NotUtf8 as exc:
        raise usage_error(f"not-utf8: {args.file} is not valid UTF-8") from exc
    return {"ok": True, "fingerprint": value, "text": value}


HANDLERS["fingerprint"] = _fingerprint


# ---- story commands

TEMPLATE_NAMES = {
    "requirements": "s01-requirements-template",
    "functional": "s02-functional-spec-template",
    "technical": "s03-technical-spec-template",
    "ai-spec": "spec-template",
    "plan": "plan-template",
    "tasks": "tasks-template",
    "verification": "s07-verification-template",
    "completion": "s08-completion-template",
}


def _config(ctx: Context, package: Package | None = None) -> Config:
    root = (package.project_root if package else None) or ctx.cwd
    try:
        return load_config(root)
    except ConfigError as exc:
        raise usage_error(str(exc)) from exc


def _title_of(package: Package) -> str:
    return overview.read_story(package)[0] or "Untitled story"


def _start(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    directory = ctx.feature_dir()
    if directory is None:
        raise usage_error(
            "no feature directory: pass --feature-dir, set SPECIFY_FEATURE_DIRECTORY, or create .specify/feature.json"
        )
    package = Package(directory)
    if package.governed:
        raise refuse(
            Refusal(
                "already-governed",
                f"{directory} is already a governed story",
                f"Continue it with the command for its current stage ({package.current_stage()})",
            )
        )
    if (directory / "spec.md").exists():
        raise refuse(
            Refusal(
                "directory-has-spec-md",
                f"{directory} holds an ordinary spec.md that this workflow did not create",
                "Choose a new feature directory; existing features are never taken over (FR-006)",
            )
        )
    config = _config(ctx, package)
    from .records import developer_identities

    owner = args.owner or next(iter(developer_identities(package, config)), None) or "unassigned"
    project = package.project_root or ctx.cwd
    start = _branch_guard(ctx, args, directory, project, config)
    overview_template = load_template(project, "s00-readme-template")
    requirements_template = load_template(project, TEMPLATE_NAMES["requirements"])
    directory.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    if not package.exists("requirements"):
        package.doc_path("requirements").write_bytes(
            requirements_template.replace("{{title}}", args.title).encode("utf-8")
        )
        created.append(package.doc_path("requirements").name)
    pointer = _persist_feature_json(package, project)
    start["previous_pointer"] = pointer["previous"]
    package.write_story_record("start", {k: v for k, v in start.items() if v is not None})
    overview.write(package, overview_template, args.title, owner)
    created.insert(0, package.overview_path.name)
    text = f"Started {directory.name}: created {', '.join(created)}."
    if pointer["current"] and pointer["previous"] != pointer["current"]:
        text += f" The active story was {pointer['previous'] or 'none'} and is now {pointer['current']}."
    if start.get("branch_confirmed_by"):
        text += f" Written on branch {start['branch']}, confirmed by {start['branch_confirmed_by']}."
    payload: dict[str, Any] = {
        "ok": True,
        "feature_dir": str(directory),
        "created": created,
        "pointer": pointer,
        "branch": start.get("branch"),
        "text": text,
    }
    if start.get("note"):
        payload["note"] = start["note"]
        payload["text"] += f" Note: {start['note']}."
    return payload


def _branch_guard(
    ctx: Context, args: argparse.Namespace, directory: Path, project: Path, config: Config
) -> dict[str, Any]:
    """D-47: refuse a start on a branch that is neither a main branch nor named for the new story,
    unless a person confirmed it (``--on-branch``, ``--by``, ``--reply``). Returns ``story.start``."""
    branch = targeting.current_branch(project)
    start: dict[str, Any] = {"at": utc_now(), "branch": branch}
    if branch is None:
        start["note"] = "no git branch is checked out (no repository, or a detached HEAD), so none was compared"
        return start
    if targeting.branch_expected(branch, directory.name, config.main_branches):
        return start
    question = targeting.branch_question(directory.name, branch)
    by, reply = (args.by or "").strip(), (args.reply or "").strip()
    if args.on_branch != branch:
        raise refuse(
            Refusal(
                "unexpected-branch",
                f"the current git branch is {branch}, which is neither a main branch "
                f"({', '.join(config.main_branches)}) nor named for {directory.name}",
                f"Switch to a branch for {directory.name}, or ask the developer to confirm and run eil start again "
                f"with --on-branch {branch} --by NAME --reply WORDS. The helper never creates or switches branches.",
                question=question,
            )
        )
    refusals = []
    if not by or is_ai_actor(by):
        refusals.append(
            Refusal("ai-approval", "a person confirms the branch, never the AI", "Ask the developer", question=question)
        )
    if not reply:
        refusals.append(
            Refusal("reply-required", "the confirmation needs the person's reply", "Pass their words with --reply", question=question)
        )
    if refusals:
        raise refuse(*refusals)
    start.update(branch_confirmed_by=by, reply=reply, question=question)
    return start


def _persist_feature_json(package: Package, project: Path) -> dict[str, str | None]:
    """Point ``.specify/feature.json`` at the new story, always (FR-001); returns the move."""
    saved = project / ".specify" / "feature.json"
    previous = targeting.read_pointer(project)
    if not (project / ".specify").is_dir():
        return {"previous": previous, "current": None}
    try:
        relative = os.path.relpath(package.root.resolve(), project.resolve())
    except ValueError:
        relative = str(package.root.resolve())
    if relative.startswith(".."):
        relative = str(package.root.resolve())
    relative = relative.replace(os.sep, "/")
    import json

    saved.write_text(json.dumps({"feature_directory": relative}) + "\n", encoding="utf-8")
    return {"previous": previous, "current": relative}


def _known_stage(package: Package, name: str) -> str:
    if name not in STAGES:
        raise refuse(Refusal("unknown-stage", f"{name!r} is not a stage", f"Use one of: {', '.join(STAGES)}"))
    return name


def _stage_init(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    stage = _known_stage(package, args.stage)
    if package.exists(stage):
        raise refuse(
            Refusal(
                "already-exists",
                f"{package.doc_path(stage).name} already exists",
                "Continue the stage instead",
            )
        )
    prior = records.prior_stage_refusals(package, stage)
    before = PREDECESSOR.get(stage)
    if before is not None and not package.exists(before):
        prior.append(handoff.missing_refusal(before, f"Complete {before} first"))
    if prior:
        raise refuse(*prior)
    template = load_template(package.project_root or ctx.cwd, TEMPLATE_NAMES[stage])
    package.doc_path(stage).write_bytes(template.replace("{{title}}", _title_of(package)).encode("utf-8"))
    if stage in ALIAS_STAGES:
        aliases.refresh(package, aliases.alias_mode(ctx.env))
    _regenerate_overview(ctx, package)
    return {
        "ok": True,
        "stage": stage,
        "created": package.doc_path(stage).name,
        "text": f"Created {package.doc_path(stage).name}.",
    }


def _check(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.chain and not args.stage:
        result = chain.check(package)
        if args.strict and not result["ok"]:
            raise refuse(
                Refusal("unmet-criteria", f"{len(result['gaps'])} gap(s) in the chain", "See the gaps")
            )
        return result
    stage = _known_stage(package, args.stage or package.current_stage() or "completion")
    if not package.exists(stage):
        raise refuse(
            Refusal("unknown-stage", f"{stage} has no document yet", f"Start it with: eil stage-init {stage}")
        )
    if args.chain:
        raise usage_error("--chain checks the whole story: give it without --stage")
    judgments = ctx.cwd / args.judgments if args.judgments else None
    try:
        result = check_stage(package, stage, judgments_path=judgments, write=not ctx.quiet)
    except JudgmentsError as exc:
        raise usage_error(str(exc)) from exc
    except NotImplementedError as exc:
        raise EilExit(EXIT_INTERNAL, {"ok": False, "error": str(exc)}, str(exc)) from exc
    _regenerate_overview(ctx, package)
    payload = result.to_json()
    payload["text"] = _render_check(result, args.full)
    if args.strict and not result.ok:
        raise refuse(
            Refusal(
                "unmet-criteria",
                f"{len(result.unmet())} criteria of {stage} are not met",
                "See the criteria in the assessment",
            )
        )
    return payload


def _render_check(result: Any, full: bool = False) -> str:
    lines = [f"Gate for {result.stage}: {'met' if result.ok else 'not met'}"]
    collapsed = 0
    for c in result.ordered_criteria():
        if not full and c.status == "met" and c.kind != "judgment":
            collapsed += 1
            continue
        lines.append(f"  {c.id} [{c.kind}] {c.status}" + (f": {c.reason}" if c.reason else ""))
    if collapsed:
        lines.append(f"  {collapsed} structural criteria met (--full lists them)")
    for f in result.findings:
        lines.append(f"  finding {f.code} at {f.where}: {f.message}")
    return "\n".join(lines)


def _approve(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = records.approve(
        package, _config(ctx, package), args.stage, args.by, args.attestation, args.played_back_to
    )
    _regenerate_overview(ctx, package)
    return result


def _override(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = records.override(
        package, _config(ctx, package), args.stage, args.criterion, args.by, args.reason
    )
    _regenerate_overview(ctx, package)
    return result


def _amend(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    from .provenance import amend

    package = ctx.package()
    from_ids = [i.strip() for i in args.from_ids.split(",") if i.strip()]
    result = amend(package, _config(ctx, package), args.stage, from_ids, args.by, args.attestation)
    _regenerate_overview(ctx, package)
    return result


REVIEW_KINDS = (
    "inferred", "changes", "tasks", "evidence", "low-challenges", "unknown-currency", "diagram-currency",
    "unsettled-challenges",
)  # fmt: skip


def _read_keyed(path: str, stage: str, what: str, rows: str, value: str, kind: str | None = None) -> dict[str, str]:
    """A ``--views`` or ``--summaries`` file: ``{"stage", rows: [{"key", value}]}`` as ``{key: value}``."""
    import json

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise usage_error(f"cannot read {what} file {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("stage") != stage or (kind and data.get("kind", kind) != kind):
        raise usage_error(f"{what} file {path} is not for stage {stage}" + (f" kind {kind}" if kind else ""))
    found = data.get(rows)
    if not isinstance(found, list) or not all(isinstance(r, dict) and "key" in r and value in r for r in found):
        raise usage_error(f'{what} file {path} needs "{rows}": [{{"key", "{value}"}}]')
    return {str(r["key"]): str(r[value]) for r in found}


def _ids(text: str | None) -> list[str] | None:
    return None if text is None else [i.strip() for i in text.split(",") if i.strip()]


def _review_list(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    views = _read_keyed(args.views, args.stage, "views", "views", "view", args.kind) if args.views else None
    listed = reviews.build_list(package, args.stage, args.kind, views, threshold=_config(ctx, package).one_at_a_time_max)
    lines = [f"{listed.kind} list for {listed.stage} ({len(listed.entries)} entries, {listed.purpose}, {listed.mode})"]
    if listed.session:
        lines.append(f"  {listed.session['answered']} answered already; these remain:")
    for group in listed.groups():
        if group["section"]:
            lines.append(f"  {group['section']}:")
        for entry in (e for e in listed.entries if e.key in group["entries"]):
            lines.append(f"    {entry.key}: {entry.summary} ({entry.why})")
    lines += [f"  limit: {limit}" for limit in listed.limits]
    return {"ok": True, **listed.to_json(), "text": "\n".join(lines)}


def _review_answer(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    _persist_adoption(package)
    package = ctx.package()
    summaries = (
        _read_keyed(args.summaries, args.stage, "summaries", "summaries", "summary") if args.summaries else None
    )
    result = reviews.answer(
        package,
        _config(ctx, package),
        args.stage,
        args.kind,
        digest=args.digest,
        by=args.by,
        reply=args.reply,
        all_=args.all_,
        all_except=_ids(args.all_except),
        question=_ids(args.question),
        reopen=_ids(args.reopen),
        defer_reason=args.defer_reason,
        summaries=summaries,
        entry=args.entry,
        disposition=args.disposition,
        rest=args.rest,
    )
    _regenerate_overview(ctx, package)
    return result


def _blocks(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action in ("classify", "reclassify"):
        _persist_adoption(package)
        package = ctx.package()
        if args.action == "reclassify":
            return provenance.reclassify(package, args.stage, args.block, args.by, args.reason)
        import json

        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise usage_error(f"cannot read classification file {args.file}: {exc}") from exc
        result = provenance.classify(package, args.stage, data)
        _regenerate_overview(ctx, ctx.package())
        return result
    stale = blockstatus.stale_sources(package, args.stage)
    rows = []
    for info in blockstatus.block_statuses(package).get(args.stage, {}).values():
        if args.status and not (
            info.status == args.status or (args.status == "stale" and (info.stale or info.status == "source-changed"))
        ):
            continue
        row = {"key": info.key, "class": info.klass, "status": info.status}
        if args.stage in blockstatus.DERIVED or info.key in stale:
            row["stale_sources"] = stale.get(info.key, [])
        rows.append(row)
    lines = [f"{args.stage}: {len(rows)} block(s)"] + [f"  {r['key']}: {r['status']}" for r in rows]
    return {"ok": True, "stage": args.stage, "blocks": rows, "text": "\n".join(lines)}


def _review(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    from . import provenance

    if args.action == "list":
        return _review_list(ctx, args)
    if args.action == "answer":
        return _review_answer(ctx, args)
    if args.action == "show":
        package = ctx.package()
        return reviews.show_entries(
            package, args.stage, args.kind, entry=args.entry, group=args.group, all_=args.all_,
            threshold=_config(ctx, package).one_at_a_time_max,
        )  # fmt: skip
    package = ctx.package()
    if args.action == "confirm":
        _persist_adoption(package)
        package = ctx.package()
        summaries = (
            _read_keyed(args.summaries, args.stage, "summaries", "summaries", "summary") if args.summaries else None
        )
        result = reviews.confirm(
            package, _config(ctx, package), args.stage, by=args.by, confirmation=args.confirmation, summaries=summaries
        )
        _regenerate_overview(ctx, package)
        return result
    if args.action == "start":
        return provenance.start(package, args.stage)
    if args.action == "accept":
        items = [i.strip() for i in args.items.split(",") if i.strip()]
        sections = [s.strip() for s in args.sections.split(",") if s.strip()]
        result = provenance.accept(
            package, _config(ctx, package), args.stage, items, sections, args.by, args.note
        )
        _regenerate_overview(ctx, package)
        return result
    result = provenance.finish(package, _config(ctx, package), args.stage, args.by, args.attestation)
    _regenerate_overview(ctx, package)
    return result


def _correct(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action == "propose":
        return corrections.propose(package, args.item, args.found_in, args.problem)
    _persist_adoption(package)
    package = ctx.package()
    result = corrections.open_correction(
        package, args.item, args.found_in, args.problem, args.by, args.owner, args.wording
    )
    _regenerate_overview(ctx, package)
    return result


def _regenerate_overview(ctx: Context, package: Package) -> bool:
    if ctx.quiet:
        return False
    return overview.write(package, load_template(package.project_root or ctx.cwd, "s00-readme-template"))


def _migrate(package: Package) -> list[str]:
    """D-48, D-50: move every JSON region body into ``eil-record.json`` and strip the old ``[ai-draft]``
    tags. Both are fingerprint-neutral, so no approval moves. Returns the stages that changed."""
    from .blocks import RegionError, strip_ai_draft

    changed = []
    for stage in package.existing_stages():
        fresh = Package(package.root)
        text = fresh.read(stage)
        stripped = strip_ai_draft(text)
        if stripped != text:
            fresh.doc_path(stage).write_bytes(stripped.encode("utf-8"))
            changed.append(stage)
        try:
            if Package(package.root).migrate(stage) and stage not in changed:
                changed.append(stage)
        except RegionError:
            continue  # a malformed region or record file is reported by status; it is never written over
    return changed


def _persist_adoption(package: Package) -> None:
    """D-42: the first writing command records the provenance an upgrade adopts, once per document."""
    for stage in package.existing_stages():
        record = blockstatus.adopt(package, stage)
        if record is not None:
            package.write_record(stage, "provenance", record)


def _sync(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    snapshots: dict[str, Any] = {"snapshotted": [], "completed_while_blocked": [], "cleared": []}
    migrated: list[str] = []
    if not args.check_only:
        migrated = _migrate(package)
        _persist_adoption(ctx.package())
        changelog.refresh_all(ctx.package())
        snapshots = staleness.sync_task_snapshots(ctx.package())
    before, after = aliases.refresh(package, aliases.alias_mode(ctx.env), check_only=args.check_only)
    changed = False if args.check_only else _regenerate_overview(ctx, package)
    faults = [s for s in before if s.fault]
    if args.strict and faults:
        raise refuse(
            Refusal(
                "alias-fault-strict",
                "alias fault(s): " + ", ".join(f"{s.name} ({s.fault})" for s in faults),
                "Run eil sync without --strict to repair them",
            )
        )
    lines = ["Synchronised."] + [f"  alias fault {s.name}: {s.fault}" for s in faults]
    if migrated:
        lines.append(f"  records moved to eil-record.json or tags removed: {', '.join(migrated)}")
    lines += [f"  completed-while-blocked {t}" for t in snapshots["completed_while_blocked"]]
    return {
        "ok": True,
        "task_snapshots": snapshots["snapshotted"],
        "findings": [
            {"code": "completed-while-blocked", "where": t, "message": f"{t} was ticked while it was blocked"}
            for t in snapshots["completed_while_blocked"]
        ],
        "alias_faults": [s.to_json() for s in faults],
        "aliases": [s.to_json() for s in after],
        "overview_changed": changed,
        "migrated": migrated,
        "text": "\n".join(lines),
    }


def _enter(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = handoff.enter(package, args.target, aliases.alias_mode(ctx.env), task=args.task)
    _regenerate_overview(ctx, package)
    return result


def _resolve(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = handoff.resolve(package, args.id, args.stage)
    _regenerate_overview(ctx, package)
    return result


def _overview(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    changed = _regenerate_overview(ctx, package)
    return {
        "ok": True,
        "overview_changed": changed,
        "text": "Overview regenerated." if changed else "Overview is current.",
    }


def _artifact(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action == "list":
        rows = list_artifacts(package, args.stage)
        lines = [
            f"{r['id']:<8} {r['kind']:<13} {r['stage']:<13} {r['form']:<7} {r['state']}  {r['title']}"
            for r in rows
        ]
        return {"ok": True, "artifacts": rows, "text": "\n".join(lines) or "No artifacts."}
    config = _config(ctx, package)
    default_by = next(iter(records.developer_identities(package, config)), None)
    result = register(
        package,
        args.id,
        args.file,
        args.kind,
        args.source_tool,
        args.source_url,
        depicts=args.depicts,
        exported_on=args.exported_on,
        exported_by=args.exported_by,
        cwd=ctx.cwd,
        default_by=default_by,
    )
    _regenerate_overview(ctx, package)
    return result


def _comprehension(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action == "plan":
        result = comprehension.plan(package, args.stage, args.level, args.attempt, by=args.by)
        lines = [
            f"{r['level']:<10} {r.get('target', r['status'])}  {r.get('section', '') or ', '.join(r.get('items', []))}"
            for r in result["levels"]
        ]
        result["text"] = "\n".join(lines)
        return result
    if args.action == "waive":
        result = comprehension.waive(package, _config(ctx, package), args.stage, args.by, args.reason)
        _regenerate_overview(ctx, package)
        return result
    items = [i.strip() for i in args.items.split(",") if i.strip()]
    result = comprehension.record(
        package,
        _config(ctx, package),
        args.stage,
        args.level,
        args.outcome,
        args.by,
        attempts=args.attempts,
        items=items,
        reason=args.reason,
    )
    _regenerate_overview(ctx, package)
    return result


def _profile(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    from . import profile

    package = ctx.package()
    if args.action == "set":
        result = profile.set_profile(package, _config(ctx, package), args.name, args.by, args.reason)
    else:
        result = profile.withdraw(package, _config(ctx, package), args.by, args.reason)
    _regenerate_overview(ctx, package)
    return result


def _abbreviate(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = records.abbreviate(package, _config(ctx, package), args.stage, args.by, args.reason)
    _regenerate_overview(ctx, package)
    return result


def _challenge(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action == "add":
        result = records.add_challenge(package, args.stage, args.target, args.text, args.by, args.severity)
    elif args.action == "severity":
        result = records.set_challenge_severity(package, _config(ctx, package), args.id, args.to, args.by)
    else:
        result = records.answer_challenge(
            package, _config(ctx, package), args.id, args.response, args.by, args.reason
        )
    _regenerate_overview(ctx, package)
    return result


def _trace(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.from_id and args.to_id:
        raise usage_error("give --from or --to, not both")
    if not (args.from_id or args.to_id):
        result = chain.report(package)
        result["text"] = _render_report(result)
        return result
    try:
        return chain.trace(package, from_id=args.from_id, to_ref=args.to_id)
    except chain.UnknownReference as exc:
        raise usage_error(str(exc)) from exc


def _render_report(result: dict[str, Any]) -> str:
    lines = []
    for row in result["requirements"]:
        end = "complete" if row["complete"] else f"ends at {row['ends_at']}"
        lines.append(f"{row['id']}: {end}")
        for key in ("functional", "decisions", "ai_spec", "tasks", "code", "evidence"):
            lines.append(f"  {key:<10} {', '.join(row[key]) or '-'}")
    from .recordfile import REACHED_TEXT

    lines += [
        f"Approved {a['stage']} by {a['by']} on {str(a['at'])[:10]} ({REACHED_TEXT.get(a['reached'], a['reached'])})"
        for a in result.get("approvals", [])
    ]
    lines += [
        f"Override {o['id']}: {o['criterion']} in {o['stage']} by {o['by']}" for o in result["overrides"]
    ]
    lines += [f"Abbreviated: {a['stage']} (authorised by {a['by']})" for a in result["abbreviated"]]
    if result.get("profile"):
        found = result["profile"]
        state = " (withdrawn)" if found.get("withdrawn") else ""
        lines.append(f"Small-story profile{state}: authorised by {found.get('by')}: {found.get('reason')}")
    lines += [f"Accepted risk {r['id']} ({r['by']}, {r['stage']})" for r in result["accepted_risks"]]
    return "\n".join(lines) or "No requirements."


def _show(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    from .show import view

    items = _ids(args.items)
    return view(ctx.package(), args.stage, items=items or None, section=args.section)


def _status(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    try:
        template: str | None = load_template(package.project_root or ctx.cwd, "s00-readme-template")
    except EilExit:
        template = None  # no preset templates here: skip the overview comparison
    report = overview.status(package, template)
    report["text"] = _render_status(report)
    return report


def _render_status(report: dict[str, Any]) -> str:
    lines = [
        f"{report['title'] or 'Untitled story'} (owner: {report['owner'] or 'unassigned'})",
        f"Current stage: {report['current_stage'] or 'complete'}",
    ]
    for stage, entry in report["stages"].items():
        note = f" ({entry['reason']})" if entry.get("reason") else ""
        lines.append(f"  {stage:<13} {entry['state']}{note}")
    outstanding = report["outstanding"]
    for label, key in (
        ("Open questions", "open_questions"),
        ("Open challenges", "open_challenges"),
        ("Pending clarifications", "pending_clarifications"),
        ("Overrides", "overrides"),
    ):
        if outstanding[key]:
            lines.append(f"{label}: {', '.join(outstanding[key])}")
    for issue in report.get("issues", []):
        lines.append(f"Issue {issue['code']} at {issue['where']}: {issue['message']}")
    if report["overview"].get("current") is False:
        lines.append(report["overview"]["message"])
    lines.append(f"Next: {report['next']}")
    return "\n".join(lines)


HANDLERS.update(
    {
        "abbreviate": _abbreviate,
        "profile": _profile,
        "challenge": _challenge,
        "trace": _trace,
        "status": _status,
        "show": _show,
        "artifact": _artifact,
        "comprehension": _comprehension,
        "start": _start,
        "stage-init": _stage_init,
        "check": _check,
        "approve": _approve,
        "override": _override,
        "amend": _amend,
        "review": _review,
        "correct": _correct,
        "blocks": _blocks,
        "sync": _sync,
        "enter": _enter,
        "resolve": _resolve,
        "overview": _overview,
    }
)


# ---- output


def _guard_target(ctx: Context, args: argparse.Namespace) -> None:
    """D-46: refuse a write whose story cannot be told for certain, before anything is touched; let a
    read-only call through, but quietly (it writes nothing at all)."""
    assert ctx.target is not None
    reason = targeting.ambiguity(ctx.target, ctx.cwd)
    if reason is None:
        return
    if COMMAND_KINDS.get(command_key(args), WRITES) == READ_ONLY:
        ctx.quiet = True
        return
    names = ", ".join(s.name for s in ctx.target.candidates) or "none"
    raise refuse(
        Refusal(
            "ambiguous-story",
            f"cannot tell which story this is for: {reason}. Nothing was written.",
            f"Name the story with --feature-dir <dir> (stories: {names}), or start a new one with eil start",
        )
    )


def render_text(payload: Mapping[str, Any]) -> str:
    if isinstance(payload.get("text"), str):
        return payload["text"]
    import json

    lines = []
    for key, value in payload.items():
        rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def _report_exit(exit_: EilExit, json_mode: bool, stdout: TextIO, stderr: TextIO) -> int:
    if json_mode:
        emit_json(exit_.payload, stdout)
    if exit_.code == EXIT_REFUSAL:
        if not json_mode:
            for refusal in exit_.payload.get("refusals", []):
                stderr.write(f"refused ({refusal['code']}): {refusal['message']}\n")
                if refusal.get("fix"):
                    stderr.write(f"  fix: {refusal['fix']}\n")
    elif exit_.message and (not json_mode or exit_.code != EXIT_OK):
        stderr.write(f"{exit_.message}\n")
    return exit_.code


def main(
    argv: list[str] | None = None,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    environment = os.environ if env is None else env
    json_mode = "--json" in argv
    try:
        try:
            args = build_parser(stderr).parse_args(argv)
        except SystemExit as exc:  # --help
            return int(exc.code or 0)
        ctx = Context(
            cwd=Path(cwd) if cwd is not None else Path.cwd(),
            env=environment,
            json_mode=json_mode,
            feature_dir_arg=getattr(args, "feature_dir", None),
        )
        ctx.feature_dir()
        story = ctx.target.name if ctx.target is not None else None
        try:
            _guard_target(ctx, args)
            if args.command not in UNGOVERNED_OK:
                ctx.package()
        except EilExit as exc:
            exc.payload.setdefault("story", story)
            raise
        handler = HANDLERS.get(args.command)
        if handler is None:
            raise EilExit(
                EXIT_INTERNAL,
                {"ok": False, "error": f"not implemented: {args.command}"},
                f"not implemented: {args.command}",
            )
        try:
            payload = handler(ctx, args)
        except EilExit as exc:
            exc.payload.setdefault("story", story)
            raise
        payload = {**payload, "story": story}
        if json_mode:
            emit_json(payload, stdout)
        else:
            text = render_text({k: v for k, v in payload.items() if k != "story"})
            if text:
                stdout.write((f"Story {story}: {text}" if story else text) + "\n")
        return EXIT_OK
    except EilExit as exc:
        return _report_exit(exc, json_mode, stdout, stderr)
    except Exception as exc:  # noqa: BLE001 - the contract is exit 4, never a traceback
        message = f"{type(exc).__name__}: {exc}"
        if json_mode:
            emit_json({"ok": False, "error": message}, stdout)
        stderr.write(f"internal error: {message}\n")
        if environment.get("EIL_DEBUG"):
            import traceback

            traceback.print_exc(file=stderr)
        return EXIT_INTERNAL

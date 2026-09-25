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

from . import aliases, chain, comprehension, handoff, overview, records
from . import fingerprint as fingerprint_module
from .artifacts import list_artifacts, register
from .gates import JudgmentsError, check_stage
from .identity import Config, ConfigError, load_config
from .package import STAGES, Package, resolve_feature_dir
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

    def feature_dir(self) -> Path | None:
        return resolve_feature_dir(self.cwd, self.feature_dir_arg, self.env)

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

    p = add("sync", "classify and refresh aliases, regenerate the overview")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--strict", action="store_true")

    p = add("enter", "the single gate call used by wraps")
    p.add_argument("target", choices=ENTER_COMMANDS)

    p = add("check", "evaluate a stage's gate")
    p.add_argument("--stage")
    p.add_argument("--chain", action="store_true")
    p.add_argument("--judgments", metavar="PATH")
    p.add_argument("--strict", action="store_true")

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
    a = actions.add_parser("record", parents=[common])
    a.stream = stream  # type: ignore[attr-defined]
    a.add_argument("--stage", required=True)
    a.add_argument("--level", required=True)
    a.add_argument(
        "--outcome",
        required=True,
        choices=("understood", "coached", "revealed", "skipped", "not-applicable"),
    )
    a.add_argument("--by", required=True)
    a.add_argument("--attempts", type=int, default=1)
    a.add_argument("--items", default="")
    a.add_argument("--reason")

    p = add("trace", "forward and reverse chains, and gaps")
    p.add_argument("--from", dest="from_id")
    p.add_argument("--to", dest="to_id")
    p.add_argument("--report", action="store_true")

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
    overview_template = load_template(project, "s00-readme-template")
    requirements_template = load_template(project, TEMPLATE_NAMES["requirements"])
    directory.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    if not package.exists("requirements"):
        package.doc_path("requirements").write_bytes(
            requirements_template.replace("{{title}}", args.title).encode("utf-8")
        )
        created.append(package.doc_path("requirements").name)
    overview.write(package, overview_template, args.title, owner)
    created.insert(0, package.overview_path.name)
    _persist_feature_json(package, project)
    return {
        "ok": True,
        "feature_dir": str(directory),
        "created": created,
        "text": f"Started {directory.name}: created {', '.join(created)}.",
    }


def _persist_feature_json(package: Package, project: Path) -> None:
    saved = project / ".specify" / "feature.json"
    if not (project / ".specify").is_dir() or saved.exists():
        return
    try:
        relative = os.path.relpath(package.root.resolve(), project.resolve())
    except ValueError:
        relative = str(package.root.resolve())
    if relative.startswith(".."):
        relative = str(package.root.resolve())
    import json

    saved.write_text(json.dumps({"feature_directory": relative}) + "\n", encoding="utf-8")


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
        result = check_stage(package, stage, judgments_path=judgments)
    except JudgmentsError as exc:
        raise usage_error(str(exc)) from exc
    except NotImplementedError as exc:
        raise EilExit(EXIT_INTERNAL, {"ok": False, "error": str(exc)}, str(exc)) from exc
    _regenerate_overview(ctx, package)
    payload = result.to_json()
    payload["text"] = _render_check(result)
    if args.strict and not result.ok:
        raise refuse(
            Refusal(
                "unmet-criteria",
                f"{len(result.unmet())} criteria of {stage} are not met",
                "See the criteria in the assessment",
            )
        )
    return payload


def _render_check(result: Any) -> str:
    lines = [f"Gate for {result.stage}: {'met' if result.ok else 'not met'}"]
    for c in result.criteria:
        lines.append(f"  {c.id} [{c.kind}] {c.status}" + (f": {c.reason}" if c.reason else ""))
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


def _regenerate_overview(ctx: Context, package: Package) -> bool:
    return overview.write(package, load_template(package.project_root or ctx.cwd, "s00-readme-template"))


def _sync(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
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
    return {
        "ok": True,
        "alias_faults": [s.to_json() for s in faults],
        "aliases": [s.to_json() for s in after],
        "overview_changed": changed,
        "text": "\n".join(lines),
    }


def _enter(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = handoff.enter(package, args.target, aliases.alias_mode(ctx.env))
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
        result = comprehension.plan(package, args.stage, args.level, args.attempt)
        lines = [
            f"{r['level']:<10} {r.get('target', r['status'])}  {r.get('section', '')}"
            for r in result["levels"]
        ]
        result["text"] = "\n".join(lines)
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


def _abbreviate(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    result = records.abbreviate(package, _config(ctx, package), args.stage, args.by, args.reason)
    _regenerate_overview(ctx, package)
    return result


def _challenge(ctx: Context, args: argparse.Namespace) -> dict[str, Any]:
    package = ctx.package()
    if args.action == "add":
        result = records.add_challenge(package, args.stage, args.target, args.text, args.by)
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
    lines += [
        f"Override {o['id']}: {o['criterion']} in {o['stage']} by {o['by']}" for o in result["overrides"]
    ]
    lines += [f"Abbreviated: {a['stage']} (authorised by {a['by']})" for a in result["abbreviated"]]
    lines += [f"Accepted risk {r['id']} ({r['by']}, {r['stage']})" for r in result["accepted_risks"]]
    return "\n".join(lines) or "No requirements."


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
        "challenge": _challenge,
        "trace": _trace,
        "status": _status,
        "artifact": _artifact,
        "comprehension": _comprehension,
        "start": _start,
        "stage-init": _stage_init,
        "check": _check,
        "approve": _approve,
        "override": _override,
        "sync": _sync,
        "enter": _enter,
        "resolve": _resolve,
        "overview": _overview,
    }
)


# ---- output


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
        if args.command not in UNGOVERNED_OK:
            ctx.package()
        handler = HANDLERS.get(args.command)
        if handler is None:
            raise EilExit(
                EXIT_INTERNAL,
                {"ok": False, "error": f"not implemented: {args.command}"},
                f"not implemented: {args.command}",
            )
        payload = handler(ctx, args)
        if json_mode:
            emit_json(payload, stdout)
        else:
            text = render_text(payload)
            if text:
                stdout.write(text + "\n")
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

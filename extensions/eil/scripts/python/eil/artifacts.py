"""Design artifacts: ``ART`` items and their attachments (tasks T030, later T066).

An artifact is an ``ART`` item line followed by exactly one attachment, either a ```` ```mermaid ````
fence (inline form) or an ```` ```eil:artifact ```` record (file form). This module pairs them,
derives each artifact's kind, and reports what is wrong as findings (FR-071, FR-076, FR-081):

* ``artifact-unregistered``: a fence or record with no ``ART`` line, an ``ART`` line with no
  attachment, or a second attachment for one ``ART`` line;
* ``artifact-untraced``: an ``ART`` line with no ``traces:`` clause;
* ``artifact-wrong-level``: a kind the owning stage does not permit (data-model.md §Artefact);
* ``diagram-unparseable`` from ``diagrams``.

Exported files (wireframes and diagram images) add the checks in ``check_export``: the file exists
inside the package, has an allowed format, matches its recorded SHA-256 (raw bytes) and names its
source (FR-077, FR-078). ``register`` writes such a record; ``list_artifacts`` and ``orphan_findings``
report on them.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .blocks import Doc, Fence, insert_record_after, replace_record
from .clock import utc_now
from .diagrams import Diagram, parse_diagram
from .results import Finding, Refusal, refuse
from .trace import _HEADING, _ITEM_PREFIX, Item, ParseResult, item_hash, parse_document

if TYPE_CHECKING:
    from .package import Package

# Kinds an artifact may have, by owning stage. Stages not listed define no artifacts.
PERMITTED_KINDS: dict[str, set[str]] = {
    "requirements": {"c4-context", "image"},
    "functional": {"sequence", "wireframe", "image"},
    "technical": {"c4-container", "c4-component", "sequence", "er", "image"},
}
DIAGRAM_KINDS = frozenset({"c4-context", "c4-container", "c4-component", "sequence", "er"})
FILE_KINDS = frozenset({"wireframe", "image"})
ALLOWED_EXTENSIONS = frozenset({".png", ".svg", ".pdf", ".jpg", ".jpeg"})
ASSETS_DIR = "assets"
_NODE_ID = re.compile(r"[?&]node-id=[^&#\s]+")


@dataclass
class Artifact:
    item: Item
    stage: str
    form: str | None = None  # inline | file | None (no attachment)
    kind: str | None = None
    depicts: str | None = None  # for an image: the diagram kind it shows
    diagram: Diagram | None = None
    record: dict[str, Any] | None = None
    attachment_line: int | None = None

    @property
    def id(self) -> str:
        return self.item.id

    @property
    def title(self) -> str:
        return self.item.title

    @property
    def traces(self) -> list[str]:
        return self.item.traces

    @property
    def store(self) -> str | None:
        return self.item.store

    @property
    def checked(self) -> bool:
        """Only inline diagrams are structurally checked; an exported image is not (FR-076)."""
        return self.form == "inline"


@dataclass
class ArtifactScan:
    artifacts: list[Artifact] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def _is_attachment(fence: Fence) -> bool:
    return fence.language == "mermaid" or fence.info.split()[:1] == ["eil:artifact"]


def scan_document(
    doc: Doc, stage: str, parsed: ParseResult | None = None, root: Path | None = None
) -> ArtifactScan:
    """Pair every ``ART`` item with its attachment and report what is wrong. With ``root`` (the
    package directory) the exported files are checked too."""
    parsed = parsed or parse_document(doc)
    items_by_line = {item.line: item for item in parsed.items}
    task_lines = {task.line for task in parsed.tasks}
    attachments = {fence.open_no: fence for fence in doc.fences if _is_attachment(fence)}

    artifacts = {item.line: Artifact(item, stage) for item in parsed.items if item.kind == "ART"}
    anchored: list[tuple[int, int, Finding]] = []  # (document line, order, finding)

    def report(anchor: int, finding: Finding) -> None:
        anchored.append((anchor, len(anchored), finding))

    current: Artifact | None = None
    for line in doc.lines:
        if line.no in items_by_line:
            current = artifacts.get(line.no)
        elif line.no in task_lines or (
            line.kind == "text" and (_HEADING.match(line.live) or _ITEM_PREFIX.match(line.live))
        ):
            current = None
        elif line.no in attachments:
            fence = attachments[line.no]
            if current is not None and current.form is None:
                _attach(current, fence, doc)
            else:
                why = "a second attachment for the same ART line" if current else "no ART line"
                report(
                    line.no,
                    Finding(
                        "artifact-unregistered", doc.where(line.no), f"{fence.info} block has {why} before it"
                    ),
                )

    ordered = [artifacts[item.line] for item in parsed.items if item.kind == "ART"]
    for artifact in ordered:
        for finding in _check(artifact, stage, doc, root):
            report(artifact.item.line, finding)
    anchored.sort(key=lambda entry: (entry[0], entry[1]))
    return ArtifactScan(ordered, [entry[2] for entry in anchored])


def _attach(artifact: Artifact, fence: Fence, doc: Doc) -> None:
    text = "\n".join(fence.body)
    artifact.attachment_line = fence.open_no
    artifact.item.attachment = text
    if fence.language == "mermaid":
        artifact.form = "inline"
        artifact.diagram = parse_diagram(text, where=doc.path, first_line=fence.body_start)
        artifact.kind = artifact.diagram.kind
        return
    artifact.form = "file"
    record = next((r for r in doc.records() if r.open_no == fence.open_no), None)
    artifact.record = record.obj if record else None
    if artifact.record:
        artifact.kind = artifact.record.get("kind")
        artifact.depicts = artifact.record.get("depicts")


def _check(artifact: Artifact, stage: str, doc: Doc, root: Path | None = None) -> list[Finding]:
    item = artifact.item
    found: list[Finding] = []
    if artifact.form is None:
        found.append(
            Finding(
                "artifact-unregistered", item.id, f"{item.id} has no mermaid fence or eil:artifact record"
            )
        )
    if artifact.diagram is not None:
        found.extend(artifact.diagram.findings)
    if artifact.form == "file" and artifact.record is not None and artifact.kind not in FILE_KINDS:
        found.append(
            Finding(
                "malformed-record",
                item.id,
                f"eil:artifact kind must be one of {sorted(FILE_KINDS)}, not {artifact.kind!r}",
            )
        )
    if root is not None and artifact.form == "file" and artifact.record is not None:
        found.extend(check_export(artifact.id, artifact.record, root))
    found.extend(_level_findings(artifact, stage))
    if not item.traces:
        found.append(Finding("artifact-untraced", item.id, f"{item.id} has no (traces: ...) clause"))
    return found


def _level_findings(artifact: Artifact, stage: str) -> list[Finding]:
    item = artifact.item
    permitted = PERMITTED_KINDS.get(stage)
    if permitted is None:
        return [Finding("artifact-wrong-level", item.id, f"stage {stage} defines no artifacts (FR-081)")]
    kind = artifact.kind
    if kind is None:
        return []  # nothing readable to judge; the unparseable or malformed finding stands
    if kind == "image":
        if artifact.depicts in permitted and artifact.depicts != "image":
            return []
        shown = artifact.depicts or "nothing declared"
        return [
            Finding(
                "artifact-wrong-level",
                item.id,
                f"an image in {stage} must depict one of {sorted(permitted - {'image'})}; it depicts {shown}",
            )
        ]
    if kind not in permitted:
        return [
            Finding(
                "artifact-wrong-level",
                item.id,
                f"{kind} is not permitted in {stage}; permitted: {sorted(permitted)} (FR-081)",
            )
        ]
    return []


def scan_text(text: str, stage: str, path: str = "") -> ArtifactScan:
    return scan_document(Doc(text, path=path), stage)


# ---- exports: paths, hashes, provenance


def file_sha256(path: Path) -> str:
    """``sha256:`` of the file's raw bytes (never normalised: an image is not text, FR-077)."""
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_inside(root: Path, relative: str) -> Path | None:
    """``relative`` under ``root``, or ``None`` if it is absolute, uses ``..`` or resolves outside."""
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def provenance_problems(source: Any) -> list[str]:
    """What is missing from a record's ``source`` (FR-077); a Figma link must name the exact frame."""
    if not isinstance(source, dict):
        return ["no source (tool, url, exported_at, exported_by)"]
    problems = [
        f"source.{key} is missing"
        for key in ("tool", "url", "exported_at", "exported_by")
        if not str(source.get(key, "")).strip()
    ]
    tool, url = str(source.get("tool", "")).strip().casefold(), str(source.get("url", "")).strip()
    if tool == "figma" and url and not _NODE_ID.search(url):
        problems.append("the Figma link has no node-id=, so it does not name the exact frame")
    return problems


def check_export(artifact_id: str, record: dict[str, Any], root: Path) -> list[Finding]:
    """The findings for one file-form record: format, existence, hash and provenance."""
    found: list[Finding] = []
    name = record.get("file")
    if not isinstance(name, str) or not name.strip():
        found.append(Finding("artifact-missing-file", artifact_id, "the record names no file"))
    else:
        if Path(name).suffix.casefold() not in ALLOWED_EXTENSIONS:
            found.append(
                Finding(
                    "artifact-format-not-allowed",
                    artifact_id,
                    f"{name} is not one of {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                )
            )
        resolved = resolve_inside(root, name)
        if resolved is None:
            found.append(
                Finding("artifact-missing-file", artifact_id, f"{name} is outside the story directory")
            )
        elif not resolved.is_file():
            found.append(Finding("artifact-missing-file", artifact_id, f"{name} does not exist"))
        elif record.get("sha256") != file_sha256(resolved):
            found.append(
                Finding(
                    "artifact-hash-mismatch",
                    artifact_id,
                    f"{name} differs from the SHA-256 recorded for {artifact_id}; register the new export to accept it",
                )
            )
    problems = provenance_problems(record.get("source"))
    if problems:
        found.append(Finding("artifact-no-provenance", artifact_id, "; ".join(problems)))
    return found


def _recorded_files(pkg: Package) -> set[str]:
    names: set[str] = set()
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        for rec in doc.records():
            if rec.kind == "artifact" and rec.obj and isinstance(rec.obj.get("file"), str):
                names.add(Path(rec.obj["file"]).as_posix())
    return names


def orphan_findings(pkg: Package) -> list[Finding]:
    """Files in ``assets/`` that no ``eil:artifact`` record names (a finding, never a refusal)."""
    assets = pkg.root / ASSETS_DIR
    if not assets.is_dir():
        return []
    referenced = _recorded_files(pkg)
    found = []
    for path in sorted(p for p in assets.rglob("*") if p.is_file()):
        relative = path.relative_to(pkg.root).as_posix()
        if relative not in referenced:
            found.append(Finding("orphan-asset", relative, f"{relative} is named by no eil:artifact record"))
    return found


# ---- states and the list


def artifact_state(
    artifact: Artifact, findings: list[Finding], approval: dict[str, Any] | None = None
) -> str:
    """One state for the overview and ``artifact list`` (data-model.md §Artefact state)."""
    mine = {f.code for f in findings if f.where == artifact.id}
    if artifact.form is None:
        return "unregistered"
    if artifact.diagram is not None and any(
        f.code == "diagram-unparseable" for f in artifact.diagram.findings
    ):
        return "unparsed"
    for code, state in (
        ("diagram-inconsistent", "inconsistent"),
        ("artifact-missing-file", "missing-file"),
        ("artifact-hash-mismatch", "hash-mismatch"),
        ("artifact-no-provenance", "no-provenance"),
        ("artifact-format-not-allowed", "format-not-allowed"),
    ):
        if code in mine:
            return state
    approved = ((approval or {}).get("items") or {}).get(artifact.id)
    if approved is not None and approved != item_hash(artifact.item):
        return "changed-since-approval"
    return "ok"


def list_artifacts(pkg: Package, stage: str | None = None) -> list[dict[str, Any]]:
    """Every artifact with kind, stage, form, derived state and traces (FR-086)."""
    from .gates import CRITERIA_BY_STAGE, check_stage  # lazily: gates imports this module

    rows: list[dict[str, Any]] = []
    for name in pkg.existing_stages():
        if stage is not None and name != stage:
            continue
        try:
            doc = pkg.doc(name)
        except UnicodeDecodeError:
            continue
        parsed = parse_document(doc)
        scan = scan_document(doc, name, parsed, root=pkg.root)
        rule_findings = check_stage(pkg, name, write=False).findings if name in CRITERIA_BY_STAGE else []
        approval = pkg.state(name).approval
        for art in scan.artifacts:
            rows.append(
                {
                    "id": art.id,
                    "kind": art.kind or "unknown",
                    "stage": name,
                    "form": art.form or "none",
                    "state": artifact_state(art, [*scan.findings, *rule_findings], approval),
                    "traces": list(art.traces),
                    "title": art.title,
                }
            )
    return rows


# ---- registering an export


def _find_artifact(pkg: Package, art_id: str) -> tuple[str, Doc, Artifact] | None:
    for stage in pkg.existing_stages():
        try:
            doc = pkg.doc(stage)
        except UnicodeDecodeError:
            continue
        parsed = parse_document(doc)
        for art in scan_document(doc, stage, parsed).artifacts:
            if art.id == art_id:
                return stage, doc, art
    return None


def register(
    pkg: Package,
    art_id: str,
    file: str,
    kind: str,
    source_tool: str,
    source_url: str,
    depicts: str | None = None,
    exported_on: str | None = None,
    exported_by: str | None = None,
    cwd: Path | None = None,
    default_by: str | None = None,
) -> dict[str, Any]:
    """Record an exported file for an existing ``ART`` item, or refuse and write nothing.

    The file is copied into ``assets/`` (unless it is already there), its raw bytes are hashed and
    the ``eil:artifact`` record is written under the item line. Registering again for the same id
    replaces the record and the file; with unchanged inputs the result is byte-identical (FR-078).
    """
    found = _find_artifact(pkg, art_id)
    if found is None:
        raise refuse(
            Refusal(
                "unknown-item",
                f"no ART item {art_id!r} in any stage document",
                "Add the ART line first, then register its export",
            )
        )
    stage, doc, art = found
    root = pkg.root
    given = Path(file)
    if given.is_absolute():
        source = given.resolve()
        outside = ".." in given.parts
        try:
            source.relative_to(root.resolve())
        except ValueError:
            outside = True
    else:
        source = ((cwd or root) / given).resolve()
        outside = ".." in given.parts
        try:
            source.relative_to(root.resolve())
        except ValueError:
            outside = True
    if outside:
        raise refuse(
            Refusal(
                "path-outside-package",
                f"{file} is not inside the story directory {root}",
                "Put the exported file inside the story directory (for example in assets/) and give that path",
            )
        )
    if not source.is_file():
        raise refuse(
            Refusal(
                "artifact-missing",
                f"{file} does not exist or is not a file",
                "Give the path of the exported file",
            )
        )
    if source.suffix.casefold() not in ALLOWED_EXTENSIONS:
        raise refuse(
            Refusal(
                "artifact-format-not-allowed",
                f"{source.suffix or 'no extension'} is not an allowed format",
                f"Export as one of {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )
        )
    prior = art.record if art.form == "file" and art.record else None
    prior_source = (prior or {}).get("source") or {}
    when = exported_on or prior_source.get("exported_at") or utc_now()[:10]
    who = exported_by or prior_source.get("exported_by") or default_by or ""
    source_record = {
        "tool": source_tool.strip(),
        "url": source_url.strip(),
        "exported_at": when,
        "exported_by": who.strip(),
    }
    problems = provenance_problems(source_record)
    if problems:
        raise refuse(
            Refusal(
                "artifact-no-provenance",
                "; ".join(problems),
                "Give the tool and a link to the exact source (for Figma, the frame link with node-id=) and who exported it",
            )
        )
    if kind not in FILE_KINDS:
        raise refuse(
            Refusal(
                "artifact-wrong-level", f"kind must be one of {sorted(FILE_KINDS)}", "Use wireframe or image"
            )
        )
    permitted = PERMITTED_KINDS.get(stage, set())
    if kind == "wireframe" and "wireframe" not in permitted:
        raise refuse(
            Refusal(
                "artifact-wrong-level",
                f"a wireframe is not permitted in {stage} (FR-081)",
                "Wireframes belong in the Functional Specification",
            )
        )
    if kind == "image" and (depicts not in permitted or depicts == "image"):
        raise refuse(
            Refusal(
                "artifact-wrong-level",
                f"an image in {stage} must say what it depicts, one of {sorted(permitted - {'image'})}",
                "Pass --depicts with a kind permitted in this stage",
            )
        )
    if art.form == "inline":
        raise refuse(
            Refusal(
                "already-exists",
                f"{art_id} already has a mermaid diagram",
                "Remove the diagram first if an image should replace it",
            )
        )

    destination = root / ASSETS_DIR / source.name
    if (
        source != destination.resolve()
        and destination.exists()
        and destination.read_bytes() != source.read_bytes()
    ):
        owner = None
        for other_stage in pkg.existing_stages():
            for other in scan_document(pkg.doc(other_stage), other_stage).artifacts:
                if (
                    other.id != art_id
                    and other.record
                    and Path(str(other.record.get("file", ""))).as_posix() == f"{ASSETS_DIR}/{source.name}"
                ):
                    owner = other.id
        if owner is not None:
            raise refuse(
                Refusal(
                    "already-exists",
                    f"assets/{source.name} is already the export for {owner}",
                    "Give the file a different name",
                )
            )
    record: dict[str, Any] = {
        "file": f"{ASSETS_DIR}/{source.name}",
        "sha256": file_sha256(source),
        "kind": kind,
    }
    if depicts:
        record["depicts"] = depicts
    record["source"] = source_record

    text = pkg.read(stage)
    if art.attachment_line is not None:
        existing = next(r for r in Doc(text).records() if r.open_no == art.attachment_line)
        updated = replace_record(text, existing, record)
    else:
        updated = insert_record_after(text, art.item.end_line, "artifact", record)
    if source != destination.resolve():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    pkg.doc_path(stage).write_bytes(updated.encode("utf-8"))
    return {
        "ok": True,
        "id": art_id,
        "stage": stage,
        "record": record,
        "sha256": record["sha256"],
        "text": f"Registered {record['file']} for {art_id}.",
    }

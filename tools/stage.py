"""Stage the files that ship, for installing or archiving (research F-16).

``specify preset add --dev <dir>`` copies its whole source directory and has no ignore mechanism, so
installing from the repository root would put ``.venv``, ``specs/`` and ``tests/`` into your
project. Stage first, then install from the staged copies:

    python3 tools/stage.py /tmp/eil-stage
    specify extension add --dev /tmp/eil-stage/extension
    specify preset add --dev /tmp/eil-stage/preset

The extension must be installed before the preset (the preset's commands check for it).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PRESET_FILES = ("preset.yml", "LICENSE", "README.md")
PRESET_DIRS = ("templates", "commands")
_JUNK = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache")


def stage_preset(destination: Path) -> Path:
    """Copy the preset's shipped files into ``destination`` (created) and return it."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in PRESET_FILES:
        source = REPO_ROOT / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    for name in PRESET_DIRS:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(source, destination / name, ignore=_JUNK, dirs_exist_ok=True)
    return destination


def stage_extension(destination: Path) -> Path:
    """Copy the extension directory (without caches) into ``destination`` and return it."""
    shutil.copytree(REPO_ROOT / "extensions" / "eil", destination, ignore=_JUNK, dirs_exist_ok=True)
    return destination


def _read_version(manifest: Path) -> str:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return "0.0.0"


def _version() -> str:
    return _read_version(REPO_ROOT / "preset.yml")


def check_release_tag(tag: str) -> str | None:
    """Return why ``tag`` (for example ``v0.1.0``) cannot release this tree, or None when it can:
    the preset and the extension must both carry the version the tag names."""
    wanted = tag.removeprefix("v")
    found = {
        "preset.yml": _read_version(REPO_ROOT / "preset.yml"),
        "extensions/eil/extension.yml": _read_version(REPO_ROOT / "extensions" / "eil" / "extension.yml"),
    }
    wrong = [f"{name} says {version}" for name, version in found.items() if version != wanted]
    return f"tag {tag} does not match: " + ", ".join(wrong) if wrong else None


def make_archives(directory: Path) -> tuple[Path, Path]:
    """Write ``eil-extension-<version>.zip`` and ``engineer-in-the-loop-preset-<version>.zip`` into
    ``directory``, each holding the staged files at its root, and return their paths. The same
    files as a staged install: nothing from ``.venv``, ``specs`` or ``tests``."""
    import tempfile
    import zipfile

    directory.mkdir(parents=True, exist_ok=True)
    version = _version()
    made: list[Path] = []
    for name, stage in (("eil-extension", stage_extension), ("engineer-in-the-loop-preset", stage_preset)):
        with tempfile.TemporaryDirectory() as scratch:
            staged = stage(Path(scratch) / "files")
            archive = directory / f"{name}-{version}.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(staged.rglob("*")):
                    if path.is_file():
                        bundle.write(path, path.relative_to(staged).as_posix())
        made.append(archive)
    return made[0], made[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage the extension and preset for installation.")
    parser.add_argument("directory", type=Path, help="where to write extension/ and preset/")
    parser.add_argument("--archives", action="store_true", help="also write the release .zip archives")
    parser.add_argument("--tag", help="refuse unless the manifests carry this tag's version")
    args = parser.parse_args(argv)
    if args.tag and (problem := check_release_tag(args.tag)):
        print(problem, file=sys.stderr)
        return 1
    if args.archives:
        extension, preset = make_archives(args.directory)
        print(f"Wrote {extension} and {preset}")
        return 0
    stage_extension(args.directory / "extension")
    stage_preset(args.directory / "preset")
    print(f"Staged {args.directory}/extension and {args.directory}/preset")
    return 0


if __name__ == "__main__":
    sys.exit(main())

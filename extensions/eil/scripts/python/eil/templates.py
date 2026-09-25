"""Find a template by name the way Spec Kit resolves them (research D-02, contract test C-03).

Resolution goes through the project's own ``resolve-template.sh`` so that project overrides, the
preset and the core templates apply in Spec Kit's order. The helper never reads the preset's files
directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .results import usage_error


def load_template(project_root: Path | None, name: str) -> str:
    if project_root is not None:
        script = project_root / ".specify" / "scripts" / "bash" / "resolve-template.sh"
        if script.is_file():
            try:
                proc = subprocess.run(
                    [str(script), name, "--json"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if proc.returncode == 0:
                    return str(json.loads(proc.stdout)["TEMPLATE_CONTENT"])
            except (OSError, subprocess.SubprocessError, ValueError, KeyError):
                pass
        plain = project_root / ".specify" / "templates" / f"{name}.md"
        if plain.is_file():
            return plain.read_text(encoding="utf-8")
    raise usage_error(
        f"template {name!r} was not found; is the engineer-in-the-loop preset installed? "
        "(specify extension add eil, then specify preset add engineer-in-the-loop)"
    )

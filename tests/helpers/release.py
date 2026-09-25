"""Staging for installs in tests. The logic lives in ``tools/stage.py``, which is also what the
README tells people to run (research F-16)."""

from tools.stage import REPO_ROOT, stage_extension, stage_preset

__all__ = ["REPO_ROOT", "stage_extension", "stage_preset"]

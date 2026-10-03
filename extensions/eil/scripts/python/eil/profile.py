"""The small-story profile (research D-52; FR-019 to FR-022).

One authorisation per story, by a person allowed to authorise abbreviations, with their reason. It is
held in the record file under ``story.profile`` and shown on the overview, in ``status``, at the gates
it affects and in the trace report. While it is active:

* the Functional wireframe criterion (FUN-G15) is met by it, and says so;
* the inferred content of the AI Specification, plan and tasks is reviewed as one ``derived`` list,
  and implementation is refused until that list is answered;
* entry to planning and task generation proceeds under an override of ``unreviewed-ai-content``,
  recorded when the profile is set, named and reasoned like any override, and withdrawn with it;
* the comprehension check asks two levels, ``explain`` and ``apply``; the others are not applicable.

Every approval, challenge rule and other override is unchanged. The AI may propose the profile; only a
person sets or withdraws it (FR-045).
"""

from __future__ import annotations

from typing import Any

from .clock import utc_now
from .identity import Config, confirmer_refusal, is_ai_actor
from .package import Package
from .results import Refusal, refuse

NAMES = ("small",)
SCOPE = ["enter plan", "enter tasks"]
LEVELS = ("explain", "apply")
CRITERION = "FUN-G15"


def recorded(pkg: Package) -> dict[str, Any] | None:
    """The story's profile record, active or withdrawn, or ``None``."""
    found = pkg.story_record().get("profile")
    return found if isinstance(found, dict) and found.get("name") in NAMES else None


def active(pkg: Package) -> dict[str, Any] | None:
    """The profile while it is in force (set and not withdrawn)."""
    found = recorded(pkg)
    return found if found is not None and not found.get("withdrawn") else None


def label(found: dict[str, Any]) -> str:
    return f"small-story profile ({found.get('by')}, {str(found.get('at', ''))[:10]})"


def _authority(pkg: Package, config: Config, by: str, reason: str) -> list[Refusal]:
    from .records import authorisers_for

    refusals: list[Refusal] = []
    if is_ai_actor(by):
        refusals.append(Refusal("ai-approval", f"{by!r} is the AI; only a person authorises the profile", "Ask the developer"))
    else:
        problem = confirmer_refusal(by, authorisers_for(pkg, config), "the story", authorising=True)
        if problem:
            refusals.append(problem)
    if not (reason or "").strip():
        refusals.append(Refusal("reason-required", "the profile needs the person's reason", "Ask why, and pass their words with --reason"))
    return refusals


def set_profile(pkg: Package, config: Config, name: str, by: str, reason: str) -> dict[str, Any]:
    """Authorise the profile, and record its override of ``unreviewed-ai-content`` for plan and task entry."""
    from .records import next_override_id

    if name not in NAMES:
        raise refuse(Refusal("unknown-item", f"{name!r} is not a profile", f"Use one of: {', '.join(NAMES)}"))
    refusals = _authority(pkg, config, by, reason)
    if active(pkg) is not None:
        refusals.append(Refusal("profile-active", "the small-story profile is already authorised for this story", "Withdraw it first to change it"))
    if refusals:
        raise refuse(*refusals)
    at = utc_now()
    override = {
        "id": next_override_id(pkg),
        "criterion": "unreviewed-ai-content",
        "scope": list(SCOPE),
        "by": by.strip(),
        "at": at,
        "reason": reason.strip(),
        "basis": "small-story profile",
    }
    record = {"name": name, "by": by.strip(), "reason": reason.strip(), "at": at, "withdrawn": None, "override": override}
    pkg.write_story_record("profile", record)
    return {
        "ok": True,
        "profile": record,
        "override": override,
        "text": (
            f"Small-story profile authorised by {record['by']}: {record['reason']}. Recorded {override['id']}, an override "
            "of unreviewed-ai-content for plan and task entry. Implementation still waits for the derived review."
        ),
    }


def withdraw(pkg: Package, config: Config, by: str, reason: str) -> dict[str, Any]:
    """Withdraw the profile and its override; stages not yet approved return to the full workflow."""
    refusals = _authority(pkg, config, by, reason)
    found = active(pkg)
    if found is None:
        refusals.append(Refusal("no-profile", "the small-story profile is not in force for this story", "Nothing to withdraw"))
    if refusals:
        raise refuse(*refusals)
    assert found is not None
    record = dict(found)
    record["withdrawn"] = {"by": by.strip(), "reason": reason.strip(), "at": utc_now()}
    pkg.write_story_record("profile", record)
    return {
        "ok": True,
        "profile": record,
        "text": f"Small-story profile withdrawn by {by.strip()}: {reason.strip()}. Its override {record['override']['id']} is withdrawn with it.",
    }


def override(pkg: Package) -> dict[str, Any] | None:
    """The profile's override while the profile is in force."""
    found = active(pkg)
    return found.get("override") if found is not None else None


__all__ = ["CRITERION", "LEVELS", "SCOPE", "active", "label", "override", "recorded", "set_profile", "withdraw"]

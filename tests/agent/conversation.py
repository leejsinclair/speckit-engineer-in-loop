"""Deterministic human boundary for multi-turn agent trials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class UnexpectedInteraction(RuntimeError):
    """The agent requested a human decision the trial did not pre-authorise."""


@dataclass(frozen=True)
class PersonReply:
    kind: str
    text: str


class NoProgress(RuntimeError):
    """Authoritative EIL state did not change across several agent turns."""


class ProgressGuard:
    def __init__(self, limit: int = 5) -> None:
        self.limit = limit
        self._last: str | None = None
        self._unchanged = 0

    def observe(self, status: dict[str, Any]) -> None:
        marker = repr(status)
        if marker == self._last:
            self._unchanged += 1
        else:
            self._last = marker
            self._unchanged = 1
        if self._unchanged >= self.limit:
            action = status.get("next_action", {})
            raise NoProgress(
                f"EIL state did not change for {self._unchanged} turns; next action: "
                f"{action.get('command') if isinstance(action, dict) else None}"
            )


_APPROVALS = {
    "requirements": "Yes, I approve the requirements as the problem I intend to solve.",
    "functional": "Yes, I approve the functional specification as the behaviour I require.",
    "technical": "Yes, I approve the technical specification as the solution I intend to build.",
    "completion": "Yes, I reviewed the evidence and confirm the story is complete.",
}


class ScriptedPerson:
    """Answer known EIL interactions and refuse to invent any other human decision."""

    def __init__(self, name: str) -> None:
        self.name = name

    def reply(self, transcript: str, status: dict[str, Any]) -> PersonReply:
        text = transcript.strip()
        lowered = text.lower()
        action = status.get("next_action", {})
        if not isinstance(action, dict):
            raise UnexpectedInteraction("status has no usable next_action")

        if _is_review_surface_question(lowered):
            return PersonReply("review-surface", f"Here in chat. My name is {self.name}.")

        if re.search(r"(?:your name|name you are confirming as|confirming person's name)", lowered):
            return PersonReply("identity", f"My name is {self.name}.")

        question = action.get("question")
        stage = action.get("stage")
        if isinstance(question, str) and question.lower() in lowered and stage in _APPROVALS:
            return PersonReply("approval", _APPROVALS[stage])

        if _is_comprehension_question(lowered):
            return PersonReply(
                "comprehension",
                "Please reveal the answer for this level, record it as revealed, and continue without a re-ask.",
            )

        if re.search(r"waiting for your review of|respond with:.*\bok\b", lowered, re.DOTALL):
            return PersonReply("review", "ok")

        if _is_review_request(lowered):
            return PersonReply("review", "I accept all entries in this review list.")

        open_challenges = status.get("outstanding", {}).get("open_challenges", [])
        if open_challenges:
            challenge = str(open_challenges[0])
            return PersonReply(
                "challenge",
                f"I accept {challenge}. Address it consistently with the behaviour and decisions I already provided.",
            )

        kind = action.get("kind")
        command = action.get("command")
        if kind in {"draft", "check"} and isinstance(command, str):
            skill = command.removeprefix("/")
            return PersonReply(
                "continue",
                f"Call the Skill tool with skill={skill!r} now and follow it completely. "
                "Do not create substitute workflow scripts or reports.",
            )

        if kind == "done":
            raise UnexpectedInteraction("the story is already complete")

        raise UnexpectedInteraction(f"unrecognised human interaction: {text[:200]}")


def _is_comprehension_question(text: str) -> bool:
    if "?" not in text:
        return False
    return "comprehension" in text or bool(
        re.search(r"\b(recognise|recognize|explain|apply|trace|evaluate)\b", text)
    )


def _is_review_surface_question(text: str) -> bool:
    return (
        "browser" in text
        and "chat" in text
        and bool(re.search(r"how would you like to review|review on a page|which would you prefer", text))
    )


def _is_review_request(text: str) -> bool:
    if "review" not in text:
        return False
    return bool(
        re.search(r"\b(accept all|accept these|do you accept|reply.*(?:entries|list)|ok to the rest)\b", text)
    )

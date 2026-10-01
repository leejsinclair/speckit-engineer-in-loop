"""Content fingerprint of a stage document (FR-011, FR-044, task T018).

The algorithm is the normative one in contracts/document-format.md:

1. decode UTF-8 (failure is ``NotUtf8``, there is no fingerprint);
2. ``\\r\\n`` and lone ``\\r`` become ``\\n``;
3. remove every ``approval``, ``assessment``, ``comprehension``, ``provenance`` and ``changelog``
   region, including its marker lines and any single blank line directly after the end marker (a
   ``## Change Log`` or ``## Record`` heading directly above its region goes with it);
4. remove every ``[ai-draft]`` tag (and one preceding space) that sits **outside an HTML
   comment**: reviewing and untagging a human's own text is not a content change (research D-23;
   matches ``trace.item_hash``, which already excludes it from the item hash). The templates'
   own instructional comments say the word without it ever being a tag on anything, and must
   keep counting as ordinary content;
5. strip trailing spaces and tabs from each line;
6. collapse each run of two or more blank lines into one;
7. strip leading and trailing blank lines;
8. append one ``\\n``, encode UTF-8, SHA-256.

A region whose end marker never appears is not removed, so the document reads as changed
(``malformed-region`` is reported separately, by ``blocks``).
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

EXCLUDED_REGIONS = ("approval", "assessment", "comprehension", "provenance", "changelog")
# The helper adds these two headings with their regions on first write; the heading goes with the
# region so that adding them never changes a fingerprint (contracts/document-format.md, D-42).
_OWN_HEADING = {"changelog": "change log", "provenance": "record"}
_H2_TITLE = re.compile(r"^##\s+(?P<title>.+?)\s*#*\s*$")

_BEGIN = {f"<!-- eil:begin {name} -->": name for name in EXCLUDED_REGIONS}
_END = {name: f"<!-- eil:end {name} -->" for name in EXCLUDED_REGIONS}
_AI_DRAFT_TAG = re.compile(r"\s*\[ai-draft\]")
_COMMENT_OPEN = "<!--"
_COMMENT_CLOSE = "-->"


class NotUtf8(Exception):
    """The file is not valid UTF-8 (reported as ``not-utf8``, exit 2)."""


def _strip_regions(lines: list[str]) -> list[str]:
    kept: list[str] = []
    i = 0
    while i < len(lines):
        name = _BEGIN.get(lines[i].strip())
        if name is None:
            kept.append(lines[i])
            i += 1
            continue
        end = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == _END[name]), None)
        if end is None:  # unmatched: leave the text in, so the document reads as changed
            kept.append(lines[i])
            i += 1
            continue
        heading = _OWN_HEADING.get(name)
        if heading is not None:
            last = next((j for j in range(len(kept) - 1, -1, -1) if kept[j].strip()), None)
            match = _H2_TITLE.match(kept[last]) if last is not None else None
            if match and " ".join(match["title"].split()).casefold() == heading:
                del kept[last:]
        i = end + 1
        if i < len(lines) and lines[i].strip() == "":
            i += 1  # the single blank line directly after the end marker
    return kept


def _strip_ai_draft(lines: list[str]) -> list[str]:
    """Remove every ``[ai-draft]`` tag, but never inside an HTML comment (a real tag is only ever
    written on live text). Comment state carries across lines, so a multi-line comment is covered.
    """
    out: list[str] = []
    in_comment = False
    for line in lines:
        pieces: list[str] = []
        i = 0
        while i < len(line):
            if in_comment:
                end = line.find(_COMMENT_CLOSE, i)
                if end == -1:
                    pieces.append(line[i:])
                    i = len(line)
                else:
                    end += len(_COMMENT_CLOSE)
                    pieces.append(line[i:end])
                    i = end
                    in_comment = False
                continue
            start = line.find(_COMMENT_OPEN, i)
            if start == -1:
                pieces.append(_AI_DRAFT_TAG.sub("", line[i:]))
                i = len(line)
            else:
                pieces.append(_AI_DRAFT_TAG.sub("", line[i:start]))
                pieces.append(_COMMENT_OPEN)
                i = start + len(_COMMENT_OPEN)
                in_comment = True
        out.append("".join(pieces))
    return out


def normalise_lines(text: str) -> list[str]:
    """Steps 2 to 7 as a list of lines (no trailing newline element)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped = _strip_regions(text.split("\n"))
    return _collapse(_strip_ai_draft(stripped))


def _collapse(lines: list[str]) -> list[str]:
    stripped = [line.rstrip(" \t") for line in lines]
    collapsed: list[str] = []
    for line in stripped:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return collapsed


def normalise(text: str) -> str:
    """The exact text that is hashed (steps 2 to 8, before encoding)."""
    return "\n".join(normalise_lines(text)) + "\n"


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=256)
def fingerprint_text(text: str) -> str:
    return _digest(normalise(text))


def fingerprint_file(path: Path | str) -> str:
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NotUtf8(str(path)) from exc
    return fingerprint_text(text)


def normalise_fragment(text: str) -> str:
    """Whitespace normalisation only (steps 2, 5 and 6 and edge trimming), with no region removal
    and no ``[ai-draft]`` stripping (callers, such as ``trace.item_hash``, already remove tags).

    Used for item hashes, which hash a fragment of a document (document-format.md §Item hash).
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(_collapse(text.split("\n"))) + "\n"


def hash_fragment(text: str) -> str:
    return _digest(normalise_fragment(text))

"""The browser review page's HTML (004 research D-60, D-62, D-69; contracts/page.md).

The Markdown renderer below (``tokenize`` to ``render_markdown``) is copied from the rich
specification viewer, ``rich-specification-viewer/specview.py`` at commit a267058, and adapted:

* reference codes are the helper's item and task ids, and an item's anchor is its id as written
  (``#REQ-004``), so a link agrees with ``trace`` and ``check``;
* everything that fetched from elsewhere (the viewer's Mermaid CDN script) is removed: a diagram is
  shown as source, and drawn by the browser only with ``review.diagram_script`` (D-69).

Its tests travel with it (``tests/unit/test_page_markdown.py``). The page itself presents and sends;
it decides nothing and writes nothing: every answer is stored by ``reviews.answer`` (constitution
1.3.0, Principle I).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# ---- reference codes (the helper's ids: trace.KINDS and task ids)

CODE = r"(?:(?:REQ|UC|FR|NFR|DEC|AIS|EVD|OQ|OVR|CH|ART|RF)-\d{3,}|T\d{3,})"
CODE_RE = re.compile(r"\b" + CODE + r"\b")
ITEM_DEF_RE = re.compile(r"^\s*(?:[-*+]\s+)?\*\*(" + CODE + r")\*\*\s*:")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HEADING_DEF_RE = re.compile(r"^(" + CODE + r")\b")
TASK_DEF_RE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(T\d{3,})\b")


def anchor_for(code: str) -> str:
    return code


# ---- Markdown renderer (copied; see the module docstring)

FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)")
EIL_BEGIN_RE = re.compile(r"^\s*<!--\s*eil:begin\s+(\w+)\s*-->\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
HR_RE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
QUOTE_RE = re.compile(r"^ {0,3}>\s?(.*)$")
TASK_BOX_RE = re.compile(r"^\[([ xX])\]\s+(.*)$", re.S)
CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1")
LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
STRONG_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
EM_STAR_RE = re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])")
EM_UNDER_RE = re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)")


@dataclass
class Fence:
    info: str
    lines: list[str]


def tokenize(text: str) -> tuple[list[Any], list[tuple[str, str]]]:
    """Split a document into line strings and Fence tokens, dropping HTML comments and ``eil:``
    regions and blocks. Returns the tokens and the dropped ``eil:`` fenced blocks as ``(kind, body)``."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    tokens: list[Any] = []
    eil_blocks: list[tuple[str, str]] = []
    i = 0
    in_comment = False
    while i < len(lines):
        line = lines[i]
        if in_comment:
            end = line.find("-->")
            if end < 0:
                i += 1
                continue
            in_comment = False
            line = line[end + 3 :]
            if not line.strip():
                tokens.append("")
                i += 1
                continue
        begin = EIL_BEGIN_RE.match(line)
        if begin:
            end_marker = re.compile(r"^\s*<!--\s*eil:end\s+" + re.escape(begin.group(1)) + r"\s*-->\s*$")
            j = i + 1
            while j < len(lines) and not end_marker.match(lines[j]):
                j += 1
            i = j + 1
            continue
        fence = FENCE_OPEN_RE.match(line)
        if fence:
            marker, info = fence.group(1), fence.group(2)
            close = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*$")
            body = []
            j = i + 1
            while j < len(lines) and not close.match(lines[j]):
                body.append(lines[j])
                j += 1
            if info.startswith("eil:"):
                eil_blocks.append((info[4:], "\n".join(body)))
            else:
                tokens.append(Fence(info.lower(), body))
            i = j + 1
            continue
        # HTML comments, possibly several on one line or spanning lines
        out = ""
        rest = line
        while "<!--" in rest:
            before, _, after = rest.partition("<!--")
            out += before
            end = after.find("-->")
            if end < 0:
                in_comment = True
                rest = ""
                break
            rest = after[end + 3 :]
        out += rest
        tokens.append(out if out.strip() or out == line else "")
        i += 1
    return tokens, eil_blocks


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", slug) or "section"


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def safe_href(href: str) -> str:
    scheme = href.split(":", 1)[0].lower() if ":" in href.split("/", 1)[0] else ""
    if scheme and scheme not in ("http", "https", "mailto"):
        return "#"
    return href


class RenderContext:
    """What the renderer needs from its caller: how to mark a code, and whether it renders a
    preview (no marking, diagrams replaced by a note)."""

    def __init__(self, marker: Any = None, tooltip: bool = False) -> None:
        self.marker = marker
        self.tooltip = tooltip
        self.slugs: dict[str, int] = {}

    def unique_id(self, base: str) -> str:
        count = self.slugs.get(base, 0)
        self.slugs[base] = count + 1
        return base if count == 0 else "%s-%d" % (base, count + 1)


def render_inline(text: str, ctx: RenderContext, skip_code: str | None = None) -> str:
    """Escape first, then inline code, links and emphasis, then mark codes outside code."""
    held: list[str] = []

    def hold(fragment: str) -> str:
        held.append(fragment)
        return "\x00%d\x00" % (len(held) - 1)

    text = CODE_SPAN_RE.sub(lambda m: hold("<code>" + esc(m.group(2).strip()) + "</code>"), text)
    text = LINK_RE.sub(
        lambda m: hold('<a href="%s">%s</a>' % (esc(safe_href(m.group(2))), _emphasis(esc(m.group(1))))), text
    )
    text = _emphasis(esc(text))
    if ctx.marker is not None:
        skipped = [False]

        def mark(m: re.Match[str]) -> str:
            code = m.group(0)
            if skip_code == code and not skipped[0]:
                skipped[0] = True
                return code
            return str(ctx.marker(code))

        text = CODE_RE.sub(mark, text)
    return re.sub("\x00(\\d+)\x00", lambda m: held[int(m.group(1))], text)


def _emphasis(text: str) -> str:
    text = STRONG_RE.sub(r"<strong>\1</strong>", text)
    text = EM_STAR_RE.sub(r"<em>\1</em>", text)
    return EM_UNDER_RE.sub(r"<em>\1</em>", text)


def _is_blank(token: Any) -> bool:
    return isinstance(token, str) and not token.strip()


def _starts_block(token: Any, following: Any = None) -> bool:
    if isinstance(token, Fence):
        return True
    return bool(
        HEADING_RE.match(token)
        or HR_RE.match(token)
        or LIST_RE.match(token)
        or QUOTE_RE.match(token)
        or (token.lstrip().startswith("|") and isinstance(following, str) and TABLE_SEP_RE.match(following))
    )


def render_tokens(tokens: list[Any], ctx: RenderContext) -> str:
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if isinstance(token, Fence):
            out.append(_render_fence(token, ctx))
            i += 1
            continue
        if not token.strip():
            i += 1
            continue
        heading = HEADING_RE.match(token)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            code = HEADING_DEF_RE.match(title)
            ident = ctx.unique_id(anchor_for(code.group(1)) if code else slugify(title))
            body = render_inline(title, ctx, code.group(1) if code else None)
            out.append('<h%d id="%s">%s</h%d>' % (level, esc(ident), body, level))
            i += 1
            continue
        if HR_RE.match(token):
            out.append("<hr>")
            i += 1
            continue
        following = tokens[i + 1] if i + 1 < n else None
        if token.lstrip().startswith("|") and isinstance(following, str) and TABLE_SEP_RE.match(following):
            j = i + 2
            rows = [token]
            while j < n and isinstance(tokens[j], str) and tokens[j].lstrip().startswith("|"):
                rows.append(tokens[j])
                j += 1
            out.append(_render_table(rows, ctx))
            i = j
            continue
        if QUOTE_RE.match(token):
            inner = []
            while i < n and isinstance(tokens[i], str) and QUOTE_RE.match(tokens[i]):
                inner.append(QUOTE_RE.match(tokens[i]).group(1))  # type: ignore[union-attr]
                i += 1
            out.append("<blockquote>%s</blockquote>" % render_tokens(inner, ctx))
            continue
        if LIST_RE.match(token):
            block = [token]
            first = LIST_RE.match(token)
            assert first is not None
            base, ordered = len(first.group(1)), first.group(2)[0].isdigit()

            def sibling_of_other_kind(line: str, base: int = base, ordered: bool = ordered) -> bool:
                m = LIST_RE.match(line)
                return bool(m) and len(m.group(1)) <= base and m.group(2)[0].isdigit() != ordered  # type: ignore[union-attr]

            j = i + 1
            while j < n and isinstance(tokens[j], str):
                line = tokens[j]
                if not line.strip():
                    nxt = tokens[j + 1] if j + 1 < n else None
                    if (
                        isinstance(nxt, str)
                        and nxt.strip()
                        and (LIST_RE.match(nxt) or nxt[:1] in " \t")
                        and not sibling_of_other_kind(nxt)
                    ):
                        block.append(line)
                        j += 1
                        continue
                    break
                if sibling_of_other_kind(line):
                    break
                if LIST_RE.match(line) or line[:1] in " \t":
                    block.append(line)
                    j += 1
                    continue
                if HEADING_RE.match(line) or HR_RE.match(line) or QUOTE_RE.match(line):
                    break
                block.append(line)  # lazy continuation of the last item
                j += 1
            out.append(_render_list(block, ctx))
            i = j
            continue
        para = [token]
        j = i + 1
        while j < n and isinstance(tokens[j], str) and tokens[j].strip():
            if _starts_block(tokens[j], tokens[j + 1] if j + 1 < n else None):
                break
            para.append(tokens[j])
            j += 1
        text = "\n".join(line.strip() for line in para)
        item = ITEM_DEF_RE.match(para[0])
        attr = ' id="%s"' % esc(ctx.unique_id(anchor_for(item.group(1)))) if item else ""
        out.append("<p%s>%s</p>" % (attr, render_inline(text, ctx, item.group(1) if item else None)))
        i = j
    return "\n".join(out)


def _render_fence(fence: Fence, ctx: RenderContext) -> str:
    source = "\n".join(fence.lines)
    if fence.info == "mermaid":
        if ctx.tooltip:
            return '<p class="diagram-note">A diagram is shown here in the document.</p>'
        return '<pre class="mermaid-src">%s</pre>' % esc(source)
    lang = ' class="language-%s"' % esc(fence.info) if fence.info else ""
    return "<pre><code%s>%s</code></pre>" % (lang, esc(source))


def _split_row(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells = re.split(r"(?<!\\)\|", row)
    return [cell.strip().replace("\\|", "|") for cell in cells]


def _render_table(rows: list[str], ctx: RenderContext) -> str:
    head = _split_row(rows[0])
    body = [_split_row(r) for r in rows[1:]]
    parts = ["<table><thead><tr>"]
    parts += ["<th>%s</th>" % render_inline(c, ctx) for c in head]
    parts.append("</tr></thead><tbody>")
    for cells in body:
        parts.append("<tr>" + "".join("<td>%s</td>" % render_inline(c, ctx) for c in cells) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _render_list(lines: list[str], ctx: RenderContext) -> str:
    first = LIST_RE.match(lines[0])
    assert first is not None
    base = len(first.group(1).expandtabs(4))
    ordered = first.group(2)[0].isdigit()
    items: list[tuple[list[str], list[str], str]] = []  # (text lines, child lines, first raw line)
    for line in lines:
        m = LIST_RE.match(line)
        if m and len(m.group(1).expandtabs(4)) <= base:
            items.append(([m.group(3)], [], line))
            continue
        text_lines, child_lines, _ = items[-1]
        if not line.strip():
            if child_lines:
                child_lines.append("")
            continue
        if child_lines or m:
            child_lines.append(line)
        else:
            text_lines.append(line.strip())
    tag = "ol" if ordered else "ul"
    start = ""
    if ordered:
        number = int(re.match(r"\d+", first.group(2)).group(0))  # type: ignore[union-attr]
        if number != 1:
            start = ' start="%d"' % number
    out = ["<%s%s>" % (tag, start)]
    for text_lines, child_lines, raw in items:
        text = "\n".join(text_lines)
        ident = ""
        skip = None
        definition = ITEM_DEF_RE.match(raw) or TASK_DEF_RE.match(raw)
        if definition:
            skip = definition.group(1)
            ident = ' id="%s"' % esc(ctx.unique_id(anchor_for(skip)))
        box = TASK_BOX_RE.match(text)
        prefix = ""
        cls = ""
        if box:
            checked = " checked" if box.group(1) in "xX" else ""
            prefix = '<input type="checkbox" disabled%s> ' % checked
            text = box.group(2)
            cls = ' class="task"'
        body = prefix + render_inline(text, ctx, skip)
        if child_lines:
            indents = [len(c) - len(c.lstrip()) for c in child_lines if c.strip()]
            cut = min(indents) if indents else 0
            body += render_tokens([c[cut:] for c in child_lines], ctx)
        out.append("<li%s%s>%s</li>" % (ident, cls, body))
    out.append("</%s>" % tag)
    return "".join(out)


def render_markdown(text: str, ctx: RenderContext | None = None) -> str:
    tokens, _ = tokenize(text)
    return render_tokens(tokens, ctx or RenderContext())


# ---- the Content-Security-Policy (D-69)


def script_origin(url: str | None) -> str | None:
    """The origin of the configured diagram script, or ``None``."""
    if not url:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme == "https" and parts.netloc else None


def csp(nonce: str, diagram_origin: str | None = None) -> str:
    """The page's policy: nothing loads from anywhere but the page itself, except the one diagram
    script a project named (D-69)."""
    scripts = f"'self' 'nonce-{nonce}'" + (f" {diagram_origin}" if diagram_origin else "")
    return (
        f"default-src 'none'; script-src {scripts}; style-src 'self' 'nonce-{nonce}'; connect-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )




# ---- the review page (D-62; contracts/page.md)

POLL_MS = 4000  # how often the page asks for ``/state`` (D-68: at most 5 seconds)
STAGE_LABELS = {"requirements": "Requirements", "functional": "Functional Specification", "technical": "Technical Specification"}
LIST_LABELS = {"inferred": "blocks that need review", "changes": "changes since approval"}
DONE = {"accept": "Accepted", "except": "Sent back", "question": "Questioned"}
COMPLETE = "List complete. Return to the chat and say done."
NOTHING = "Nothing to answer now."
STOPPED = "The review page has stopped; ask the agent to start it again"
CHANGED = "This block changed; read it again before answering"
_SECTION_HEADING = re.compile(r"^\s{0,3}(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_SECTION_CLAUSE = re.compile(r"\((?:traces|code|status|material|store|accepted-by|decided):[^)]*\)|\s*\[(?:ai-draft|pending-clarification)\]")


def stage_label(stage: str | None) -> str:
    return STAGE_LABELS.get(stage or "", (stage or "").title())


def footer_text(listed: Any) -> str:
    """The footer: nothing listed at all, or every entry answered, or nothing yet (empty)."""
    if listed is None or not listed.full:
        return NOTHING
    return COMPLETE if not listed.entries else ""


def _section_title(text: str) -> str | None:
    """The section a level-1 or level-2 heading opens, normalised as ``content.blocks_of`` does."""
    match = _SECTION_HEADING.match(text)
    if not match or len(match["hashes"]) > 2:
        return None
    return " ".join(_SECTION_CLAUSE.sub("", match["title"]).split())


def _when(at: Any) -> str:
    text = str(at or "")
    return text.replace("T", " ").replace("Z", " UTC") if text else "just now"


def stored_text(answer: dict[str, Any]) -> str:
    """How a stored answer reads on the page: what, who, when, and the comment."""
    line = f"{DONE.get(str(answer.get('disposition')), 'Answered')} by {answer.get('by')} on {_when(answer.get('at'))}"
    if answer.get("together"):
        line += f", with the rest of {answer['together']}"
    return line + (f": {answer['comment']}" if answer.get("comment") else ".")


def _control(
    key: str, entry: Any, answer: dict[str, Any] | None, last: dict[str, Any] | None, disabled: bool, kind: str | None = None
) -> str:
    """One entry's answer control (contracts/page.md "Answer control"); ``answer`` is its stored answer."""
    from .reviews import entry_question

    off = " disabled" if disabled else ""
    k = esc(key)
    question = entry.question or entry_question(kind, entry)
    classes = "control" + (" answered" if answer else "")
    parts = [
        f'<div class="{classes}" data-entry="{k}" data-entry-hash="{esc(entry.hash)}" data-question="{esc(entry.question)}"'
        f' data-section="{esc(entry.section)}">',
        f'<p class="question">{esc(question)}</p>',
    ]
    if entry.why:
        parts.append(f'<p class="why">Why it is listed: {esc(entry.why)}</p>')
    if last:
        parts.append(f'<p class="last">Last answer: {esc(stored_text(last))}</p>')
    parts.append(
        f'<div class="stored"{"" if answer else " hidden"}><span class="stored-text">{esc(stored_text(answer)) if answer else ""}</span> '
        f'<button type="button" data-act="change" aria-label="Change the answer to {k}"{off}>Change</button></div>'
    )
    parts.append(
        f'<div class="buttons"{" hidden" if answer else ""}>'
        f'<button type="button" data-act="accept" aria-label="Accept {k}"{off}>Accept</button>'
        f'<button type="button" data-act="except" aria-label="Send back {k}"{off}>Send back</button>'
        f'<button type="button" data-act="question" aria-label="Question {k}"{off}>Question</button></div>'
    )
    parts.append(
        f'<div class="comment" hidden><label><span class="comment-label">Comment</span>'
        f'<textarea rows="3" aria-label="Comment on {k}"{off}></textarea></label>'
        f'<button type="button" data-act="send" aria-label="Send the answer to {k}"{off}>Send</button>'
        f'<button type="button" data-act="cancel">Cancel</button></div>'
    )
    parts.append('<p class="result" role="status"></p></div><!--/control-->')
    return "".join(parts)


@dataclass
class _Review:
    """What the page renders: the list, its answers, and what the person may do."""

    stage: str | None
    kind: str | None
    document: str | None
    listed: Any
    answers: dict[str, dict[str, Any]]
    last: dict[str, dict[str, Any]]
    disabled: bool
    notice: str


def _review_of(package: Any, config: Any, listed: Any = None, current: tuple[str, str] | None = None) -> _Review:
    from .reviews import current_review

    error = package.record_file().error
    if listed is not None and current is not None:
        stage, kind, document = current[0], current[1], current[0]
    else:
        found = current_review(package, config.one_at_a_time_max)
        stage, kind, document, listed = found["stage"], found["kind"], found["document"], found["list"]
    answers: dict[str, dict[str, Any]] = {}
    last: dict[str, dict[str, Any]] = {}
    if listed is not None:
        answers = {row["key"]: row for row in listed.answers or []}
        last = {row["key"]: row for row in listed.last_answers or []}
    notice = f"malformed-record-file: answers are refused until the record file is repaired: {error}" if error else ""
    return _Review(stage, kind, document, listed, answers, last, bool(error), notice)


def state_of(review: _Review, package: Any) -> dict[str, Any]:
    """``GET /state`` (D-68): the current review, the document's fingerprint, each listed entry's hash
    and each stored answer. The page compares two of these; it never changes what it shows."""
    current = None
    if review.stage is not None:
        current = {"stage": review.stage, "kind": review.kind, "label": stage_label(review.stage)}
    entries = {e.key: e.hash for e in review.listed.full} if review.listed is not None else {}
    answers = {key: [row["disposition"], row["by"], row["at"]] for key, row in review.answers.items()}
    doc = package.fingerprint(review.document) if review.document else None
    return {"current": current, "doc": doc, "entries": entries, "answers": answers}


def page_state(package: Any, config: Any) -> dict[str, Any]:
    return state_of(_review_of(package, config), package)


def _story_title(package: Any) -> str:
    from .overview import read_story

    return read_story(package)[0] or package.root.name


def _head(title: str, nonce: str, metas: dict[str, str]) -> str:
    tags = "".join(f'<meta name="{esc(name)}" content="{esc(value)}">' for name, value in metas.items())
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title>{tags}<style nonce=\"{esc(nonce)}\">{CSS}</style></head>"
    )


def message_page(text: str, nonce: str) -> str:
    """A short page with one message: never the token, never document text."""
    return _head("Review page", nonce, {}) + f'<body><main class="message"><p>{esc(text)}</p></main></body></html>\n'


def _segments(package: Any, stage: str) -> list[tuple[Any, list[str]]]:
    """The clean view of ``stage`` cut into runs of lines: one run per block (``(Block, lines)``), one
    per heading, and runs of other lines between them (``(None, lines)``)."""
    from .content import blocks_of
    from .show import view_lines

    doc = package.doc(stage)
    owner: dict[int, Any] = {}
    for block in blocks_of(doc):
        for number in range(block.first_line, block.last_line + 1):
            owner[number] = block
    out: list[tuple[Any, list[str], bool]] = []
    for number, text in view_lines(package, stage, doc, set(), set()):
        block = owner.get(number)
        heading = block is None and _SECTION_HEADING.match(text) is not None
        if out and block is not None and out[-1][0] is block:
            out[-1][1].append(text)
        elif out and block is None and not heading and out[-1][0] is None and not out[-1][2]:
            out[-1][1].append(text)
        else:
            out.append((block, [text], heading))
    return [(block, lines) for block, lines, _ in out]


def _document(package: Any, stage: str, review: _Review | None, ctx: RenderContext, comment: bool) -> tuple[str, set[str]]:
    """The document's HTML, block by block, with controls on ``review``'s entries. Returns the HTML and
    the keys it placed, so the entries left over go to the panels."""
    from .blockstatus import SETTLED, block_statuses

    statuses = block_statuses(package).get(stage, {})
    on_list = {e.key: e for e in (review.listed.full if review and review.listed is not None else [])} if review and review.stage == stage else {}
    groups = {e.key[1:].casefold(): e for e in on_list.values() if e.key.startswith("§") and e.members}
    member_of = {m: e.key for e in groups.values() for m in e.members}
    disabled = review.disabled if review else False
    placed: set[str] = set()
    out: list[str] = []
    for block, lines in _segments(package, stage):
        body = render_markdown("\n".join(lines), ctx)
        if block is None:
            if not body:
                continue
            out.append(body)
            title = _section_title(lines[0]) if len(lines) == 1 else None
            group = groups.get(title.casefold()) if title else None
            if group is not None and review is not None:
                placed.add(group.key)
                out.append(
                    f'<div class="section-entry listed"><p class="needs">Needs review: {esc(group.key)}</p>'
                    f'<p class="why">{esc(group.why)}</p>'
                    + _control(group.key, group, review.answers.get(group.key), review.last.get(group.key), disabled, review.kind)
                    + "</div>"
                )
            continue
        entry = on_list.get(block.key)
        info = statuses.get(block.key)
        classes = ["blk"]
        if entry is not None:
            classes.append("listed")
        elif block.key in member_of:
            classes.append("member")
        elif info is not None and info.status == SETTLED:
            classes.append("settled")
        head = f'<div class="{" ".join(classes)}" data-key="{esc(block.key)}" data-hash="{esc(block.hash)}"'
        if block.key in member_of:
            head += f' data-group="{esc(member_of[block.key])}"'
        parts = [head + ">"]
        if entry is not None:
            parts.append(f'<p class="needs">Needs review: {esc(block.key)}</p>')
        parts.append(body)
        if entry is not None and review is not None:
            placed.add(block.key)
            parts.append(_control(block.key, entry, review.answers.get(block.key), review.last.get(block.key), disabled, review.kind))
        elif comment and "settled" in classes:
            parts.append(_reopen_control(block.key, disabled))
        parts.append("</div>")
        out.append("".join(parts))
    return "\n".join(out), placed


def _reopen_control(key: str, disabled: bool) -> str:
    """Hook for US2: the Comment control on a settled block (none yet)."""
    return ""


def _panels(review: _Review, placed: set[str]) -> str:
    """Entries that are not blocks of the document: removed blocks, the legacy entry, and any other."""
    if review.listed is None:
        return ""
    left = [e for e in review.listed.full if e.key not in placed]
    removed = [e for e in left if e.why.startswith("removed")]
    legacy = [e for e in left if e.key.startswith("legacy:")]
    other = [e for e in left if e not in removed and e not in legacy]
    out = []
    for css, title, entries in (
        ("removed", "Removed since approval", removed),
        ("legacy", "Approved before section-level records", legacy),
        ("other", "Also on this list", other),
    ):
        if not entries:
            continue
        rows = [f'<section class="panel {css}" aria-label="{esc(title)}"><h2>{esc(title)}</h2>']
        for entry in entries:
            rows.append(
                f'<div class="blk listed panel-entry" data-key="{esc(entry.key)}" data-hash="{esc(entry.hash)}">'
                f'<p class="needs">Needs review: {esc(entry.key)}</p><div class="entry-text">{render_markdown(entry.what)}</div>'
                + _control(entry.key, entry, review.answers.get(entry.key), review.last.get(entry.key), review.disabled, review.kind)
                + "</div>"
            )
        rows.append("</section>")
        out.append("".join(rows))
    return "\n".join(out)


def review_page(package: Any, ctx: Any, nonce: str, listed: Any = None, current: tuple[str, str] | None = None) -> str:
    """``GET /``: the current review's document as a person reads it, with an answer control on exactly
    the entries ``review list`` returns (D-61, D-62). ``ctx`` gives ``name``, ``token`` and ``config``."""
    review = _review_of(package, ctx.config, listed, current)
    state = state_of(review, package)
    render_ctx = RenderContext()
    title = _story_title(package)
    if review.stage is not None:
        heading = f"{stage_label(review.stage)}: {LIST_LABELS.get(review.kind or '', review.kind or '')}"
    else:
        heading = f"{stage_label(review.document)}: no review is current" if review.document else "No review is current"
    total = len(review.listed.full) if review.listed is not None else 0
    answered = len(review.answers)
    document, placed = ("", set())
    if review.document:
        document, placed = _document(package, review.document, review, render_ctx, comment=review.stage is not None)
    metas = {"eil-token": ctx.token, "eil-state": json.dumps(state, sort_keys=True)}
    body = [
        f'<body><header class="top" data-stage="{esc(review.stage or "")}" data-kind="{esc(review.kind or "")}">',
        f'<p class="story">{esc(title)}</p><h1>{esc(heading)}</h1>',
        f'<p class="meta"><span id="counter" data-total="{total}" data-answered="{answered}">{answered} of {total} answered</span>'
        f' · Answering as <span id="name">{esc(ctx.name)}</span> '
        '<button type="button" data-act="change-name" aria-controls="name-form">Change</button>'
        " · <kbd>n</kbd> moves to the next unanswered block</p>",
        '<form id="name-form" hidden><label>Your name <input id="name-input" autocomplete="name"></label>'
        '<button type="submit">Save</button><button type="button" data-act="cancel-name">Cancel</button>'
        '<span class="result" role="status"></span></form></header>',
        f'<div id="notice" class="notice" role="status" aria-live="polite"{"" if review.notice else " hidden"}>{esc(review.notice)}</div>',
        _panels(review, placed) if review.stage is not None else "",
        f'<main id="doc">{document}</main>',
        f'<footer id="footer"><p>{esc(footer_text(review.listed))}</p></footer>',
        f'<script nonce="{esc(nonce)}">{SCRIPT}</script></body></html>\n',
    ]
    return _head(f"Review: {title}", nonce, metas) + "".join(body)


def document_page(package: Any, stage: str, ctx: Any, nonce: str) -> str:
    """``GET /doc/<stage>``: another stage's document, read-only."""
    title = _story_title(package)
    document, _ = _document(package, stage, None, RenderContext(), comment=False)
    body = (
        f'<body><header class="top" data-stage="" data-kind=""><p class="story">{esc(title)}</p>'
        f"<h1>{esc(stage_label(stage))} (read-only)</h1></header>"
        f'<main id="doc">{document}</main></body></html>\n'
    )
    return _head(f"{stage_label(stage)}: {title}", nonce, {}) + body


CSS = """
:root{--fg:#1d1d1f;--bg:#fff;--muted:#5f6368;--line:#d0d4d9;--listed:#fff8e1;--listed-edge:#e0a800;--ok:#e6f4ea;--panel:#f6f7f9;--notice:#fde8e8}
@media (prefers-color-scheme:dark){:root{--fg:#e8eaed;--bg:#16181b;--muted:#a0a4a8;--line:#3c4043;--listed:#2b2614;--listed-edge:#c79500;--ok:#17301f;--panel:#202327;--notice:#3a1d1d}}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg);margin:0 auto;max-width:56rem;padding:0 1rem 4rem;line-height:1.55}
header.top{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:.6rem 0;z-index:2}
header.top h1{font-size:1.15rem;margin:.1rem 0}.story{margin:0;color:var(--muted);font-size:.9rem}.meta{margin:.2rem 0 0;font-size:.92rem}
.notice{position:sticky;top:5.5rem;background:var(--notice);border:1px solid var(--line);padding:.5rem .75rem;margin:.5rem 0;z-index:1}
.notice button{margin-left:.75rem}
main#doc h1{font-size:1.4rem}main#doc h2{font-size:1.2rem;margin-top:2rem}
.blk{margin:.4rem 0;padding:.1rem .6rem;border-left:4px solid transparent}
.blk.listed,.section-entry{background:var(--listed);border-left-color:var(--listed-edge);padding:.5rem .75rem}
.blk.member{border-left:4px dashed var(--listed-edge)}
.needs{font-size:.8rem;font-weight:600;margin:0 0 .2rem;color:var(--muted)}
.control{border-top:1px solid var(--line);margin-top:.5rem;padding-top:.5rem}
.control.answered{background:var(--ok);padding:.5rem}
.question{font-weight:600;margin:.2rem 0}.why,.last{font-size:.9rem;color:var(--muted);margin:.2rem 0}
.buttons button,.comment button,.stored button{margin:.2rem .4rem .2rem 0}
button{font:inherit;padding:.3rem .8rem;border:1px solid var(--line);border-radius:.3rem;background:var(--bg);color:var(--fg);cursor:pointer}
button:focus-visible,textarea:focus-visible,input:focus-visible{outline:3px solid var(--listed-edge);outline-offset:2px}
button[disabled]{opacity:.5;cursor:not-allowed}
textarea{width:100%;font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);margin:.3rem 0}
.comment-label{display:block;font-size:.9rem}
.result{white-space:pre-wrap;color:#b3261e;margin:.2rem 0}
.changed{border:1px dashed #b3261e;padding:.4rem;margin:.4rem 0}.changed pre{white-space:pre-wrap}
.panel{background:var(--panel);border:1px solid var(--line);padding:.5rem 1rem;margin:1rem 0}
pre{overflow:auto;background:var(--panel);padding:.5rem}table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:.2rem .5rem}
.diagram{margin:.5rem 0}.diagram-credit{font-size:.85rem;color:var(--muted)}
.ref{text-decoration:underline dotted}.ref-error{color:#b3261e;text-decoration:underline wavy}
.preview{position:absolute;max-width:32rem;background:var(--bg);border:1px solid var(--line);padding:.5rem;box-shadow:0 2px 8px rgba(0,0,0,.2);z-index:3}
kbd{border:1px solid var(--line);border-radius:.2rem;padding:0 .3rem}
footer{margin-top:2rem;font-weight:600}
"""

# The page's one script. It renders, polls and sends; every decision is the helper's (constitution
# 1.3.0). It reads values only as text (``textContent``), never as HTML, except a diagram the project's
# own diagram script drew.
SCRIPT = r"""
(() => {
  "use strict";
  const NONCE = document.currentScript ? document.currentScript.nonce : "";
  const meta = (name) => { const el = document.querySelector('meta[name="' + name + '"]'); return el ? el.getAttribute("content") : null; };
  const TOKEN = meta("eil-token");
  let baseline = JSON.parse(meta("eil-state") || "{}");
  const top = document.querySelector("header.top");
  const STAGE = top ? top.dataset.stage : "";
  const KIND = top ? top.dataset.kind : "";
  const notice = document.getElementById("notice");
  const counter = document.getElementById("counter");
  const footer = document.getElementById("footer");
  const DONE = {accept: "Accepted", except: "Sent back", question: "Questioned"};
  let stopped = false;

  function showNotice(text, reload) {
    if (!notice) return;
    notice.textContent = "";
    const line = document.createElement("span");
    line.textContent = text;
    notice.appendChild(line);
    if (reload) {
      const button = document.createElement("button");
      button.type = "button"; button.dataset.act = "reload"; button.textContent = "Reload";
      notice.appendChild(button);
    }
    notice.hidden = false;
  }
  function pageStopped() { stopped = true; showNotice(__STOPPED__, false); }

  async function post(path, body) {
    try {
      const response = await fetch(path, {method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-EIL-Token": TOKEN}, body: JSON.stringify(body)});
      return await response.json();
    } catch (error) { pageStopped(); return null; }
  }
  function refusalText(result) {
    if (!result) return "";
    if (result.refusals) return result.refusals.map((r) => r.message + (r.fix ? " (" + r.fix + ")" : "")).join("\n");
    return result.error || "Not stored.";
  }
  function storedText(disposition, by, comment, together) {
    let line = (DONE[disposition] || "Answered") + " by " + by + " just now";
    if (together) line += ", with the rest of " + together;
    return line + (comment ? ": " + comment : ".");
  }
  function adopt(result) { if (result && result.state) baseline = result.state; }
  function updateCounter(result) {
    if (!counter || !result) return;
    const total = Number(counter.dataset.total);
    const answered = result.closed ? total : result.answered;
    if (typeof answered === "number") counter.textContent = answered + " of " + total + " answered";
    if (footer && (result.closed || (Array.isArray(result.remaining) && result.remaining.length === 0))) {
      footer.textContent = __COMPLETE__;
    }
  }
  function busy(scope, on) { scope.querySelectorAll("button, textarea").forEach((el) => { if (on) el.dataset.wasDisabled = el.disabled ? "1" : ""; el.disabled = on || el.dataset.wasDisabled === "1"; }); }
  function name() { const el = document.getElementById("name"); return el ? el.textContent : ""; }

  function markAnswered(control, disposition, comment, together) {
    control.classList.add("answered");
    control.querySelector(".stored-text").textContent = storedText(disposition, name(), comment, together);
    control.querySelector(".stored").hidden = false;
    control.querySelector(".buttons").hidden = true;
    control.querySelector(".comment").hidden = true;
    control.querySelector(".result").textContent = "";
  }
  function showChanged(control, current) {
    let box = control.querySelector(".changed");
    if (!box) {
      box = document.createElement("div"); box.className = "changed";
      const said = document.createElement("p"); said.textContent = __CHANGED__;
      const text = document.createElement("pre");
      box.appendChild(said); box.appendChild(text);
      control.insertBefore(box, control.querySelector(".buttons"));
    }
    box.querySelector("pre").textContent = current.what;
    control.dataset.entryHash = current.hash;
  }

  async function answer(control, disposition, comment) {
    const body = {stage: STAGE, kind: KIND, entry: control.dataset.entry, disposition: disposition,
      shown: control.dataset.entryHash, question: control.dataset.question, comment: comment};
    busy(control, true);
    const result = await post("/answer", body);
    busy(control, false);
    if (!result) return;
    if (result.ok) { markAnswered(control, disposition, comment); updateCounter(result); adopt(result); return; }
    control.querySelector(".result").textContent = refusalText(result);
    const changed = (result.refusals || []).find((r) => r.code === "entry-changed" && r.current);
    if (changed) showChanged(control, changed.current);
  }

  function openComment(scope, act, label) {
    const box = scope.querySelector(".comment");
    scope.dataset.pending = act;
    box.querySelector(".comment-label").textContent = label;
    box.hidden = false;
    box.querySelector("textarea").focus();
  }
  const LABELS = {except: "Send back: what should change?", question: "Question: what do you want to know?",
    reopen: "Send this block back for review with your comment"};

  async function onControl(control, act) {
    if (act === "accept") return answer(control, "accept", null);
    if (act === "except" || act === "question") return openComment(control, act, LABELS[act]);
    if (act === "cancel") { control.querySelector(".comment").hidden = true; return; }
    if (act === "change") { control.querySelector(".buttons").hidden = false; control.querySelector(".stored").hidden = true; return; }
    if (act === "send") {
      const text = control.querySelector("textarea").value;
      if (!text.trim()) { control.querySelector(".result").textContent = "Write a comment first; it is sent with your answer."; return; }
      return answer(control, control.dataset.pending, text);
    }
  }

  async function onReopen(block, act) {
    if (act === "comment") return openComment(block, "reopen", LABELS.reopen);
    if (act === "cancel") { block.querySelector(".comment").hidden = true; return; }
    if (act !== "send") return;
    const text = block.querySelector("textarea").value;
    const result_ = block.querySelector(".result");
    if (!text.trim()) { result_.textContent = "Write a comment first; it is sent with the block."; return; }
    busy(block, true);
    const result = await post("/reopen", {stage: STAGE, key: block.dataset.key, shown: block.dataset.hash, comment: text});
    busy(block, false);
    if (!result) return;
    if (!result.ok) { result_.textContent = refusalText(result); return; }
    block.querySelector(".reopen").textContent = "Reopened by " + name() + ": " + text + " (reload to answer it here)";
    adopt(result);
  }

  async function onSection(button) {
    if (!button.dataset.armed) {
      button.dataset.armed = "1";
      button.dataset.label = button.textContent;
      button.textContent = "Accept the " + button.dataset.count + " unanswered blocks under " + button.dataset.section + "?";
      return;
    }
    delete button.dataset.armed;
    busy(button.parentElement, true);
    const result = await post("/section", {stage: STAGE, kind: KIND, section: button.dataset.section});
    busy(button.parentElement, false);
    button.textContent = button.dataset.label;
    if (!result) return;
    if (!result.ok) { button.parentElement.querySelector(".result").textContent = refusalText(result); return; }
    document.querySelectorAll(".control:not(.answered)").forEach((control) => {
      if (control.dataset.section === button.dataset.section) markAnswered(control, "accept", null, button.dataset.section);
    });
    button.hidden = true;
    updateCounter(result);
    adopt(result);
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || button.disabled) return;
    const act = button.dataset.act;
    if (act === "reload") return location.reload();
    if (act === "change-name") { const form = document.getElementById("name-form"); form.hidden = false; const input = document.getElementById("name-input"); input.value = name(); input.focus(); return; }
    if (act === "cancel-name") { document.getElementById("name-form").hidden = true; return; }
    if (act === "section") return onSection(button);
    const control = button.closest(".control");
    if (control) return onControl(control, act);
    const block = button.closest(".blk");
    if (block) return onReopen(block, act);
  });

  const form = document.getElementById("name-form");
  if (form) form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await post("/name", {name: document.getElementById("name-input").value});
    if (!result) return;
    if (result.ok) { document.getElementById("name").textContent = result.name; form.hidden = true; form.querySelector(".result").textContent = ""; }
    else form.querySelector(".result").textContent = refusalText(result);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "n" || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target;
    if (target && (target.tagName === "TEXTAREA" || target.tagName === "INPUT")) return;
    const open = Array.from(document.querySelectorAll(".control:not(.answered)"));
    if (!open.length) return;
    const here = document.activeElement ? document.activeElement.closest(".control") : null;
    const next = here && open.indexOf(here) >= 0 ? open[(open.indexOf(here) + 1) % open.length] : open[0];
    const button = next.querySelector(".buttons button");
    if (button) { button.focus(); button.scrollIntoView({block: "center"}); event.preventDefault(); }
  });

  function differences(now) {
    const key = (s) => (s && s.current ? s.current.stage + "/" + s.current.kind : "");
    if (key(now) !== key(baseline)) return [now.current ? "A new review is current: " + now.current.label : "No review is current now"];
    const out = [];
    const before = baseline.entries || {}, after = now.entries || {};
    const answersBefore = baseline.answers || {}, answersAfter = now.answers || {};
    Object.keys(before).forEach((k) => {
      if (k in after && after[k] !== before[k]) out.push(k + " changed");
      else if (!(k in after)) out.push(k + " was answered elsewhere");
    });
    Object.keys(after).forEach((k) => { if (!(k in before)) out.push(k + " is now on the list"); });
    Object.keys(answersAfter).forEach((k) => {
      if (JSON.stringify(answersAfter[k]) !== JSON.stringify(answersBefore[k]) && !out.includes(k + " changed")) out.push(k + " was answered elsewhere");
    });
    if (!out.length && now.doc !== baseline.doc) out.push("The document changed outside the review blocks");
    return out;
  }
  async function poll() {
    if (stopped) return;
    try {
      const response = await fetch("/state", {headers: {"X-EIL-Token": TOKEN}, credentials: "same-origin"});
      if (!response.ok) throw new Error(String(response.status));
      const found = differences(await response.json());
      if (found.length) showNotice(found.join("; "), true);
    } catch (error) { pageStopped(); return; }
    setTimeout(poll, __POLL_MS__);
  }
  if (TOKEN && top && top.dataset.stage !== undefined && baseline) setTimeout(poll, __POLL_MS__);

  const diagrams = meta("eil-diagram-script");
  if (diagrams) {
    import(diagrams).then((module) => {
      const mermaid = module.default || module;
      mermaid.initialize({startOnLoad: false, securityLevel: "strict"});
      document.querySelectorAll("pre.mermaid-src").forEach((source, index) => {
        const drawn = document.createElement("div");
        drawn.className = "diagram";
        source.after(drawn);
        mermaid.render("eil-diagram-" + index, source.textContent).then((out) => {
          drawn.innerHTML = out.svg.replace(/<style/g, '<style nonce="' + NONCE + '"');
        }).catch(() => { drawn.textContent = "This diagram could not be drawn; its source is shown above."; });
      });
    }).catch(() => {
      document.querySelectorAll(".diagram-credit").forEach((el) => { el.textContent += " (the script could not be loaded; sources are shown)"; });
    });
  }
})();
""".replace("__POLL_MS__", str(POLL_MS)).replace("__STOPPED__", json.dumps(STOPPED)).replace(
    "__COMPLETE__", json.dumps(COMPLETE)
).replace("__CHANGED__", json.dumps(CHANGED))

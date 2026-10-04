# Page contract: Browser Review Page

This contract covers what the person sees and can do on the page. The routes behind it are in [cli.md](cli.md). Its script presents and sends; it decides nothing and writes nothing (constitution 1.3.0, Principle I).

## Layout, top to bottom

1. **Header**:
   - the story;
   - the stage and list ("Functional Specification: blocks that need review", or "...: changes since approval");
   - the counter "N of M answered";
   - "Answering as NAME", with a Change button that opens a one-field form posting to `/name`.
2. **Notice bar**, empty until the state check finds a change (research D-68). It holds one line naming what changed and a Reload button. It is announced to screen readers (`role="status"`).
3. **Panels**, when present: "Removed since approval" (one control per removed entry) and the legacy statement (one control).
4. **The document**, rendered. Each listed block is highlighted and followed by its answer control. Every other block is shown as settled: plain, with a small "Comment" button.
5. **Footer**:
   - when nothing remains: "List complete. Return to the chat and say done.";
   - when nothing is listed: "Nothing to answer now."

## Answer control (one per listed entry)

- The entry's fixed question (D-64), as text.
- Three buttons: **Accept**, **Send back**, **Question**.
  - Send back and Question open a comment box. The answer is sent only when the comment is not empty.
- After a stored answer: the disposition, the name and the time. A Change button answers again, storing a new answer as in chat.
- After a refusal: the helper's message and fix, verbatim, as text. For `entry-changed`, the current text replaces the shown text in this control only, with "This block changed; read it again before answering". The rest of the page stays as loaded.
- Section headings with unanswered entries carry **Accept the rest of this section**. It asks "Accept the N unanswered blocks under SECTION?" and needs a second click to confirm.

## Comment on a settled block

The Comment button opens a comment box with the label "Send this block back for review with your comment". The comment cannot be empty. After it is stored, the block shows "Reopened by NAME". It is not answerable on the page until a reload lists it.

The Comment button appears only on settled blocks of the stage under review. Other stages' documents (`/doc/<stage>`) are read-only. When no review is current, comments are given in chat (spec FR-016).

## References and diagrams

- A reference code is a link to the defining block. Hover or keyboard focus shows that block's text in a popup. An unresolved or duplicate code carries the error mark and a title saying which.
- A diagram is shown as source. With `review.diagram_script`, it is also drawn beside its source, and the first diagram carries "Diagrams drawn by URL".

## Accessibility and keyboard

Deferred from clarification to this contract:
- Every control is a native `button`, `textarea` or `a`, reachable with Tab in document order and labelled with the entry key.
- "Next unanswered" (`n`) moves focus to the next answer control. It is listed in the header.
- Colour is never the only marker: highlighted blocks also carry the text "Needs review: KEY".
- No timeout acts on the person's behalf. The idle stop only ends the server. When a state check or an answer then fails to connect, the notice bar shows "The review page has stopped; ask the agent to start it again".

## Performance

The page for the 002 performance fixture's largest stage (about 100 KB) is rendered by the helper in under 1 second. The unit test sits beside `tests/unit/test_performance.py`.

# Constitution PATCH 1.2.2: draft for `/speckit-constitution`

**Status**: Applied 2026-10-02 with `/speckit-constitution` (task T098), with one narrowing made on application: the question MUST be recorded "when the reply does not itself say what it confirms", so sentence-style approvals recorded without a question stay compliant. `.specify/memory/constitution.md` holds the final wording.

**Why**: `specs/003-proportionate-effort` FR-047 to FR-049 (change 10) accept a one-word reply such as "ok" to the helper's explicit approval question as a complete approval. Principle II's second paragraph allows a short acknowledgement "when, and only when" every change since an approval is covered by recorded decisions. Read literally, that limits short replies to carry-forward. This PATCH clarifies the scope of that clause. No principle's intent changes, and no compliant practice becomes non-compliant.

**Version**: 1.2.1 → 1.2.2 (PATCH: clarification).

## Change to Principle II

Insert this paragraph **before** the paragraph that begins "A human confirmation MAY be a short acknowledgement":

> A human confirmation is the person's reply to an explicit question that states what is being confirmed (for example "Approve the Functional Specification as the behaviour you require?"). The reply MAY be as short as "ok", "yes" or "approved": the question carries the content, and it MUST be recorded with the reply so that a reader sees what was confirmed. The question is fixed by the helper, never worded by the AI.

Then change the opening of the existing paragraph from:

> A human confirmation MAY be a short acknowledgement (for example "ok") of an explanation the helper generates, when, and only when, every change since an approval is covered by recorded human decisions that the helper has verified.

to:

> An approval MAY also be carried forward, with no fresh approval question, on a short acknowledgement (for example "ok") of an explanation the helper generates, when, and only when, every change since that approval is covered by recorded human decisions that the helper has verified.

The rest of that paragraph is unchanged: verbatim, with name and time, from a configured confirmer, never supplied by the AI, and marked as carried forward.

## Sync Impact Report entry

```text
Version change: 1.2.1 -> 1.2.2 (2026-10-02)
1.2.2 (PATCH): Principle II clarified. A short reply ("ok") to an explicit approval question
  is an ordinary confirmation, recorded with the helper's fixed question. The "short
  acknowledgement ... when, and only when" clause governs approvals carried forward with no
  fresh question. Enables specs/003-proportionate-effort FR-047 to FR-049. Nothing compliant
  with 1.2.1 becomes non-compliant.
Modified principles: II (scope of the short-acknowledgement clause made explicit)
Follow-up: none; 003 records the question beside every approval reply (D-59).
Templates reviewed: none modified (dependent commands read this file at runtime)
```

Also update the footer's **Version** to 1.2.2 and **Last Amended** to the date applied.

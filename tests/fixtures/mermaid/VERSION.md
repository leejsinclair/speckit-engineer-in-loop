# Mermaid fixtures

The `*.docs.mmd` files are taken verbatim from the Mermaid documentation source
(`packages/mermaid/src/docs/syntax/{c4,sequenceDiagram,entityRelationshipDiagram}.md`, branch
`develop`), fetched on 2026-09-25 when the latest published Mermaid release was **12.0.0**
(`npm view mermaid version`).

The `*.malformed.mmd` and `*.borderline.mmd` files are hand-written for this repository.

## What these fixtures do and do not prove

They pin what `eil`'s line-oriented parser accepts and rejects. They have **not** been rendered:
nothing here proves that Mermaid itself accepts them, and nothing here proves that a future Mermaid
still does (risk R-10; Mermaid C4 is documented as experimental). Rendering validity is out of the
helper's reach by design (research D-21); a team may add `mmdc` in CI.

## Updating

When the Mermaid documentation adds or changes a construct, add a `*.docs.mmd` example, extend the
subset table in `specs/001-staged-definition-workflow/contracts/document-format.md` and
`extensions/eil/scripts/python/eil/diagrams.py` together, and update the date and version above.

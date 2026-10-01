## What this changes

<!-- One or two sentences. -->

## Constitution checklist

Governing document: `.specify/memory/constitution.md`.

- [ ] **Principles touched**: list which of I (enforcement lives in the helper), II (honest attestation limits), III (test-first, no runtime dependencies) and IV (proportionate ceremony) this change touches, or write "none".
- [ ] **Principle I, tier 1**: no gate, refusal or record exists only in a prompt. Every gate, refusal, approval, fingerprint, alias, artifact check and comprehension record is deterministic `eil` helper code with a unit test.
- [ ] **Principle I, tier 2**: for each new behavioural rule added to a prompt, name the contract test (`tests/contract/test_prompt_guidance.py` entry) or the trial probe (`docs/trials.md`) that covers it:
  - <!-- rule → test or probe, or "no new prompt rules" -->
- [ ] **Principle II**: nothing in this change describes a gate as tamper-proof, and any new limit is stated where the feature is documented.
- [ ] **Principle III**: the new tests were seen to fail before the code that satisfies them, and no runtime dependency was added.
- [ ] **Contracts**: a change to `specs/**/contracts/*.md` lands in this pull request together with the tests that pin it.
- [ ] **Principle IV**: name each human interaction this change adds or removes, with its purpose (awareness, understanding, decision, validation or approval), or write "none". No person is asked to reconfirm what is already established, and nothing removed was a decision, approval or risk acceptance.
  - <!-- interaction → added or removed, and its purpose; or "none" -->

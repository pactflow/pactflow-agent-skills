# {{title: 3a. Design — Knowledge ramp-up ({{team}})}}

## Why this phase

Before writing the first contract test, {{team}} needs enough shared mental model of contract testing that conversations don't stall on terminology. This is a pure learning task — no code yet — modelled on the structure that has worked for prior teams adopting Pact / PactFlow / Drift.

## What to do

- Skim the **Pact docs** (you do not need to read everything — focus on the "Getting Started" + "Pact Nirvana" sections).
- Watch **one or two intro videos** on consumer-driven contract testing.
- Skim the **PactFlow product docs**, focused on the broker concepts (pacticipants, environments, deployments) and `can-i-deploy`.
- (If BDCT or Both) Skim the **Drift docs** and **Bi-Directional Contract Testing guide** — these come into play in Phase 4b.
- Clone a reference **example repo** in {{stack}} (link below) and run its tests locally — even a 5-minute roundtrip helps the concepts land.

## Acceptance criteria

- Every engineer assigned to Phases 4 / 4b can articulate the difference between a consumer test, a provider verification, and a pact in 1–2 sentences.
- (BDCT / Both) Every engineer assigned to Phase 4b can articulate what Drift verifies and how it differs from a Pact provider verification.
- A short summary or comment on this ticket lists which materials were consumed and any gaps to follow up on.

## References

- [Pact docs (start here)](https://docs.pact.io)
- [Pact Nirvana — the maturity ladder](https://docs.pact.io/pact_nirvana)
- [Pact implementation guides (per language)](https://docs.pact.io/implementation_guides)
- [{{pact_library}}]({{pact_library_url}})
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Foundation GitHub org (sample apps)](https://github.com/pact-foundation)
- (BDCT / Both) [Drift docs](https://pactflow.github.io)
- (BDCT / Both) [BDCT guide](https://docs.pactflow.io/docs/bi-directional-contract-testing)
- (BDCT / Both) [BDCT OpenAPI examples](https://github.com/pactflow/bdct-oas-examples)

---
*If you're using Claude Code: `swagger-contract-testing:pactflow` skill answers conceptual questions and walks through Pact / PactFlow flows.*

# {{title: 1. Planning — agree scope, versioning, environments ({{team}})}}

## Why this phase

Contract testing only delivers value when both sides of an integration agree on what they're contracting about. Before a single Pact test gets written, {{team}} needs a shared picture of which systems are in scope, which integrations have caused breaking changes recently, and how versioning + environments will be named in the broker. Skipping this conversation is the most common cause of stalled rollouts.

## What to do

- Run a 30-60 minute working session with {{team}} and the owners of {{consumer}} and {{provider}}.
- List recent breaking changes between {{consumer}} and {{provider}} (or any integration partner — even if it's not the chosen pair, the patterns are informative).
- Confirm {{consumer}} ↔ {{provider}} is the right first pair: highest pain, most frequent integration, or most blocked by manual coordination.
- Agree the naming convention for **pacticipant versions** (recommended: git SHA, optionally suffixed with a build number).
- Agree the **environment names** that will appear in the broker matrix (e.g. `test`, `staging`, `production`).
- Identify who owns release decisions on each side (used in Phase 6 when `can-i-deploy` blocks a merge).

## Acceptance criteria

- A 1-page planning doc exists in the team's docs repo (or wiki) capturing: chosen consumer/provider pair, version-naming convention, environment names, and the recent-breaking-change history that motivated the choice.
- The doc is linked from this ticket.
- Both sides' release owners are named in the doc.

## References

- [Pact Nirvana — maturity ladder (start with Cloning + Versioning levels)](https://docs.pact.io/pact_nirvana)
- [Versioning in the Pact Broker](https://docs.pact.io/getting_started/versioning_in_the_pact_broker)
- [Environments in PactFlow](https://docs.pactflow.io/docs/permissions/environments)

---
*If you're using Claude Code: `/swagger-contract-testing` can help shape the planning doc; `smartbear-mcp` provides PactFlow context if you need to inspect existing pacticipants.*

# Contract testing context — CDCT consumer

This is the **consumer side** of a Pact integration with `{{provider}}`. Pact tests live in `pact/` alongside this repo's existing tests. The published pact file is the source of truth for what `{{consumer}}` expects from `{{provider}}`.

## Stack

- Language / framework: `{{stack}}`
- Pact library: [`{{pact_library}}`]({{pact_library_url}})
- Broker: `{{broker_url_or_phrase}}`
- CI: `{{ci_tool}}`

## Skills and tools Claude Code should prefer here

- `/swagger-contract-testing` — end-to-end help authoring tests.
- `swagger-contract-testing:pact-generator` — scaffold Pact tests from existing client code or examples.
- `swagger-contract-testing:pact-reviewer` — audit existing tests for false positives, naming, and best-practice violations.
- `swagger-contract-testing:pactflow` — publish, can-i-deploy, matrix queries.
- `smartbear-mcp` — AI-assisted test generation and PactFlow operations.

## House rules

- Every new API call from `{{consumer}}` to `{{provider}}` gets a Pact interaction. Extend the existing test file for that provider endpoint; do not scatter tests across files.
- Provider states follow the convention `"<resource> exists with <condition>"` (lower-case, present tense). Check what `{{provider}}` already supports before inventing a new one.
- Run the Pact suite locally before opening a PR. CI runs it too, but treat CI as a backstop, not the primary check.
- On merge to `main`, CI publishes the pact to `{{broker_url_or_phrase}}` with consumer version = git SHA. Do not publish manually.

## References

- [Pact docs](https://docs.pact.io)
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Nirvana](https://docs.pact.io/pact_nirvana)
- [{{pact_library}}]({{pact_library_url}})

# Contract testing context — CDCT provider

This is the **provider side** of a Pact integration with `{{consumer}}`. The pact published by `{{consumer}}` is the source of truth for what it expects from this service. A provider verification harness pulls the latest pact from `{{broker_url_or_phrase}}` and runs it against this service's real implementation.

## Stack

- Language / framework: `{{stack}}`
- Pact library: [`{{pact_library}}`]({{pact_library_url}})
- Broker: `{{broker_url_or_phrase}}`
- CI: `{{ci_tool}}`

## Skills and tools Claude Code should prefer here

- `/swagger-contract-testing` — end-to-end help with provider verification.
- `swagger-contract-testing:pact-reviewer` — audit the verification harness and provider states for false positives, naming, and best-practice violations.
- `swagger-contract-testing:pactflow` — pull the latest pact, publish verification results, run can-i-deploy, inspect the matrix.
- `smartbear-mcp` — AI-assisted PactFlow operations.

## House rules

- Provider states follow the convention `"<resource> exists with <condition>"` (lower-case, present tense). Reuse an existing state before inventing a new one — check what `{{consumer}}` already expects.
- The verification harness pulls the latest pact for `{{consumer}}` from `{{broker_url_or_phrase}}` and runs it against a locally-running instance of this service — never against a mocked version of this service's own code.
- Run the verification suite locally before opening a PR. CI runs it too, but treat CI as a backstop, not the primary check.
- On every PR, `{{ci_tool}}` runs verification and publishes the result back to `{{broker_url_or_phrase}}`, tagged with the provider version (git SHA). Do not publish results manually.
- A failing verification blocks the PR — do not relax or skip a pact interaction to make the build pass. Fix the implementation, or take it up with `{{consumer}}`'s owners if the expectation itself is wrong.

## References

- [Pact docs](https://docs.pact.io)
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Nirvana](https://docs.pact.io/pact_nirvana)
- [{{pact_library}}]({{pact_library_url}})

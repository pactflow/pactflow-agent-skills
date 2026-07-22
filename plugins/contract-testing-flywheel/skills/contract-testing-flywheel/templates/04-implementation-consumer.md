# {{title: 4. Consumer-side contract tests ({{consumer}} → {{provider}})}}

## Why this phase

This is {{team}}'s first piece of *production* contract testing. {{consumer}} records what it expects from {{provider}} as executable tests; those tests produce a pact file; the pact file is published to {{broker_url_or_phrase}}. From this point on, breaking changes to {{provider}} that {{consumer}} depends on get caught before they reach production.

## Where the consumer tests live

Inside the {{consumer}} repository, alongside its existing unit and integration tests. Pact tests exercise {{consumer}}'s real HTTP client, so colocation keeps the client and its contract expectations in one PR, lets the pact file fall out as a build artefact of {{consumer}}'s own test suite, and — for BDCT — lets the contract record from real request/response traffic during {{consumer}}'s tests.

This matches every official Pact workshop and reference repo (`pactflow-example-consumer-*`).

## What to do

<!-- BEGIN CDCT -->
- Add a `pact/` test directory inside {{consumer}}, next to its existing tests.
- Set up {{pact_library}} (see {{pact_library_url}}).
- Write consumer tests that define each expected interaction with {{provider}} chosen in Phase 1.
- Run the suite to generate the pact file.
- Configure publishing to {{broker_url_or_phrase}}. Consumer version tag = git SHA.
- Add a {{ci_tool}} step to {{consumer}}'s existing pipeline that runs the tests on PRs and publishes the pact on merge to main.
- Route publish failures to the team's notification channel.
<!-- END CDCT -->

<!-- BEGIN BDCT -->
- Add a `pact/` test directory inside {{consumer}}, next to its existing tests.
- Wire {{consumer}}'s existing API client (against {{provider}}) to record its real request/response interactions during the consumer test run.
- Run the suite to generate the consumer contract.
- Configure publishing to {{broker_url_or_phrase}} via PactFlow's BDCT consumer-contract flow. Consumer version tag = git SHA.
- Add a {{ci_tool}} step to {{consumer}}'s existing pipeline that runs the tests on PRs and publishes the contract on merge to main.
- Route publish failures to the team's notification channel.
<!-- END BDCT -->

## Acceptance criteria

- Pact tests live in a `pact/` directory inside the {{consumer}} repository.
- {{pact_library}} is set up (CDCT) — or BDCT consumer-contract recording is configured (BDCT) — and produces a contract file on a local run.
- {{ci_tool}} runs the tests on every PR and publishes on merge to main; the publish step is visible in the pipeline.
- Publish failures notify the team's chosen channel.
- `CLAUDE.md` from the plugin's `examples/CLAUDE.md.cdct-consumer.md` (or the BDCT-flavoured equivalent) is copied into {{consumer}} with placeholders filled in.
- The first published contract appears in {{broker_url_or_phrase}}'s matrix for {{consumer}} ↔ {{provider}}.

## References

- [Pact docs](https://docs.pact.io)
- [{{pact_library}}]({{pact_library_url}})
- [pactflow-example-consumer-js (colocated reference)](https://github.com/pactflow/example-consumer-js)
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Nirvana](https://docs.pact.io/pact_nirvana)
- (BDCT / Both) [BDCT guide](https://docs.pactflow.io/docs/bi-directional-contract-testing)
- (BDCT / Both) [BDCT OpenAPI examples](https://github.com/pactflow/bdct-oas-examples)

---
*If you're using Claude Code:*
- *`/swagger-contract-testing` — end-to-end help authoring tests.*
- *`swagger-contract-testing:pact-generator` skill — scaffold tests from existing client code.*
- *`swagger-contract-testing:pact-reviewer` skill — audit tests for false positives, naming, and best-practice violations.*
- *`swagger-contract-testing:pactflow` skill — publish, can-i-deploy, matrix.*
- *`smartbear-mcp` server — AI-assisted test generation and PactFlow operations.*
- *Drop `examples/CLAUDE.md.cdct-consumer.md` from this plugin into {{consumer}}'s root.*

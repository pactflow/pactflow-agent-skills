# {{title: 4b. Provider-side verification ({{provider}} ← {{consumer}})}}

## Why this phase

{{provider}} now needs to prove it actually meets the expectations that {{consumer}} published in Phase 4. This is the other half of the contract: a verification harness that pulls the published contract from {{broker_url_or_phrase}}, runs it against {{provider}}'s implementation (or its authoritative OpenAPI spec, for BDCT), and reports a pass/fail.

## What to do

<!-- BEGIN CDCT -->
- In {{provider}}'s repository, add a Pact provider verification harness using {{pact_library}}.
- Implement **provider states** for any consumer expectations that need specific fixture data (use the convention `"<resource> exists with <condition>"`, lower-case + present tense).
- Configure the harness to pull the latest pact for {{consumer}} from {{broker_url_or_phrase}} and verify it against a locally-running {{provider}}.
- Hook the verification into the team's {{ci_tool}} pipeline: run on PRs, publish results back to the broker tagged with the provider version (git SHA).
- Wire failure notifications into the team's notification channel of choice.
<!-- END CDCT -->

<!-- BEGIN BDCT -->
- Treat {{provider}}'s OpenAPI spec (at `{{openapi_path}}`) as the **authoritative source of truth** for its API surface.
- Install the **Drift CLI** (https://pactflow.github.io).
- Create a `drift/` directory in {{provider}}'s repo; author Drift test cases covering every endpoint in the spec, including every documented response variant (`anyOf`, `oneOf`, `allOf`, discriminators, polymorphism, `$ref` chains, regex patterns, enums).
- Use **drift expressions** for dynamic values (timestamps, UUIDs); **drift datasets** for parameterised cases; **lifecycle hooks** (Lua) for fixture setup / teardown.
- Run the Drift suite locally against a running {{provider}} instance; iterate until green.
- Configure {{ci_tool}} to run Drift on PRs against a deployed (or locally-spun-up) {{provider}}; failures block the merge and notify.
- On merge to main, publish the OpenAPI spec to {{broker_url_or_phrase}} as the provider contract via PactFlow's BDCT flow. Provider version tag = git SHA.
- Confirm the cross-contract verification result is visible in {{broker_url_or_phrase}}'s matrix for {{consumer}} ↔ {{provider}}.
<!-- END BDCT -->

## Acceptance criteria

<!-- BEGIN CDCT -->
- Provider verification harness lives in {{provider}}'s repo and runs locally green against a published consumer pact.
- Provider states are implemented for every consumer expectation that needs one.
- {{ci_tool}} runs the verification on every PR; results are published back to {{broker_url_or_phrase}}.
- Failure notifications reach the team's chosen channel.
<!-- END CDCT -->

<!-- BEGIN BDCT -->
- OpenAPI spec at `{{openapi_path}}` is authoritative and lives in {{provider}}'s repo.
- Drift CLI is installed and `drift/` contains test cases for every endpoint and documented response variant.
- Drift suite passes locally against a real / deployed {{provider}} instance.
- {{ci_tool}} runs Drift on every PR; failures block merge and notify.
- OpenAPI spec is published to {{broker_url_or_phrase}} via the BDCT flow on merge to main.
- Cross-contract verification result is visible in the matrix for {{consumer}} ↔ {{provider}}.
- `can-i-deploy` queries succeed against the recorded environments.
<!-- END BDCT -->
- **`CLAUDE.md` from the plugin's `examples/CLAUDE.md.bdct-drift-provider.md` (BDCT) or `examples/CLAUDE.md.cdct-provider.md` (CDCT) has been copied into {{provider}}'s repo root and customised** (provider name, OpenAPI path, broker URL, CI tool, paths).

## References

- [Pact docs](https://docs.pact.io)
- [{{pact_library}}]({{pact_library_url}})
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Nirvana](https://docs.pact.io/pact_nirvana)
- (BDCT / Both) [Drift docs](https://pactflow.github.io)
- (BDCT / Both) [BDCT guide](https://docs.pactflow.io/docs/bi-directional-contract-testing)
- (BDCT / Both) [BDCT OpenAPI examples](https://github.com/pactflow/bdct-oas-examples)
- (BDCT / Both) [OpenAPI / Pact comparator](https://github.com/pactflow/openapi-pact-comparator)

---
*If you're using Claude Code:*
- *`/swagger-contract-testing` — end-to-end help with provider verification and BDCT flows.*
- *(BDCT) `swagger-contract-testing:drift-testing` skill — write, run, and debug Drift test cases; full endpoint coverage; spec drift detection; lifecycle hooks; Lua scripting.*
- *(BDCT) `swagger-contract-testing:openapi-parser` skill — generate Drift test cases from complex OpenAPI schemas (polymorphism, discriminators, `$ref` chains, regex, enums).*
- *`swagger-contract-testing:pactflow` skill — publish provider contracts, run `can-i-deploy`, inspect the matrix.*
- *`smartbear-mcp` server — AI-assisted operations on PactFlow.*
- *Drop the matching `CLAUDE.md` from this plugin's `examples/` into {{provider}}'s repo root.*

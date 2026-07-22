# {{title: 5. Testing — first CI trigger ({{team}})}}

## Why this phase

Up to now, the consumer tests + provider verification have run on developer laptops. This phase moves them into {{team}}'s shared {{ci_tool}} pipeline, so contract regressions get caught at PR time, not at deploy time. This is the first phase where contract testing actually defends production.

## What to do

<!-- BEGIN CDCT -->
- Add a {{ci_tool}} job to {{consumer}}'s pipeline that runs the consumer tests on every PR.
- Add a publish-pact step on merge to the main branch.
- Add a {{ci_tool}} job to {{provider}}'s pipeline that pulls the latest consumer pact and runs provider verification on every PR.
- Wire the broker to trigger {{provider}}'s verification job whenever {{consumer}} publishes a new pact (via webhook).
- Configure failure notifications: failing build alerts go to the team's chosen channel with a summary of the failure.
<!-- END CDCT -->

<!-- BEGIN BDCT -->
- Add a {{ci_tool}} job to {{provider}}'s pipeline that runs the **Drift CLI** suite on every PR.
- Add a publish-OpenAPI-spec step on merge to the main branch (BDCT provider-contract flow).
- Add a {{ci_tool}} job to {{consumer}}'s pipeline that records the consumer's expectations and publishes them via the BDCT consumer-contract flow.
- Configure cross-contract verification in PactFlow to surface a pass/fail result whenever either side publishes.
- Configure failure notifications: Drift failures + cross-contract verification failures alert the team's chosen channel.
<!-- END BDCT -->

## Acceptance criteria

- {{ci_tool}} runs contract tests on every PR to both {{consumer}} and {{provider}} repos.
- On merge to main, contracts are published to {{broker_url_or_phrase}}.
- (CDCT / Both) Broker webhook triggers {{provider}} verification when {{consumer}} publishes a new pact.
- (BDCT / Both) Drift suite runs in CI and cross-contract verification surfaces in PactFlow.
- Failing builds notify the team's chosen channel with a summary of the failure.

## References

- [Pact in CI ({{ci_tool}})]({{ci_docs_url}})
- [Pact Broker webhook setup](https://docs.pact.io/pact_broker/webhooks)
- [PactFlow webhooks](https://docs.pactflow.io/docs/workshops/ci-cd/webhooks/)
- (BDCT / Both) [Drift docs](https://pactflow.github.io)
- (BDCT / Both) [BDCT guide](https://docs.pactflow.io/docs/bi-directional-contract-testing)

---
*If you're using Claude Code:*
- *`/swagger-contract-testing` — end-to-end help wiring CI.*
- *(BDCT) `swagger-contract-testing:drift-testing` skill — author and debug the Drift CI step.*
- *`swagger-contract-testing:pactflow` skill — webhook + broker config + matrix.*
- *`smartbear-mcp` server — manage broker webhooks programmatically.*

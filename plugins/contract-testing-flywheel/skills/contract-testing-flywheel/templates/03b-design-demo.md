# {{title: 3b. Design — Local CT demo ({{team}})}}

## Why this phase

The fastest way for {{team}} to internalise contract testing is to see one work end-to-end on their own laptop, in {{stack}}. This phase is a throwaway demo — not production code — designed to make every concept from Phase 3a tangible before the team commits to the production implementation in Phases 4 / 4b.

## What to do

<!-- BEGIN CDCT -->
- Pick a single tiny interaction between a mock consumer and a mock provider (e.g. `GET /widgets/:id`).
- In a new throwaway repo, set up the {{stack}} side of {{pact_library}}.
- Write a single consumer test that produces a pact file.
- Write a single provider verification that consumes the pact file from disk.
- Publish the pact to {{broker_url_or_phrase}} (use a test/sandbox tenant if available — don't publish demo pacts to the production broker).
- Show the team how the test failure mode looks when the provider's response shape no longer matches the consumer's expectation.
<!-- END CDCT -->

<!-- BEGIN BDCT -->
- Pick a single tiny endpoint on a mock provider.
- Author a small OpenAPI spec describing it.
- Install the **Drift CLI** (https://pactflow.github.io) and write a Drift test case verifying a running implementation matches the spec.
- Run the Drift suite locally against a stub server.
- Publish the OpenAPI spec to {{broker_url_or_phrase}} as a provider contract via PactFlow's BDCT flow.
- Generate a small mock consumer "expectation" and observe the cross-contract verification result in the PactFlow matrix.
- Show the team how the failure mode looks when the spec and the implementation diverge.
<!-- END BDCT -->

## Acceptance criteria

- The throwaway demo runs end-to-end on at least one engineer's laptop.
- The demo is checked in to a private throwaway repo (so the team can revisit it).
- {{team}} has seen at least one **green** run and one **red** run (deliberately broken) of the demo.
- The team has flagged any open questions that came up during the demo and added them to the Phase 4 / 4b ticket as risks.

## References

- [Pact docs](https://docs.pact.io)
- [{{pact_library}}]({{pact_library_url}})
- [PactFlow docs](https://docs.pactflow.io)

---
*If you're using Claude Code: `swagger-contract-testing:pact-generator` skill can scaffold the consumer test from your example client code; `/swagger-contract-testing` walks through the end-to-end flow.*

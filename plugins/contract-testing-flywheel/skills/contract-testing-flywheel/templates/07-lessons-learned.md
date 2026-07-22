# {{title: 7. Internal docs — lessons learned + best practices ({{team}})}}

## Why this phase

The work is no good to anyone else if only {{team}} knows what it took to get here. This phase captures the team's hard-won lessons — gotchas, conventions, broker URLs, CI snippets, escalation paths — into a single internal page that future {{team}} engineers (and the next team adopting contract testing) can read in 15 minutes and skip half the rediscovery cost.

It also re-measures the Phase 2 baseline metrics so the team can demonstrate the value.

## What to do

- Create a single page in {{team}}'s internal wiki titled "Contract testing — how we do it" (or similar).
- Capture, at minimum:
  - The chosen consumer/provider pair and why it was first.
  - Naming conventions (pacticipant versions, provider states, environments).
  - Broker URL + how to authenticate.
  - {{ci_tool}} snippets for consumer publish, provider verify, and `can-i-deploy`.
  - Gotchas the team hit during Phases 3–6 (provider-state fixture issues, flaky tests, webhook misconfigurations, anything else).
  - Who to talk to when contract testing blocks a deploy (the team's contract-testing point person).
- Re-measure the metrics chosen in Phase 2. Compare against the baseline.
- Link the page from {{team}}'s README so it's discoverable.
- Have one engineer who *didn't* write the page read it cold and flag anything unclear.

## Acceptance criteria

- A single page exists in {{team}}'s internal wiki capturing the items above.
- The page is linked from {{team}}'s README (or equivalent landing page).
- Phase 2 metrics have been re-measured and the delta is noted on the page.
- At least one engineer who did not author the page has reviewed it cold and confirmed it would let them get started on contract testing without further help.

## References

- [Pact Nirvana](https://docs.pact.io/pact_nirvana)
- [PactFlow audit log API (useful for "how active have we been?" measurements)](https://docs.pactflow.io/docs/api/audit)

---
*If you're using Claude Code: `smartbear-mcp` can pull audit-log activity from PactFlow when re-measuring usage in this phase.*

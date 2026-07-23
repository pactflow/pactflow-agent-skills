# {{title: 2. Requirements Analysis — baseline DORA metrics ({{team}})}}

## Why this phase

To prove contract testing was worth the rollout (Phase 7), {{team}} needs a *before* picture. This phase captures the baseline numbers that will be re-measured later. Without a baseline, the team's leadership has to take the value on faith — which makes funding future rollouts to adjacent teams much harder.

## What to do

- Identify the metrics that matter most to {{team}} and its leadership. Default set (DORA + contract-testing-specific):
  - Lead time — from code committed to deployed.
  - Deployment frequency — production deploys per week.
  - Change-failure rate — % of deploys that need a follow-up fix.
  - MTTR — mean time to restore after a failure.
  - Deployment rework rate — % of deploys in the last 6 months that were unplanned bug-fix deploys.
  - Services independently deployable — count of services {{team}} can deploy without coordinating with another team.
  - Integration-test maintenance — % of {{team}}'s time spent maintaining E2E tests.
- For each chosen metric: identify the source of truth (CI, deploy tool, JIRA, manual estimate) and the owner who'll re-measure it in Phase 7.
- Capture the current numbers — even if rough — in the team's wiki or a tracking doc.

## Acceptance criteria

- A tracking doc exists with each chosen metric, its current baseline value, the data source, and the named owner.
- The doc is linked from this ticket.
- The Phase 7 lessons-learned ticket carries a follow-up to re-measure these.

## References

- [DORA — Four key metrics](https://dora.dev/research/2024/dora-report/)
- [Pact ROI thinking (qualitative)](https://docs.pact.io/pact_nirvana)
- [PactFlow audit log API (for measuring activity later)](https://docs.pactflow.io/docs/api/audit)

---
*If you're using Claude Code: `smartbear-mcp` exposes the PactFlow audit API; useful when re-measuring activity in Phase 7.*

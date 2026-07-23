# {{title: 8. Management dashboard — contract-testing health ({{team}})}}

## Why this phase

Engineering management cares about outcomes, not pact files. This dashboard answers two questions on one screen:

1. **Did contract testing pay off?** — by tracking the Phase 2 baseline metrics (see the Phase 2 ticket) before vs after the rollout.
2. **Is contract testing healthy right now?** — by surfacing the app's current verification, deployment-gate, and time-to-fix posture.

It's also a reusable artefact when {{team}}'s leadership argues for the next team's rollout.

## What to build

**Panel A — ROI from the Phase 2 baseline.** Pull the metrics, sources, and owners agreed in the Phase 2 ticket; show baseline vs current.

- Lead time (commit → production deploy)
- Deployment frequency (production deploys per week)
- Change-failure rate (% of deploys needing a follow-up fix)
- MTTR (mean time to restore after a failure)
- Deployment rework rate
- Services {{team}} can deploy independently
- % of {{team}}'s time on E2E test maintenance

For each metric, show: baseline value, current value, delta, and the named owner.

**Panel B — Contract-testing health (current state).** A single-page snapshot for {{consumer}} ↔ {{provider}}:

- Last verification status (pass / fail / stale) per environment, with timestamp.
- Verification pass rate — % of PRs where the verification passed first time, last 30 days.
- `can-i-deploy` gate activity — attempts, blocks, and overrides, last 30 days.
- Mean time to fix a contract regression (commit-fail → commit-green).
- Active (consumer, provider) pairs in the broker.
- Pacts that haven't been verified in > 14 days (stale).
<!-- BEGIN BDCT -->
- Drift suite status on the provider side (pass / fail, coverage of documented endpoints).
<!-- END BDCT -->

## What to do

- Identify the reporting surface. Reuse what {{team}} already has (Datadog, internal BI, Confluence with charts). Do not build something new just for this.
- Pull Panel A data from the sources named in the Phase 2 ticket plus the deploy / CI tooling.
- Pull Panel B data from {{broker_url_or_phrase}}'s metrics and audit APIs (see References).
- Add the dashboard to a recurring engineering-management forum (1:1, monthly review, whatever applies).
- Link the dashboard from the Phase 7 lessons-learned page.

## Acceptance criteria

- Panel A renders all Phase 2 metrics with baseline, current value, delta, and owner.
- Panel B renders at least: last verification status, verification pass rate, can-i-deploy activity, MTT-fix, active pairs, stale pacts.
- The dashboard is shared in a recurring forum with {{team}}'s engineering management.
- Engineering management can name what "good" looks like for at least three metrics across the two panels.
- The dashboard is linked from the Phase 7 lessons-learned page.

## References

- [PactFlow audit log API](https://docs.pactflow.io/docs/api/audit)
- [PactFlow metrics](https://docs.pactflow.io)
- [DORA metrics reference](https://dora.dev/research/2024/dora-report/)

---
*If you're using Claude Code: `smartbear-mcp` exposes the PactFlow audit and metrics APIs; useful when wiring the panels up programmatically.*

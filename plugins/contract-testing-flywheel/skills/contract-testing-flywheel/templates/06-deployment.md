# {{title: 6. Deployment — can-i-deploy + record-deployment ({{team}})}}

## Why this phase

Catching contract regressions at PR time (Phase 5) is half the value. The other half is using the broker's matrix as a *deploy-time gate*: before {{team}} deploys a new version of {{consumer}} or {{provider}}, the broker should be able to answer the question "is this version compatible with every other version currently running in the target environment?" That's what `can-i-deploy` does. Pair it with `record-deployment` so the matrix stays accurate.

This is Pact Nirvana's "Diamond" level.

## What to do

- Add a **`can-i-deploy`** step to each repo's deploy pipeline. The step queries {{broker_url_or_phrase}} for the target environment and exits non-zero (blocking the deploy) if the new version is not compatible with the deployed versions of integration partners.
- Add a **`record-deployment`** step after a successful deploy, so the broker matrix knows which version is now live in which environment.
- If working with Dev-Ops on shared deploy infrastructure, set up a deployment gateway / approval step that calls `can-i-deploy` on the team's behalf.
- (Optional) Set up broker webhooks to alert on matrix changes (compatible → incompatible) so the team finds out before a deploy is attempted.

## Acceptance criteria

- `can-i-deploy` runs in both {{consumer}}'s and {{provider}}'s deploy pipelines and blocks incompatible deploys.
- `record-deployment` runs after every successful deploy to a tracked environment.
- The broker matrix accurately reflects what's currently deployed in each environment (verified by spot-checking the matrix UI after the next two deploys).
- (Optional) The team has documented its escalation path for a failed `can-i-deploy` query (who to talk to, where the conversation happens).

## References

- [can-i-deploy](https://docs.pact.io/pact_broker/can_i_deploy)
- [Recording deployments + releases](https://docs.pact.io/pact_broker/recording_deployments_and_releases)
- [Pact in {{ci_tool}}]({{ci_docs_url}})
- [Pact Nirvana "Diamond" level](https://docs.pact.io/pact_nirvana#level-5-diamond)

---
*If you're using Claude Code:*
- *`/swagger-contract-testing` — end-to-end help wiring can-i-deploy.*
- *`swagger-contract-testing:pactflow` skill — query and explain matrix state, debug can-i-deploy failures.*
- *`swagger-contract-testing:pact-maintainer` skill — manage environments, record deployments, audit broker state.*
- *`smartbear-mcp` server — call can-i-deploy, record-deployment, and matrix programmatically.*

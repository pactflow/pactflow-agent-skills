# CI tool → docs pointer lookup

Used by SKILL.md Step 4 to fill `{{ci_docs_url}}` and to phrase the Testing-phase ticket.

| `{{ci_tool}}` value | `{{ci_docs_url}}` | Notes |
|---|---|---|
| GitHub Actions | https://docs.pact.io/pact_broker/recording_deployments_and_releases#github-actions | Mature, most common in the Pact docs examples. |
| GitLab CI | https://docs.pact.io/getting_started/versioning_in_the_pact_broker#using-git-tags | GitLab pipelines example via `pact-cli`. |
| Buildkite | https://docs.pact.io/pact_broker/recording_deployments_and_releases | Use the generic `pact-broker` CLI step. |
| Jenkins | https://docs.pact.io/pact_broker/recording_deployments_and_releases | Same pattern — `pact-broker` CLI inside a pipeline stage. |
| CircleCI | https://docs.pact.io/pact_broker/recording_deployments_and_releases | Same pattern. |
| Other | https://docs.pact.io/pact_broker | Generic broker docs root. |

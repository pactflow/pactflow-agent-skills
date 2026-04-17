---
name: "swagger-contract-testing"
displayName: "Swagger Contract Testing"
description: "Expert assistant for the full contract testing lifecycle — Pact consumer-driven contracts, provider verification, can-i-deploy, Drift API spec conformance, OpenAPI parsing, and Bi-Directional Contract Testing (BDCT) with PactFlow."
keywords:
  - pact
  - pactflow
  - contract testing
  - consumer-driven contracts
  - can-i-deploy
  - provider verification
  - drift
  - openapi
  - bdct
  - spec drift
  - pact broker
  - consumer test
  - service compatibility
  - api conformance
---

# Swagger Contract Testing

## Onboarding

Run these checks when the Power first activates:

1. **Verify Node.js 20+** — run `node --version`. If missing or below v20, direct the user to https://nodejs.org before continuing.

2. **Check credentials** — the SmartBear MCP server requires two environment variables:
   - `PACT_BROKER_BASE_URL` — full URL to PactFlow or Pact Broker, e.g. `https://yourorg.pactflow.io`
   - `PACT_BROKER_TOKEN` — API token from `app.pactflow.io/settings/api-tokens`

   For an open-source Pact Broker, use `PACT_BROKER_USERNAME` + `PACT_BROKER_PASSWORD` instead of a token.

3. **Verify the connection** — call `contract-testing_list_environments`.
   - Returns results → setup is working
   - Returns 401 → token is wrong or missing
   - Returns 404 → base URL is wrong or has a trailing slash

## Available Tools

The `contract-testing_*` MCP tools connect directly to the user's PactFlow workspace:

- **AI test generation** — `contract-testing_generate_pact_tests`: creates Pact consumer tests from request/response pairs, code files, or an OpenAPI spec
- **AI test review** — `contract-testing_review_pact_tests`: audits existing tests for best-practice violations and false positives
- **Publishing** — `contract-testing_publish_consumer_contracts` and `contract-testing_publish_provider_contract`
- **Deployment safety** — `contract-testing_can_i_deploy`: checks the contract matrix before deploying
- **Recording** — `contract-testing_record_deployment` and `contract-testing_record_release`
- **Workspace management** — pacticipants, environments, webhooks, secrets, labels, and metrics
- **BDCT verification** — cross-contract verification results for Bi-Directional Contract Testing

If any AI tool (`generate_pact_tests`, `review_pact_tests`) returns a 401, call `contract-testing_check_pactflow_ai_entitlements` to diagnose credit or permission issues.

## Steering Map

Load the steering file that matches the user's task:

| Task                                                                                                                              | Load                            |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Writing or generating Pact consumer tests; parsing OpenAPI schemas; scaffolding Drift test cases                                  | `steering/write-tests.md`       |
| Provider verification config; running can-i-deploy; diagnosing can-i-deploy failures; recording deployments; workspace onboarding | `steering/verify-and-deploy.md` |
| Bi-Directional Contract Testing end-to-end (Drift self-verification + publish + cross-contract + can-i-deploy)                    | `steering/bdct.md`              |

## Companion Skills

Install these Kiro skills alongside this Power for deeper reference material and richer guidance:

| Skill              | What it adds                                                                                                          | Install from GitHub                                                                                                  |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **pactflow**       | Full Pact/PactFlow reference — consumer test patterns, provider verification, CI/CD, BDCT, DSL guides for 8 languages | `https://github.com/pactflow/pactflow-agent-skills/tree/main/plugins/swagger-contract-testing/skills/pactflow`       |
| **drift-testing**  | Full Drift CLI reference — test case YAML schema, Lua API, authentication, mock server, CI/CD publishing              | `https://github.com/pactflow/pactflow-agent-skills/tree/main/plugins/swagger-contract-testing/skills/drift-testing`  |
| **openapi-parser** | Complex OpenAPI schema patterns (anyOf/oneOf/allOf/discriminator/$ref) and Drift YAML mapping                         | `https://github.com/pactflow/pactflow-agent-skills/tree/main/plugins/swagger-contract-testing/skills/openapi-parser` |

To install: open the **Agent Steering & Skills** panel in Kiro → **+** → **Import a skill** → **GitHub** → paste the URL.

## License and support

This power integrates with [SmartBear MCP](https://github.com/SmartBear/smartbear-mcp) (MIT).
- [Privacy Policy](https://smartbear.com/privacy/)
- [Support](https://support.smartbear.com/)

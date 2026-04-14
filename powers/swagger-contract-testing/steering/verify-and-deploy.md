# Provider Verification, Can-i-Deploy & Deployments

Covers provider verification config, diagnosing can-i-deploy failures, recording deployments, and workspace onboarding.

---

## Provider Verification Config

Every provider verification setup requires all three selectors and both flags. Missing any of these is the leading cause of can-i-deploy failures.

```javascript
// pact-js / pact-node example
const verifier = new Verifier({
  providerBaseUrl: "http://localhost:3000",
  pactBrokerUrl: process.env.PACT_BROKER_BASE_URL,
  pactBrokerToken: process.env.PACT_BROKER_TOKEN,
  provider: "OrderService",

  consumerVersionSelectors: [
    { mainBranch: true }, // latest from consumer's main branch
    { matchingBranch: true }, // feature branch pair-testing
    { deployedOrReleased: true }, // ALL versions currently deployed/released anywhere
  ],

  enablePending: true, // new consumer interactions won't break provider CI
  publishVerificationResults: process.env.CI === "true", // only publish in CI
  providerVersion: process.env.GIT_COMMIT,
  providerVersionBranch: process.env.GIT_BRANCH,
});
```

The `deployedOrReleased: true` selector is the most commonly missing one — without it, the provider never verifies the version that's actually deployed in production, so can-i-deploy fails.

---

## Can-i-Deploy

Run in CI **before** deploying a service:

```
contract-testing_can_i_deploy
  pacticipant: "FrontendApp"
  version: "abc1234"
  environment: "production"
```

### Diagnosing a can-i-deploy failure

**Step 1: What is actually deployed in production?**

```
contract-testing_get_currently_deployed_versions
  environmentId: "<production-env-uuid>"
```

Get the environment UUID from `contract-testing_list_environments`.

**Step 2: Inspect the contract matrix** — this is the source of truth

```
contract-testing_matrix
  q:
    - pacticipant: "FrontendApp"
      version: "abc1234"
    - pacticipant: "OrderService"
      environment: "production"
```

| Matrix result             | Meaning                                                   |
| ------------------------- | --------------------------------------------------------- |
| No row                    | Provider has never verified this consumer version         |
| Row with `success: false` | Verification ran and failed — genuine contract break      |
| Row with `success: true`  | These two are compatible; check other integrated services |

**Step 3: Fix based on root cause**

| Root cause                                   | Fix                                                                                                                         |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Provider not verifying this consumer version | Add `{ deployedOrReleased: true }` to provider's `consumerVersionSelectors`                                                 |
| Verification results not published           | Set `publishVerificationResults: true`, `providerVersion: $GIT_COMMIT`, `providerVersionBranch: $GIT_BRANCH` in provider CI |
| No webhook firing on pact changes            | Create webhook with event `contract_requiring_verification_published`                                                       |
| Version not recorded as deployed             | Call `contract-testing_record_deployment` for the version currently in production                                           |

For deeper investigation: `plugins/swagger-contract-testing/skills/pactflow/references/pact-broker-advanced.md`

---

## Recording Deployments vs. Releases

Run after a successful deploy to keep the workspace state accurate for future can-i-deploy checks.

**Service deployed to an environment** (replaces previous version):

```
contract-testing_record_deployment
  pacticipantName: "FrontendApp"
  versionNumber: "abc1234"
  environmentId: "<production-env-uuid>"
```

Get the environment UUID from `contract-testing_list_environments`.

**Mobile app or library** (multiple versions coexist simultaneously):

```
contract-testing_record_release
  pacticipantName: "MobileApp"
  versionNumber: "3.2.1"
  environmentId: "<production-env-uuid>"
```

Get the environment UUID from `contract-testing_list_environments`.

Check what's currently live:

```
contract-testing_get_currently_deployed_versions
  environmentId: "<env-uuid>"

contract-testing_get_currently_supported_versions   # for released (mobile/library) versions
  environmentId: "<env-uuid>"
```

---

## Workspace Onboarding

When registering a new service:

**1. Register the pacticipant:**

```
contract-testing_create_pacticipant
  name: "PaymentService"
  repositoryUrl: "https://github.com/example/payment-service"
```

**2. Set the main branch** (required for branch-based can-i-deploy):

```
contract-testing_patch_pacticipant
  pacticipantName: "PaymentService"
  mainBranch: "main"
```

**3. Discover existing environments:**

```
contract-testing_list_environments
```

**4. Create a new environment if needed:**

```
contract-testing_create_environment
  name: "staging"
  displayName: "Staging"
  production: false
```

---

## Observability

```
contract-testing_get_metrics              # workspace-wide stats
contract-testing_get_team_metrics         # per-team breakdown (PactFlow Cloud only)
contract-testing_list_integrations        # all consumer-provider pairings
contract-testing_get_pacticipant_network  # blast-radius visualisation
  pacticipantName: "OrderService"
```

---

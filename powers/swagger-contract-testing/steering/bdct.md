# Bi-Directional Contract Testing (BDCT)

BDCT is a PactFlow cloud-only feature. The provider publishes an OpenAPI spec and self-verification results (e.g. from Drift, Dredd, or Schemathesis). PactFlow performs the cross-contract comparison automatically — the provider never needs to run consumer Pact tests.

## When to Use BDCT

- The provider already has API testing in place (Drift, Pact provider tests, Dredd, Schemathesis, Postman)
- Migrating a REST API to contract testing with minimal provider-side changes
- Large organisations where consumer and provider teams are loosely coupled

---

## Full BDCT Workflow

```
Provider: run Drift against live API
      ↓
contract-testing_publish_provider_contract   ← upload OpenAPI + verification result
      ↓
PactFlow performs cross-contract verification automatically
      ↓
Consumer: publish pact
contract-testing_publish_consumer_contracts
      ↓
      ↓
BOTH SIDES independently before deploying:
      ↓
contract-testing_can_i_deploy                ← gate before deploy (consumer checks its version)
contract-testing_can_i_deploy                ← gate before deploy (provider checks its version)
      ↓
Deploy respective service
      ↓
BOTH SIDES after successful deploy:
      ↓
contract-testing_record_deployment           ← consumer records its deployment
contract-testing_record_deployment           ← provider records its deployment
```

> **Important:** Consumer and Provider publishing steps can happen in any order — PactFlow re-triggers cross-contract verification whenever either side is updated. Each side independently runs `can-i-deploy` before their own deployment and records their deployment afterward.

---

## Step 1: Provider — Self-Verify and Publish

Run a self-verification tool that validates your OpenAPI spec against the live API (or a running mock):

**Drift** (OpenAPI spec conformance):

```bash
drift verify --base-url http://localhost:3000 drift.yaml
```

> **Important:** The spec passed to your verification tool must be the same OpenAPI file you publish as the provider contract. Standard Pact provider verification is NOT sufficient for BDCT — it verifies consumer pacts, not the OpenAPI spec.

Then publish the OpenAPI spec and self-verification result. Set `verifier` to match the tool you ran:

```
contract-testing_publish_provider_contract
  providerName: "OrderService"
  pacticipantVersionNumber: "def5678"    # git SHA
  branch: "main"
  buildUrl: "https://ci.example.com/builds/99"
  contract:
    content: "<base64-encoded OpenAPI YAML or JSON>"
    contentType: "application/yaml"      # or application/json
    specification: "oas"
    selfVerificationResults:
      success: true                      # set to false if tests failed
      verifier: "drift"                  # or "pact", "dredd", "schemathesis", etc.
```

`selfVerificationResults.success` must be `true` for PactFlow to mark the provider as verified. Fix any test failures before publishing.

---

## Step 2: Consumer — Publish the Pact

Same as the standard Pact flow — run consumer tests, then publish:

```
contract-testing_publish_consumer_contracts
  pacticipantName: "FrontendApp"
  pacticipantVersionNumber: "abc1234"
  branch: "main"
  contracts:
    - consumerName: "FrontendApp"
      providerName: "OrderService"
      content: "<base64-encoded pact JSON>"
      contentType: "application/json"
      specification: "pact"
  buildUrl: "https://ci.example.com/builds/42"
```

---

## Step 3: Cross-Contract Verification

PactFlow runs this automatically after both contracts are published. To check results:

**Top-level pass/fail for a provider version:**

```
contract-testing_get_bdct_cross_contract_verification_results
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

**Which consumer contracts were compared:**

```
contract-testing_get_bdct_consumer_contracts
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

**Provider self-verification results:**

```
contract-testing_get_bdct_provider_contract_verification_results
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

**Drill into a specific consumer/provider failure:**

```
contract-testing_get_bdct_consumer_contract_verification_results_by_consumer_version
  providerName: "OrderService"
  providerVersionNumber: "def5678"
  consumerName: "FrontendApp"
  consumerVersionNumber: "abc1234"
```

**Common failure causes:**

| Symptom                                  | Cause                                                              | Fix                                                                                 |
| ---------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Cross-contract verification failed       | Consumer pact uses a request shape not covered by the OpenAPI spec | Update OpenAPI spec or update the consumer's expectations to match the OpenAPI spec |
| `selfVerificationResults.success: false` | Self-verification tool failures before publishing                  | Fix failing tests first, re-run, then re-publish                                    |
| Provider contract not found              | Wrong `providerName` or version                                    | Verify with `contract-testing_list_pacticipants`                                    |

---

## Step 4: Can-i-Deploy and Record Deployment

**Before deploying:**

```
contract-testing_can_i_deploy
  pacticipant: "OrderService"
  version: "def5678"
  environment: "production"
```

**After a successful deploy:**

```
contract-testing_record_deployment
  pacticipantName: "OrderService"
  versionNumber: "def5678"
  environmentId: "<production-env-uuid>"
```

---

## Reference

For deeper detail on BDCT patterns and all available BDCT tools:
`plugins/swagger-contract-testing/skills/pactflow/references/bdct.md`

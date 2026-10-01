# Bi-Directional Contract Testing (BDCT)

BDCT removes the need for the provider to run consumer pact tests directly. Instead, the provider publishes its OpenAPI or AsyncAPI definition and the results of self-verification. PactFlow performs the cross-contract comparison automatically. AsyncAPI provider contracts are also supported in PactFlow On-Premises 2.6.0 and later; read `asyncapi.md` before advising on message-based contracts.

## When to Use BDCT

- The provider team cannot or will not run consumer Pact tests in their pipeline
- The provider already has API spec-based testing (Dredd, Schemathesis, etc.)
- Migrating an existing REST API to contract testing with minimal provider-side changes
- Testing an event-driven API described by AsyncAPI against Pact message interactions
- Large organisations where consumer and provider teams are loosely coupled

## BDCT Workflow

```
Provider publishes OpenAPI or AsyncAPI definition + self-verification results
      ↓
contract-testing_publish_provider_contract
      ↓
PactFlow performs cross-contract verification automatically
      ↓
Consumer publishes pact (same as standard flow)
contract-testing_publish_consumer_contracts
      ↓
can-i-deploy checks BDCT cross-contract results
contract-testing_can_i_deploy
      ↓
Deploy + record
contract-testing_record_deployment
```

## Publishing a Provider Contract

```
contract-testing_publish_provider_contract
  providerName: "OrderService"
  pacticipantVersionNumber: "def5678"
  branch: "main"
  buildUrl: "https://ci.example.com/builds/99"
  contract:
    content: "<base64-encoded OpenAPI YAML or JSON>"
    contentType: "application/yaml"   # or application/json
    specification: "oas"
    selfVerificationResults:
      success: true
      verifier: "dredd"              # or schemathesis, postman, etc.
      # content and format are optional — include if you want results stored
```

The `selfVerificationResults.success` boolean is critical — PactFlow will not mark the provider as verified unless this is `true`.

This example is for OpenAPI. For AsyncAPI publication requirements and verification semantics, read `asyncapi.md`. A provider can publish either an OpenAPI or an AsyncAPI definition, but not both for the same provider version.

## Investigating BDCT Failures

Start broad, then drill down:

### 1. Cross-contract results for a provider version

```
contract-testing_get_bdct_cross_contract_verification_results
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

This shows the overall pass/fail and which consumer pact interactions failed the spec comparison.

### 2. Consumer contracts that were compared

```
contract-testing_get_bdct_consumer_contracts
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

Lists all consumer pact files that PactFlow used in the cross-contract verification.

### 3. Provider self-verification results

```
contract-testing_get_bdct_provider_contract_verification_results
  providerName: "OrderService"
  providerVersionNumber: "def5678"
```

The output of the provider's own spec-verification tool. If `success: false`, the provider failed its own self-verification — the API definition does not match the implementation.

### 4. Pinpointing a specific consumer-provider version pair

When you know which consumer version is failing:

```
# The cross-contract result for this exact pair
contract-testing_get_bdct_cross_contract_verification_results_by_consumer_version
  providerName: "OrderService"
  providerVersionNumber: "def5678"
  consumerName: "CheckoutApp"
  consumerVersionNumber: "abc1234"

# The consumer's pact that was compared
contract-testing_get_bdct_consumer_contract_by_consumer_version
  providerName: "OrderService"
  providerVersionNumber: "def5678"
  consumerName: "CheckoutApp"
  consumerVersionNumber: "abc1234"

# The provider's API definition that was used
contract-testing_get_bdct_provider_contract_by_consumer_version
  providerName: "OrderService"
  providerVersionNumber: "def5678"
  consumerName: "CheckoutApp"
  consumerVersionNumber: "abc1234"
```

## BDCT vs Standard Pact: Key Differences

| Aspect                       | Standard Pact                               | BDCT                                                    |
| ---------------------------- | ------------------------------------------- | ------------------------------------------------------- |
| Provider runs consumer tests | Yes                                         | No                                                      |
| Provider publishes           | Verification results (via pact library)     | API definition + self-verification results              |
| Cross-contract verification  | Done by provider test suite                 | Done by PactFlow automatically                          |
| Consumer side                | Same (publish pact, run can-i-deploy)       | Same                                                    |
| Availability                 | Cloud + On-Prem + Open Source Broker        | Cloud; AsyncAPI also in On-Premises 2.6.0+              |
| Best for                     | Tight teams with shared test infrastructure | Loosely coupled teams; existing spec-based testing      |

## Common Issues

**Cross-contract verification fails even though provider self-verification passed** — The API definition does not fully cover what the consumer expects. For OpenAPI, common causes include `additionalProperties: false`, an overly strict response schema, or missing response headers. For AsyncAPI, use the result-code guidance in `asyncapi.md`.

**`success: false` in self-verification results** — The provider's implementation does not match its own API definition. The provider needs to fix either the implementation or the definition before BDCT can pass.

**Consumer pact publishes fine but can-i-deploy still fails** — Check `contract-testing_get_bdct_cross_contract_verification_results` for the specific provider version deployed in the target environment. The provider may need to re-publish a new version with an updated spec.

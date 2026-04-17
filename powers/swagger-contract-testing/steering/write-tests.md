# Writing & Generating Contract Tests

Covers three entry points: AI-generated Pact consumer tests, manual Pact consumer test patterns, and Drift test scaffolding from OpenAPI specs.

---

## Before Writing Any Test

Always run these two checks first to avoid duplicating existing work:

```
contract-testing_get_provider_states
  provider: "ProviderName"
```

Returns all provider states already defined — reuse these names in new consumer tests rather than inventing new ones.

```
contract-testing_list_pacticipants
```

Confirms the exact registered names of consumers and providers — names must match exactly or pacts will be published under a new, unlinked pacticipant.

---

## AI-Assisted Pact Consumer Test Generation

Use `contract-testing_generate_pact_tests` to generate a complete consumer test. It accepts three input modes:

**From a request/response pair:**

```
contract-testing_generate_pact_tests
  language: "javascript"
  request_response:
    request: "GET /users/123 HTTP/1.1\nHost: api.example.com"
    response: "200 OK\nContent-Type: application/json\n\n{\"id\": 123, \"name\": \"Alice\"}"
  additional_instructions: "use pact-js v13, vitest"
```

**From an OpenAPI spec + operation:**

```
contract-testing_generate_pact_tests
  language: "typescript"
  openapi:
    document: "<base64-encoded OpenAPI YAML or JSON>"
    matcher: "GET /users/{id} → 200"
  additional_instructions: "use pact-js v13, Jest"
```

**From existing code (client or handler):**

```
contract-testing_generate_pact_tests
  language: "java"
  code: "<content of the API client file>"
  additional_instructions: "use pact-jvm 4.x, JUnit 5"
```

To review and improve existing tests:

```
contract-testing_review_pact_tests
  pact_tests: ["<content of consumer test file>"]
  error_messages: "<paste failing test output here if debugging>"
```

---

## Manual Consumer Test Patterns

### Matching rules

**Type matching** (value doesn't matter, only type):

```javascript
like(123); // any integer
like("Alice"); // any string
like(true); // any boolean
```

**Regex matching:**

```javascript
term({ generate: "2024-01-15", matcher: "\\d{4}-\\d{2}-\\d{2}" });
```

**Array matching (EachLike):**

```javascript
eachLike({ id: like(1), name: like("Alice") }); // array of ≥1 objects matching this shape
```

### Optional fields

Pact has no `optional()` matcher. Model optionality with **two separate interactions** differentiated by provider state:

```javascript
// Interaction 1 — field present
given("user 123 has a nickname")
  .uponReceiving("GET /users/123")
  .willRespondWith({ body: { id: like(123), nickname: like("ace") } });

// Interaction 2 — field absent
given("user 123 has no nickname")
  .uponReceiving("GET /users/123")
  .willRespondWith({ body: { id: like(123) } });
```

### Message pacts (Kafka, SQS, SNS) — hexagonal architecture

Split your code before writing tests:

- **Adapter** — the Kafka listener / SQS consumer / `@KafkaListener`. Pact does NOT test this layer.
- **Port** — the domain function that receives the deserialized payload. Pact tests THIS directly.

The consumer test calls the Port function directly with a Pact-generated message. No Kafka broker needed.

For full JS and Java examples: `plugins/swagger-contract-testing/skills/pactflow/references/pact-messages.md`

---

## OpenAPI Schema Parsing for Drift

When generating Drift test cases from a complex OpenAPI spec, resolve all schema compositions before writing tests. One Drift test case per viable schema path.

### Step 1: Locate and extract the endpoint

```bash
grep -n "^  /path/to/endpoint:" spec.yaml
```

Extract: path/query/header parameters, request body schema, each response status code's schema.

### Step 2: Resolve `$ref` chains recursively

```bash
grep -n "SchemaName:" spec.yaml
```

Follow every `$ref` until you have concrete field definitions. Do not write tests against unresolved refs.

### Step 3: Enumerate schema variants

| Pattern           | Rule                                                               |
| ----------------- | ------------------------------------------------------------------ |
| `anyOf` / `oneOf` | One test per variant listed                                        |
| `allOf`           | Merge all sub-schemas into one combined shape                      |
| `discriminator`   | One test per discriminator value                                   |
| `nullable: true`  | Two tests: value present, value null                               |
| Optional field    | Two tests: field present, field absent                             |
| `enum`            | One test per enum value (or representative sample for large enums) |

### Step 4: Map to Drift test YAML

For the Drift YAML syntax for each pattern type, see:
`plugins/swagger-contract-testing/skills/openapi-parser/references/drift-mapping.md`

---

## Drift Test Generation Workflow

```bash
# Scaffold initial project (interactive)
drift init

# Generate an operations: block for endpoints not yet covered
# (script lives in the repo at the path below)
python3 plugins/swagger-contract-testing/skills/drift-testing/scripts/extract_endpoints.py \
  --spec spec.yaml \
  --scaffold \
  --only-missing drift.yaml

# Run tests
drift verify

# Check coverage — reports missing operations and response codes
python3 plugins/swagger-contract-testing/skills/drift-testing/scripts/check_coverage.py \
  --spec spec.yaml \
  --test-files drift.yaml

# Run feedback loop until all tests pass and coverage is complete
# macOS/Linux:
plugins/swagger-contract-testing/skills/drift-testing/scripts/run_loop.sh
# Windows:
plugins/swagger-contract-testing/skills/drift-testing/scripts/run_loop.ps1
```

> **Note:** The scripts above require a local clone of the `pactflow/pactflow-agent-skills` repo. They are not bundled with this Power. If you installed the Power from GitHub without cloning the full repo, find the scripts at:
> https://github.com/pactflow/pactflow-agent-skills/tree/main/plugins/swagger-contract-testing/skills/drift-testing/scripts

For full Drift CLI reference: `plugins/swagger-contract-testing/skills/drift-testing/references/cli-reference.md`
For full test case YAML schema: `plugins/swagger-contract-testing/skills/drift-testing/references/test-cases.md`

---

---
name: drift
description: >
  Expert assistant for Drift — PactFlow's OpenAPI contract testing CLI. Use this skill whenever
  the user mentions Drift, API contract testing, provider verification, spec drift,
  OpenAPI verification, Bi-Directional Contract Testing (BDCT), or asks to write/run/debug
  Drift test cases. Trigger even if they just say "help me test my API against its spec" or
  "write provider side contract tests" — Drift is likely the right tool. Also trigger when the user mentions
  drift expressions, drift datasets, drift lifecycle hooks, or Lua scripting in a testing context.
---

# Drift Skill

Drift is a CLI tool that verifies API implementations against OpenAPI specifications, catching
"API drift" — when your code no longer matches its openapi spec. It's built by PactFlow and supports
Bi-Directional Contract Testing (BDCT).

## Reference Files

Read these when you need deeper detail on a topic:

- `references/test-cases.md` — Full test case YAML schema, all fields, every negative/positive pattern
- `references/lua-api.md` — Complete Lua API: all lifecycle events, `http()`, `dbg()`, modules, embedding in test frameworks
- `references/cli-reference.md` — All CLI commands and flags, parallel execution, JUnit reports, exit codes
- `references/pactflow-and-cicd.md` — BDCT publishing workflow, GitHub Actions (single + parallel), GitLab CI, framework embedding

Full docs: https://pactflow.github.io/drift-docs/
For anything not covered here, fetch: `https://pactflow.github.io/drift-docs/docs/<section>/<page>.md`

To discover all available pages, fetch the sitemap: `https://pactflow.github.io/drift-docs/sitemap.xml`

For an LLM-optimised index of all docs, fetch: `https://pactflow.github.io/drift-docs/llms.txt`

## Installation

```bash
# Quickest — no install needed
npx @pactflow/drift --help

# Project-level (recommended for teams)
npm install --save-dev @pactflow/drift

# Global
npm install -g @pactflow/drift

# Verify
drift --version
```

Manual binary downloads available for Linux/macOS/Windows at:
`https://download.pactflow.io/drift/${version}/${osArch}`

---

## Project Setup

Run the interactive wizard to scaffold a project(do not run this on your own the user should run this as this is a TUI):

```bash
drift init
```

This produces:

```
drift/
├── drift.yaml                 # Main config — sources, plugins, global settings
├── drift.lua                  # Lifecycle hooks and helper functions
├── my-api.dataset.yaml        # Test data
└── my-api.tests.yaml          # Test cases
```

### drift.yaml — main manifest

```yaml
# yaml-language-server: $schema=https://download.pactflow.io/drift/schemas/drift.testcases.v1.schema.json
drift-testcase-file: v1
title: "My API Tests"

sources:
  - name: source-oas # Reference this name in test targets
    path: ./openapi.yaml # or uri: https://... for remote specs
  - name: product-data
    path: ./product.dataset.yaml
  - name: functions
    path: ./product.lua

plugins:
  - name: oas
  - name: json
  - name: data

global:
  auth:
    apply: true
    parameters:
      authentication:
        scheme: bearer # or basic, api-key
        token: ${env:API_TOKEN} # pulled from env var

operations:
  # ... test cases here
```

---

## Running Tests

```bash
# Basic run
drift verify --test-files drift.yaml --server-url https://api.example.com/v1

# Run specific operation
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --operation getProductByID

# Re-run only failed tests
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --failed

# Filter by tags
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --tags smoke
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --tags '!security'  # exclude

# Save results to a directory
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --output-dir ./results

# For PactFlow BDCT publishing
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --generate-result
```

---

## Writing Test Cases

See `references/test-cases.md` for the full guide. Key patterns below.

### Minimal test

```yaml
operations:
  getAllProducts_Success:
    target: source-oas:getAllProducts # source-name:operationId
    expected:
      response:
        statusCode: 200
```

Drift auto-reads the request schema, uses the first OpenAPI example for the body, validates
the response against the JSON schema, and checks content-type. When writing tests all OpenAPI
operation paths as well as response codes needs to be covered and always run all the generated tests
to ensure that they are passing.

### Target without operationId

```yaml
target: product-oas:get:/products/{id} # source:method:path
```

### With path/query/header parameters

```yaml
operations:
  getProductByID_Success:
    target: source-oas:getProductByID
    parameters:
      path:
        id: 10
      query:
        format: json
      headers:
        x-custom: value
    expected:
      response:
        statusCode: 200
```

### With request body from dataset

```yaml
operations:
  createProduct_Success:
    target: source-oas:createProduct
    dataset: product-data
    parameters:
      request:
        body: ${product-data:products.newProduct}
    expected:
      response:
        statusCode: 201
        body: ${equalTo(product-data:products.newProduct)}
```

### Negative / error scenarios

```yaml
operations:
  getProductByID_NotFound:
    target: source-oas:getProductByID
    parameters:
      path:
        id: ${product-data:notIn(products.*.id)} # guaranteed non-existent ID
    expected:
      response:
        statusCode: 404

  createProduct_Unauthorized:
    target: source-oas:createProduct
    exclude:
      - auth # strip global auth
    parameters:
      headers:
        authorization: "Bearer invalid-token"
    expected:
      response:
        statusCode: 401

  createProduct_MissingRequired:
    target: source-oas:createProduct
    parameters:
      request:
        body:
          price: 9.99
      ignore:
        schema: true # suppress schema validation on bad input
    expected:
      response:
        statusCode: 400
```

### Tags

```yaml
operations:
  getAllProducts_Success:
    target: source-oas:getAllProducts
    tags: [smoke, read-only, products]
    expected:
      response:
        statusCode: 200
```

Common tag strategies: `smoke`, `regression`, `security`, `read-only`, `write`, `destructive`

---

## Datasets

Datasets decouple test logic from test data.

```yaml
# product.dataset.yaml
drift-dataset-file: V1
datasets:
  - name: product-data # This name is what you use in ${product-data:...}
    data:
      products:
        existingProduct:
          id: 10
          name: "cola"
          price: 10.99
        newProduct:
          id: 25
          name: "chips"
          price: 5.49
```

Reference data with dot-notation: `${product-data:products.existingProduct.id}`

Use glob `*` for all items: `${product-data:products.*}` or `${product-data:products.*.id}`

**Important:** the `dataset` field in an operation must match the `name` inside the dataset file,
not the source name in `drift.yaml`.

---

## Expressions

Expressions inject dynamic values anywhere a string is allowed (except file headers, operation
keys, and tags).

| Syntax                                              | Example                                       | Purpose                       |
| --------------------------------------------------- | --------------------------------------------- | ----------------------------- |
| `${env:VAR}`                                        | `${env:API_TOKEN}`                            | Environment variable          |
| `${dataset-name:path}`                              | `${product-data:products.item.id}`            | Dataset value                 |
| `${functions:fn_name}`                              | `${functions:generate_uuid}`                  | Call a Lua function           |
| `${source-name:operation.parameters.field.example}` | `${api-spec:operation.parameters.id.example}` | Value from OpenAPI spec       |
| `${notIn(path)}`                                    | `${product-data:notIn(products.*.id)}`        | Generate value NOT in dataset |

Execution order: sources → descriptions → datasets → parameters/expected. You can't reference
a later-resolved field from an earlier-resolved one.

---

## Lifecycle Hooks (Lua)

Use hooks to manage state — create data before a test, clean up after, inject dynamic headers.

```lua
-- drift.lua
local exports = {
  event_handlers = {
    -- Runs before each operation
    ["operation:started"] = function(event, data)
      -- Create test product so delete/update tests have data to work with
      http({
        url = "http://localhost:8080/products",
        method = "POST",
        body = { id = 10, name = "Test Product", price = 9.99 }
      })
    end,

    -- Runs after each operation
    ["operation:finished"] = function(event, data)
      http({ url = "http://localhost:8080/products/10", method = "DELETE" })
    end,

    -- Modify every outgoing HTTP request (e.g. add a signature header)
    ["http:request"] = function(event, data)
      data.headers["x-timestamp"] = tostring(os.time())
      return data   -- MUST return modified data
    end,

    -- Runs once before all operations
    ["testcase:started"] = function(event, data)
      print("Starting test suite")
    end,

    -- Runs once after all operations
    ["testcase:finished"] = function(event, data)
      print("Done")
    end,
  },

  exported_functions = {
    -- Called via ${functions:bearer_token}
    bearer_token = function()
      local res = http({
        url = "http://localhost:8080/auth/token",
        method = "POST",
        body = { username = "test", password = os.getenv("TEST_PASSWORD") }
      })
      return res.body.token
    end,

    generate_uuid = function()
      return string.format("%d-%d", os.time(), math.random(1000, 9999))
    end
  }
}

return exports
```

### Available lifecycle events

| Event                | When                                            |
| -------------------- | ----------------------------------------------- |
| `testcase:started`   | Once before all operations                      |
| `testcase:finished`  | Once after all operations                       |
| `operation:started`  | Before each operation                           |
| `operation:prepared` | After parameters resolved, before HTTP dispatch |
| `operation:finished` | After each operation                            |
| `operation:failed`   | When an operation fails                         |
| `http:request`       | Before every HTTP request — must `return data`  |

### Built-in Lua functions

- `http(request_table)` — make HTTP calls (url, method, query, headers, body); response has status/headers/body
- `dbg(data)` — pretty-print a Lua table for debugging

Standard modules available: `os`, `io`. Pure-Lua LuaRocks packages supported (no C/FFI).

---

## Authentication

### PactFlow auth (for publishing results)

```bash
export PACTFLOW_BASE_URL="https://your-workspace.pactflow.io"
export PACTFLOW_TOKEN="your-api-token"   # Settings → API Tokens in PactFlow UI
```

### API under test auth

In `drift.yaml` global block:

```yaml
global:
  auth:
    apply: true
    parameters:
      authentication:
        scheme: bearer # bearer | basic | api-key
        token: ${env:API_TOKEN}
```

Or dynamic token from Lua:

```yaml
token: ${functions:bearer_token}
```

To test unauthorized scenarios, exclude auth on specific operations:

```yaml
operations:
  createProduct_Unauthorized:
    exclude:
      - auth
    parameters:
      headers:
        authorization: "Bearer bad-token"
    expected:
      response:
        statusCode: 401
```

---

## PactFlow / BDCT Integration

```bash
# 1. Run tests and generate verification bundle
drift verify --test-files drift.yaml --server-url https://api.example.com \
  --generate-result

# 2. Publish to PactFlow
pactflow publish-provider-contract \
  --provider my-api \
  --provider-app-version $(git rev-parse --short HEAD) \
  --branch $(git branch --show-current) \
  --verification-exit-code $EXIT_CODE \
  --verification-results ./drift-results/verification-bundle.json \
  --verification-results-content-type application/vnd.smartbear.drift.result \
  --spec openapi.yaml \
  --spec-content-type application/yaml
```

---

## Plugins

| Plugin        | Name in YAML | Purpose                                  |
| ------------- | ------------ | ---------------------------------------- |
| OpenAPI (OAD) | `oas`        | Spec-first verification (primary driver) |
| Pact          | `pact`       | Verify against Pact contract files       |
| Data          | `data`       | YAML dataset support                     |
| HTTP Dump     | `http-dump`  | Log request/response for debugging       |
| Standard      | (built-in)   | Core validation                          |

```bash
drift plugins installed-plugins   # list available plugins
drift plugins info <plugin-file>  # show plugin metadata
```

---

## Configuration

Priority (highest to lowest): CLI args > env vars > config files

Config files (`drift.config.yaml`, `drift.config.toml`, etc.) are searched in:

1. OS config dir (`~/.config/drift/` on Linux, `~/Library/Application Support/drift/` on macOS)
2. `$HOME/.drift/`
3. Executable directory / CWD

Key settings:

| Setting      | Env var     | Default            | Purpose                     |
| ------------ | ----------- | ------------------ | --------------------------- |
| `log_level`  | `LOG_LEVEL` | INFO               | TRACE/DEBUG/INFO/WARN/ERROR |
| `output_dir` | —           | test file dir      | Results output location     |
| `plugin_dir` | —           | `home_dir/plugins` | Plugin directory            |

---

## Debugging

```bash
# Verbose logging
LOG_LEVEL=DEBUG drift verify --test-files drift.yaml --server-url https://...

# Add http-dump plugin to drift.yaml to log all HTTP traffic
plugins:
  - name: http-dump

# Use dbg() in Lua to inspect event data
["operation:started"] = function(event, data)
  print(dbg(data))
end
```

---

## CI/CD (GitHub Actions example)

```yaml
- name: Run Drift contract tests
  run: |
    drift verify \
      --test-files drift.yaml \
      --server-url ${{ env.API_BASE_URL }} \
      --generate-result
  env:
    API_TOKEN: ${{ secrets.API_TOKEN }}
    PACTFLOW_BASE_URL: ${{ secrets.PACTFLOW_BASE_URL }}
    PACTFLOW_TOKEN: ${{ secrets.PACTFLOW_TOKEN }}
```

---

## Parallel Execution

Run multiple test files simultaneously to reduce CI time:

```bash
drift verify --test-files "tests/*.yaml" --server-url https://...
```

Or specify multiple files:

```bash
drift verify \
  --test-files products.yaml \
  --test-files users.yaml \
  --test-files orders.yaml \
  --server-url https://...
```

---

## Quick Reference: When to Use What

| Scenario                           | Approach                          |
| ---------------------------------- | --------------------------------- |
| Stateless read-only endpoint       | Declarative test, no hooks needed |
| Stable test data exists            | Use dataset expressions           |
| Need to create data before test    | `operation:started` hook          |
| Need to clean up after test        | `operation:finished` hook         |
| Dynamic values (UUIDs, timestamps) | `exported_functions` in Lua       |
| Test a guaranteed 404              | `${notIn(...)}` expression        |
| Re-run only broken tests           | `--failed` flag                   |
| Publish to PactFlow                | `--generate-result` flag          |

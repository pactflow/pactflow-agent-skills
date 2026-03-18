---
name: drift-testing
description: >
  Verifies API implementations against OpenAPI specifications using the Drift CLI,
  catching spec drift and supporting Bi-Directional Contract Testing (BDCT). Use when
  the user mentions Drift, API contract testing, provider verification, spec drift,
  OpenAPI verification, BDCT, drift expressions, drift datasets, drift lifecycle hooks,
  or Lua scripting in a testing context. Use when the user asks to write, run, or debug
  Drift test cases. Use when the user wants full endpoint coverage,
  wants all tests to pass, or asks to "keep running until everything passes".

argument-hint: "[path/to/oad|path/to/drift-test]"
metadata: 
  context: fork
  agent: general-purpose
---

# Drift Skill

Never modify the openapi spec that you are testing.

## Reference Files

- [`references/test-cases.md`](references/test-cases.md) — Full test case YAML schema, all patterns, datasets, expressions
- [`references/auth.md`](references/auth.md) — Authentication config, dynamic tokens, non-standard schemes, 401/403 testing
- [`references/mock-server.md`](references/mock-server.md) — Local testing with Prism: setup, Prefer header, spec quality issues
- [`references/lua-api.md`](references/lua-api.md) — Complete Lua API: lifecycle events, `http()`, `dbg()`, exported functions
- [`references/cli-reference.md`](references/cli-reference.md) — All CLI commands/flags, configuration, parallel execution, exit codes
- [`references/pactflow-and-cicd.md`](references/pactflow-and-cicd.md) — BDCT publishing workflow, GitHub Actions, GitLab CI

## Scripts

- `scripts/extract_endpoints.py` — Reads the spec and outputs all operations + response codes.
  Summary mode flags parameters with no spec example. Scaffold mode (`--scaffold`) emits a
  ready-to-fill `operations:` YAML block with correct auth patterns, nil UUIDs for 404s,
  `ignore.schema` for 4xx, and `FILL_IN` markers. Use `--only-missing <drift.yaml>` to generate
  only the gaps not yet covered by an existing test file. Requires `pyyaml`.
- `scripts/check_coverage.py` — Coverage checker: diffs an OpenAPI spec against Drift test files
  and reports which operations and response codes are missing tests. Requires `pyyaml`.
- `scripts/run_loop.sh` / `scripts/run_loop.ps1` — Feedback loop runner: retries `drift verify --failed` until all tests
  pass, then runs `check_coverage.py`. Both gates must pass for exit 0. Auto-creates the Python venv.
  Use the `.ps1` version on Windows.
- `scripts/start_mock.sh` / `scripts/start_mock.ps1` — Starts a Prism mock server from an OpenAPI spec. Installs Prism if
  needed. Supports `--port` and `--dynamic` flags. Use the `.ps1` version on Windows.

Full docs: https://pactflow.github.io/drift-docs/
For anything not covered here, fetch: `https://pactflow.github.io/drift-docs/docs/<section>/<page>.md`

To discover all available pages, fetch the sitemap: `https://pactflow.github.io/drift-docs/sitemap.xml`

For an LLM-optimised index of all docs, fetch: `https://pactflow.github.io/drift-docs/llms.txt`

---

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


---

## Project Setup

```bash
drift init   # interactive wizard — scaffolds all files below
```

> `drift init` is interactive — ask the user to run it.

```
drift/
├── drift.yaml              # Main config — sources, plugins, global settings
├── drift.lua               # Lifecycle hooks and helper functions
├── my-api.dataset.yaml     # Test data
└── my-api.tests.yaml       # Test cases
```

Minimal `drift.yaml`:

```yaml
# yaml-language-server: $schema=https://download.pactflow.io/drift/schemas/drift.testcases.v1.schema.json
drift-testcase-file: v1
title: "My API Tests"

sources:
  - name: source-oas # referenced in test targets
    path: ./openapi.yaml # or uri: https://... for remote specs
  - name: product-data
    path: ./product.dataset.yaml
  - name: functions
    path: ./product.lua

plugins:
  - name: oas # spec-first verification
  - name: json
  - name: data

global:
  auth:
    apply: true
    parameters:
      authentication:
        scheme: bearer # bearer | basic | api-key
        token: ${env:API_TOKEN}

operations:
  # test cases here — see references/test-cases.md
```

---

## Running Tests

```bash
# Basic run
drift verify --test-files drift.yaml --server-url https://api.example.com/v1

# Single operation (fast iteration)
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --operation getProductByID

# Re-run only failures
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --failed

# Filter by tags
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --tags smoke
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --tags '!destructive'
```

See `references/cli-reference.md` for all flags, parallel execution, JUnit output, and exit codes.

---

## Full Coverage Feedback Loop

When the goal is full endpoint coverage:

> **Caution — destructive tests on production:** If `--server-url` points at a live
> production API, DELETE and POST tests are permanent. Always use a dedicated test account
> and confirm any resource used in a DELETE test is disposable.

Copy this checklist and track your progress:

```
Coverage Loop Progress:
- [ ] Step 0: Check current coverage (check_coverage.py)
- [ ] Step 1: Parse spec and collect operation list (openapi-parser skill or extract_endpoints.py)
- [ ] Step 2: Assemble initial test file
- [ ] Step 3: Run tests (run_loop.sh / run_loop.ps1)
- [ ] Step 4: Diagnose and fix each failure
- [ ] Step 5: Apply common fixes (hooks for state, data seeding)
- [ ] Step 6: Verify exit code 0 + full coverage
```

### Step 0 — Check current coverage

Run before writing tests or when resuming an existing test suite:

```bash
# Set up once
python3 -m venv .venv && .venv/bin/pip install pyyaml -q

# Run against your spec and test file(s)
.venv/bin/python3 path/to/scripts/check_coverage.py \
  --spec openapi.yaml \
  --test-files drift.yaml

# Multiple files / globs
.venv/bin/python3 path/to/scripts/check_coverage.py \
  --spec openapi.yaml \
  --test-files "tests/*.yaml"

# Machine-readable output (for CI or scripting)
.venv/bin/python3 path/to/scripts/check_coverage.py \
  --spec openapi.yaml \
  --test-files drift.yaml --json
```

Output shows: operations with no tests at all, operations missing specific response codes,
and overall operation/code percentages. Exit code 0 = full coverage, 1 = gaps remain.

The script excludes 500/501/502/503 by default (same rule as Step 1 below). Pass
`--exclude-codes` to customise.

### Step 1 — Parse the spec with the openapi-parser skill

Use the **openapi-parser skill** to parse the spec. Collect: the complete operation list, all documented response codes per operation, and ready-to-use `operations:` YAML stubs.

Alternatively, `extract_endpoints.py` does this without the skill:

```bash
# See all operations + response codes, flagging params with no spec example
.venv/bin/python3 scripts/extract_endpoints.py --spec openapi.yaml

# Generate skeleton stubs for every operation
.venv/bin/python3 scripts/extract_endpoints.py --spec openapi.yaml \
  --scaffold --source my-oas > operations.yaml

# Generate ONLY the gaps not already in an existing test file
.venv/bin/python3 scripts/extract_endpoints.py --spec openapi.yaml \
  --scaffold --only-missing drift.yaml --source my-oas >> drift.yaml
```

```
GET /products          → 200, 401, 404
POST /products         → 201, 400, 401
DELETE /products/{id}  → 204, 401, 403, 404
```

**Critical:** Any parameter without a spec-level `example` causes `Value for query parameter X is missing`. Supply an explicit value in `parameters.query/path/headers` for each.

**Globally-required query parameters** (e.g. `?version=YYYY-MM-DD` on every endpoint) can be
injected once via the `http:request` hook rather than repeated in every test case:

```lua
["http:request"] = function(event, data)
  if data.query == nil then data.query = {} end
  data.query["version"] = "2024-01-04"
  return data   -- MUST return modified data
end
```

**Duplicate `operationId` values** — some specs reuse the same operationId for two different
paths. Use `method:path` targeting for the affected operation:

```yaml
target: source-oas:post:/orgs/{org_id}/apps/installs/{install_id}/secrets
```

**500 responses are excluded from the coverage requirement** — a 500 requires a server bug and
can't be deterministically triggered.

### Step 2 — Assemble the initial test file

Wire the stubs from the openapi-parser into `drift.yaml`. Don't aim for perfection — the loop
surfaces what's missing. Start each test as simple as possible:

```yaml
getProduct_Success:
  target: source-oas:getProductByID
  parameters:
    path:
      id: 10
  expected:
    response:
      statusCode: 200
```

For error paths, see `references/test-cases.md` for 401, 403, 404, and 400 patterns.
For mock server setup, see `references/mock-server.md`.

### Step 3 — Run and capture failures

The `run_loop.sh` script automates this entire step through Step 6:

```bash
# Runs drift --failed in a loop, then checks coverage. Exits 0 only when both pass.
path/to/scripts/run_loop.sh \
  --spec openapi.yaml \
  --test-files drift.yaml \
  --server-url https://api.example.com/v1
```

Or run drift manually and iterate:

```bash
drift verify --test-files drift.yaml --server-url https://api.example.com/v1

# Re-run only failures to keep the loop fast
drift verify --test-files drift.yaml --server-url https://api.example.com/v1 --failed
```

For local testing with a mock server, start Prism first:

```bash
path/to/scripts/start_mock.sh --spec openapi.yaml --port 4010
# then in another terminal:
path/to/scripts/run_loop.sh --spec openapi.yaml --test-files drift.yaml --server-url http://localhost:4010
```

### Step 4 — Diagnose and fix each failure

| Symptom                                  | Likely cause                                        | Fix                                                                                 |
| ---------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Got 404, expected 200                    | Test data doesn't exist                             | Add `operation:started` hook to seed the resource                                   |
| Got 200, expected 404                    | ID happens to exist                                 | Use `${notIn(...)}` or nil UUID `00000000-0000-0000-0000-000000000000`              |
| Got 401, expected 200                    | Auth not configured                                 | Add `global.auth` or check token env var                                            |
| Got 200, expected 401                    | Auth not stripped                                   | Add `exclude: [auth]` + bad token                                                   |
| Got 403, expected 200                    | Token lacks required scope                          | Use a token with sufficient permissions                                             |
| Got 200, expected 403                    | Need valid auth + forbidden resource                | Point at a resource the token can't access; see `references/auth.md`                |
| Schema validation error on response      | API drifted from spec, OR spec has invalid examples | Check whether spec examples are valid — Drift may be correctly reporting a spec bug |
| `Value for query parameter X is missing` | Optional param has no spec `example`                | Supply an explicit value for every param without a spec example                     |
| Got 400 on a 200 test                    | Missing globally-required query param               | Inject it via `http:request` hook or add to every test case                         |
| Got 500                                  | Test data triggered a server bug                    | Fix the data                                                                        |

**`ignore: { schema: true }`** suppresses request schema validation only — use on 400 scenarios. Response schema validation has no bypass; spec example bugs surface as failures (see `references/mock-server.md`).

**Multiple 2xx codes:** Write one test per documented code — `statusCode: [200, 204]` array syntax is not supported.

**Dynamic IDs and hook timing:** Dataset expressions resolve _before_ `operation:started`. Use pre-seeded static IDs, or rewrite the URL via `http:request`.

### Step 5 — Common fixes

**Data must exist before the test (DELETE, PUT, PATCH):**

```lua
["operation:started"] = function(event, data)
  if data.operation == "deleteProduct_Success" then
    http({ url = server_url .. "/products", method = "POST",
           body = { id = 10, name = "test", price = 9.99 } })
  end
end,
["operation:finished"] = function(event, data)
  http({ url = server_url .. "/products/10", method = "DELETE" })
end,
```

See `references/lua-api.md` for the full Lua API and the `data` object shape.

### Step 6 — Repeat until all green

```bash
drift verify --test-files drift.yaml --server-url https://api.example.com/v1
echo "Exit code: $?"
```

Before declaring done, verify coverage is complete:

```bash
.venv/bin/python3 path/to/scripts/check_coverage.py \
  --spec openapi.yaml --test-files drift.yaml
echo "Coverage exit: $?"
```

Done when both commands exit 0.

---

## Quick Reference

| Scenario                           | Approach                                       |
| ---------------------------------- | ---------------------------------------------- |
| Stateless read-only endpoint       | Declarative test, no hooks                     |
| Stable test data                   | Dataset expressions                            |
| Create data before test            | `operation:started` hook                       |
| Clean up after test                | `operation:finished` hook                      |
| Dynamic values (UUIDs, timestamps) | `exported_functions` in Lua                    |
| Guaranteed 404                     | `${notIn(...)}` or nil UUID                    |
| Force error code on mock server    | `Prefer: code=X` header                        |
| Test without live backend          | Prism mock — see `references/mock-server.md`   |
| Non-standard auth prefix           | `http:request` hook — see `references/auth.md` |
| Re-run only broken tests           | `--failed` flag                                |
| Publish to PactFlow                | `--generate-result` flag                       |

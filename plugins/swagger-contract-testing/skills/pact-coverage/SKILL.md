---
name: pact-coverage
description: >
  Runs a coverage check to find which API operations, status codes, request body
  required fields, and response body required fields are NOT exercised by existing
  Pact consumer tests. Invoke this skill whenever the user asks "what's not covered
  by my pacts?", "which endpoints are missing pact tests?", "do my pact files cover
  the full spec?", "how complete is my pact coverage?", "which required fields
  aren't tested?", or any time they have Pact v4 JSON files and want to measure
  contract test coverage against an OpenAPI spec. Also invoke when they say they
  want to improve pact coverage or find coverage gaps — even if they don't say
  "pact-coverage" explicitly. Do NOT invoke for running provider verification,
  publishing pacts to a broker, or checking can-i-deploy; use the pactflow skill
  for those.
argument-hint: "[./consumer-src path/to/openapi.yaml \"pacts/*.json\"]"
metadata:
  context: fork
  agent: general-purpose
---

# Pact Coverage

Analyses Pact v4 `Synchronous/HTTP` interactions against an OpenAPI spec and reports
gaps across four dimensions: path/method, status codes, request body required fields,
and response body required fields. Never modifies files.

**Prerequisites:** `ripwire` is required — as an MCP server for interactive use (see [ripwire MCP setup](#ripwire-mcp-setup) above), or as a CLI binary for CI scripts (see [Scripts (CI / advanced)](#scripts-ci--advanced) below). Run `command -v ripwire` to check; see [`references/install-ripwire.md`](references/install-ripwire.md) for install instructions.

---

## What this measures

Pact coverage answers one question: **do the consumer's pact files exercise everything the consumer actually uses from the provider?**

The provider's OAS describes its full surface — but the consumer only calls a subset of it. Measuring coverage against the full OAS produces false gaps (unused provider endpoints appearing as uncovered). The correct denominator is the *consumer-filtered provider OAS*: the slice of the provider's OAS that the consumer actually calls.

Flow:
1. **ripwire scans the consumer codebase** → discovers which provider paths/methods the consumer calls
2. **The provider OAS is filtered** to only those routes (removing unused endpoints)
3. **Pact files are compared** against the filtered OAS → gaps = operations/codes/fields the consumer calls but hasn't exercised in any pact interaction

---

## ripwire MCP setup

The `swagger-contract-testing:pact-coverage` agent uses ripwire via MCP tools for adaptive route discovery. The ripwire MCP server must be connected before running coverage interactively.

**Register in one command:**
```bash
ripwire wrap claude   # prints the command to run
# → claude mcp add ripwire -- ripwire --mcp
```

Or add to `mcp.json`:
```json
{ "mcpServers": { "ripwire": { "command": "ripwire", "args": ["--mcp"] } } }
```

For full install instructions → [`references/install-ripwire.md`](references/install-ripwire.md)

For CI usage (no agent, no MCP), see the Scripts section below.

---

## OpenAPI spec selection

Before running the coverage check, resolve which spec file to use:

**If `--spec` was not provided or is ambiguous**, search the project for OpenAPI/Swagger files:
```bash
find . -maxdepth 4 \( -name "openapi.yaml" -o -name "openapi.json" \
  -o -name "swagger.yaml" -o -name "swagger.json" \
  -o -name "*openapi*.yaml" -o -name "*openapi*.json" \
  -o -name "*swagger*.yaml" -o -name "*swagger*.json" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*"
```

After finding candidates, **validate each file is an actual OAS/Swagger document** — open it and
confirm it has an `openapi`, `swagger`, or `paths` top-level key. Discard files that don't (e.g.
MCP server descriptors, schema files, workflow configs). If discarding reduces the candidate list,
re-apply the rules below on the validated set.

Note: if no local spec exists because the consumer tests against an *external* provider (e.g. a
SaaS API), ask the user for the provider's OAS path or URL before proceeding.

- **No valid files found** — ask the user to provide the path or URL; do not proceed without a spec. **Never synthesize or generate an OAS from pact interactions, client code, or any other source — only use a real spec provided by the user or fetched from a broker.**
- **Exactly one valid file found** — use it automatically (no need to ask).
- **Multiple valid files found** — ask via selector:

```
AskUserQuestion({
  question: "Found multiple OpenAPI spec files. Which would you like to use?",
  multiSelect: false,
  options: [
    { label: "openapi.yaml", description: "./openapi.yaml" },
    { label: "docs/openapi.yaml", description: "./docs/openapi.yaml" },
    …one entry per file found…
    { label: "Specify my own", description: "I'll provide a custom path or URL" },
  ]
})
```

If the user picks **Specify my own**, prompt for the path and use that.

---

## Pact file resolution

When no pact files exist on disk yet, resolve them in this order — stop as soon as files are found:

**1. MCP tools** (preferred when running inside a Claude session)
Use `contract-testing_get_pacts_for_verification` or `contract-testing_list_pacticipant_versions`
to retrieve the latest published pacts for the consumer. Save each response body as
`pacts/{consumer}-{provider}.json`, then proceed with the coverage check.

**2. Broker CLI / direct HTTP** (when MCP tools are unavailable)
Pass broker credentials — the script fetches pacts automatically:
```bash
uv run scripts/parse_pact_coverage.py --spec openapi.yaml \
  --consumer OrderClient \
  --broker-url $PACT_BROKER_BASE_URL \
  --broker-token $PACT_BROKER_TOKEN
```
Env vars `PACT_BROKER_BASE_URL`, `PACT_BROKER_TOKEN`, `PACT_CONSUMER` are read automatically if flags are omitted.

**3. Run consumer tests** (when no broker is available)
1. Locate pact test files — search for `*pact*` / `*contract*` in test directories, or use
   ripwire: `ripwire . --for="pact consumer test setup"`.
2. Determine the exact run command from the project's build config (`package.json` scripts,
   `pyproject.toml`, `pom.xml` surefire, `build.gradle`, etc.).
   Examples: `npm run test:pact`, `pytest tests/pact/`, `mvn test -Dtest=*PactTest`.
3. Run the command. Generated pacts appear in `pacts/`, `target/pacts/`, or `build/pacts/`.
4. Re-invoke this skill with `--pacts <output-dir>/*.json`.

---

## Pact file selection

After resolving pact files (from disk, broker, or tests), if **more than one** pact file is found,
ask the user which to include before running the coverage check:

```
AskUserQuestion({
  question: "Found N pact files. Which would you like to measure coverage for?",
  multiSelect: true,
  options: [
    { label: "consumer-A-provider.json", description: "…/pacts/consumer-A-provider.json" },
    { label: "consumer-B-provider.json", description: "…/pacts/consumer-B-provider.json" },
    …one entry per file…
    { label: "All of the above", description: "Run coverage across every pact file found" },
    { label: "Specify my own", description: "I'll provide a custom glob or file path" },
  ]
})
```

- If the user picks **All of the above**, pass every file to `--pacts`.
- If the user picks **Specify my own**, ask for the glob or path, then use that.
- If only **one** pact file is found, skip this step and proceed directly.

---

## Running coverage

Invoke the `swagger-contract-testing:pact-coverage` agent. It will:
1. Resolve the provider OAS spec and pact files (prompting if ambiguous)
2. Use ripwire MCP tools to discover which provider routes the consumer calls
3. Build a consumer-filtered provider OAS
4. Run `parse_pact_coverage.py` and report the gaps

The agent handles all framework-specific patterns (direct HTTP clients, class-based wrappers, deserialization sites, string-dispatch) automatically.

---

## Interpreting the report

| Section | What it measures | Covered means |
|---------|-----------------|---------------|
| 1 · PATH / METHOD | Each OAS operation | ≥1 pact interaction matches method + path |
| 2 · STATUS CODES | Per covered operation | Every documented 2xx/4xx code has a pact response |
| 3 · REQ BODY FIELDS | Required request fields | Every `required[]` field appears in ≥1 pact req body |
| 4 · RESP BODY FIELDS | Required response fields per (op, code) | Every `required[]` field appears in ≥1 pact resp body |

Default exclusions: 500, 501, 502, 503. 3xx, 5xx, wildcard codes, and `default` are
always silently skipped. For dimension details, path matching, and limitations →
[`references/coverage-concepts.md`](references/coverage-concepts.md).

---

## Filling gaps

| Gap type | Recommended action |
|----------|--------------------|
| Entire operation not covered (Section 1) | Invoke the `pact-generator` agent |
| Missing status code (Section 2) | Add an interaction with that status; use the pactflow skill for provider state hints |
| Missing required request field (Section 3) | Enrich an existing interaction's request body |
| Missing required response field (Section 4) | Enrich an existing interaction's response body for that (op, status) |

After adding or modifying interactions, re-run to verify exit code 0.

---

## Scripts (CI / advanced)

For headless CI usage without the agent:

```bash
# Step 1: discover consumer routes (Strategy 1 only — simple consumers)
uv run scripts/build_filtered_oas.py \
  --consumer-root ./consumer-src \
  --output consumer-routes.json

# Step 2: filter provider OAS + measure coverage
uv run scripts/parse_pact_coverage.py \
  --spec provider-openapi.yaml \
  --pacts "pacts/*.json" \
  --consumer-routes "$(cat consumer-routes.json)"
```

| Script | Purpose |
|--------|---------|
| `scripts/parse_pact_coverage.py` | Coverage checker — accepts `--consumer-routes` JSON for filtered OAS |
| `scripts/build_filtered_oas.py` | CI tool: Strategy 1 route discovery only (outputs `--consumer-routes` JSON) |

**Note:** `build_filtered_oas.py` runs Strategy 1 only. For consumers with class-based HTTP clients or unusual patterns, use the interactive agent which tries all strategies.

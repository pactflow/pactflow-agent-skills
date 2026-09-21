---
name: pact-coverage
description: >
  Runs a coverage check to find which API operations, status codes, request body
  required fields, and response body required fields are NOT exercised by existing
  Pact consumer tests. Invoke this skill whenever the user asks "what's not covered
  by my pacts?", "which endpoints are missing pact tests?", "do my pact files cover
  the full spec?", "how complete is my pact coverage?", "which required fields
  aren't tested?", or any time they have Pact v2/v3/v4 JSON files and want to
  measure contract test coverage against an OpenAPI spec. Also invoke when they
  say they want to improve pact coverage or find coverage gaps — even if they
  don't say "pact-coverage" explicitly. Do NOT
  invoke for running provider verification, publishing pacts to a broker, or
  checking can-i-deploy; use the pactflow skill for those.
argument-hint: "[./consumer-src path/to/openapi.yaml \"pacts/*.json\"]"
metadata:
  context: fork
  agent: general-purpose
---

# Pact Coverage

Analyses Pact v2/v3/v4 interactions against an OpenAPI spec and reports gaps across
four core dimensions: path/method, status codes, request body required fields, and
response body required fields. An optional fifth dimension — consumer code status
branch analysis — surfaces status codes the consumer handles in code but hasn't
tested in any pact. Never modifies files.

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

> **NEVER synthesize or hallucinate an OAS. Only use a real spec from disk, a URL, PactFlow, or the `oas-generator` skill — which performs static analysis of real source code, not hallucination.**

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

### After validation — you MUST follow one of these three paths and no others:

- **No valid files found** — **STOP. Do not proceed. Do not generate or synthesize anything.** Use `AskUserQuestion` immediately:

```
AskUserQuestion({
  question: "No OpenAPI/Swagger spec found in this project. How would you like to provide one?",
  multiSelect: false,
  options: [
    { label: "I'll provide a file path", description: "Enter the local path to the spec" },
    { label: "I'll provide a URL", description: "Enter a URL to fetch the spec from" },
    { label: "Provider has a BDCT contract on PactFlow", description: "Fetch the provider OAS from PactFlow using contract-testing_get_bdct_provider_contract" },
    { label: "Generate from provider codebase", description: "Use the oas-generator skill to produce a spec from the provider's source code (requires ripwire)" },
  ]
})
```

  Then follow the path the user selects:

  - **Provide a file path / URL** — follow up with a free-text prompt for the specific path or URL. If the user cannot or does not provide one, stop with an error — do not proceed.
  - **Provider has a BDCT contract on PactFlow** — call `contract-testing_get_bdct_provider_contract` with the provider name and version to retrieve the OAS. Write the response body to a temp file and use that as `spec_path`.
  - **Generate from provider codebase** — **invoke the `swagger-contract-testing:oas-generator` skill** with the provider codebase path. Once the skill produces a spec file, use that path as `spec_path` and continue. Note: the generated spec may be incomplete for complex schemas but is always valid OAS and usable for path-coverage testing.

- **Exactly one valid file found** — use it automatically (no need to ask).

- **Multiple valid files found** — **STOP. Do not pick automatically.** You MUST use `AskUserQuestion` before proceeding:

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

  If the user picks **Specify my own**, follow up with a free-text prompt for the path and use that.

---

## Pact file resolution

> **NEVER synthesize or generate pact JSON from scratch. Only use real pact files from disk, fetched from a broker, or produced by running the actual consumer test suite.**

**First, search for pact files on disk** in the standard locations:
```bash
find . -maxdepth 5 \( -path "*/pacts/*.json" -o -path "*/target/pacts/*.json" -o -path "*/build/pacts/*.json" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*"
```

**If pact files are found on disk**, proceed directly to the [Pact file selection](#pact-file-selection) step.

**If no pact files are found on disk**, **STOP. Do not proceed automatically.** You MUST use `AskUserQuestion` to ask the user how to obtain them:

```
AskUserQuestion({
  question: "No pact files found on disk. How would you like to obtain them?",
  multiSelect: false,
  options: [
    { label: "Fetch from PactFlow/broker (MCP)", description: "Use the connected PactFlow MCP tools to fetch the latest published pacts" },
    { label: "Provide broker URL + credentials", description: "I'll supply PACT_BROKER_BASE_URL and PACT_BROKER_TOKEN to fetch pacts via CLI" },
    { label: "Run consumer tests now", description: "Run the consumer test suite to generate fresh pact files" },
    { label: "Specify a path or glob", description: "I'll provide the path or glob pattern to the pact files" },
  ]
})
```

Then follow the path the user selects:

**Fetch from PactFlow/broker (MCP)**
Use `contract-testing_get_pacts_for_verification` or `contract-testing_list_pacticipant_versions`
to retrieve the latest published pacts for the consumer. Save each response body as
`pacts/{consumer}-{provider}.json`, then proceed with the coverage check.

**Provide broker URL + credentials**
Pass broker credentials — the script fetches pacts automatically:
```bash
uv run scripts/parse_pact_coverage.py --spec openapi.yaml \
  --consumer OrderClient \
  --broker-url $PACT_BROKER_BASE_URL \
  --broker-token $PACT_BROKER_TOKEN
```
Env vars `PACT_BROKER_BASE_URL`, `PACT_BROKER_TOKEN`, `PACT_CONSUMER` are read automatically if flags are omitted.

**Run consumer tests now**
1. Locate pact test files — search for `*pact*` / `*contract*` in test directories, or use
   ripwire: `ripwire . --for="pact consumer test setup"`.
2. Determine the exact run command from the project's build config (`package.json` scripts,
   `pyproject.toml`, `pom.xml` surefire, `build.gradle`, etc.).
   Examples: `npm run test:pact`, `pytest tests/pact/`, `mvn test -Dtest=*PactTest`.
3. Run the command. Generated pacts appear in `pacts/`, `target/pacts/`, or `build/pacts/`.

**Specify a path or glob**
Use the path or glob the user provides.

---

## Pact file selection

After resolving pact files (from disk, broker, or tests):

- If only **one** pact file is found, use it automatically (no need to ask).
- If **more than one** pact file is found, **STOP. Do not pick automatically.** You MUST use `AskUserQuestion` before proceeding:

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
- If the user picks **Specify my own**, follow up with a free-text prompt for the glob or path, then use that.

---

## Consumer codebase path

Before invoking the agent, resolve the consumer codebase root (`consumer_root`).

If the user provided it as an argument (e.g. `./consumer-src`), use that directly.

Otherwise, **ask**:

```
AskUserQuestion({
  question: "Where is the consumer codebase? Provide the path to the source root.",
  multiSelect: false,
  options: [
    { label: "Current directory (.)", description: "Use the current working directory" },
    { label: "I'll specify a path", description: "Enter the path to the consumer source root" },
  ]
})
```

If the user picks **I'll specify a path**, follow up with a free-text prompt. Do not proceed without a valid `consumer_root`.

---

## Running coverage

Pass the three resolved inputs to the `swagger-contract-testing:pact-coverage` agent:
- `consumer_root` — path to the consumer codebase (resolved above)
- `spec_path` — path to the provider OAS (resolved in OpenAPI spec selection)
- `pact_glob` — glob or list of pact files (resolved in Pact file selection)

The agent will:
1. Use ripwire MCP tools to discover which provider routes the consumer calls
2. Build a consumer-filtered provider OAS
3. Run `parse_pact_coverage.py` and report the gaps

The agent **does not** prompt for missing inputs — it will hard-stop with an error if any of the three are absent. Ensure all three are resolved before invoking.

The agent handles all framework-specific patterns (direct HTTP clients, class-based wrappers, deserialization sites, string-dispatch) automatically.

---

## Interpreting the report

| Section | What it measures | Covered means |
|---------|-----------------|---------------|
| 1 · PATH / METHOD | Each OAS operation | ≥1 pact interaction matches method + path |
| 2 · STATUS CODES | Per covered operation | Every documented 2xx/4xx code has a pact response |
| 3 · REQ BODY FIELDS | Required request fields | Every `required[]` field appears in ≥1 pact req body |
| 4 · RESP BODY FIELDS | Required response fields per (op, code) | Every `required[]` field appears in ≥1 pact resp body |
| 5 · STATUS BRANCHES | Consumer code branches on status codes (optional) | Every status the consumer explicitly checks is tested in pact |

Default exclusions: 500, 501, 502, 503. 3xx, 5xx, wildcard codes, and `default` are
always silently skipped. Section 5 appears only when `--consumer-root` is passed.

**Schema quality warnings (⚠):** when an OAS operation has response/request body properties
but no `required: [...]` array, Sections 3 and 4 report N/A. The script emits a ⚠ warning
listing which fields the pact already sends that aren't measured, and suggests adding
`required:` to the OAS schema to unlock field-level coverage. These warnings do not affect
the exit code.

For dimension details, path matching, and limitations →
[`references/coverage-concepts.md`](references/coverage-concepts.md).

---

## Filling gaps

| Gap type | Recommended action |
|----------|--------------------|
| Entire operation not covered (Section 1) | Invoke the `pact-generator` agent |
| Missing status code (Section 2) | Add an interaction with that status; use the pactflow skill for provider state hints |
| Missing required request field (Section 3) | Enrich an existing interaction's request body |
| Missing required response field (Section 4) | Enrich an existing interaction's response body for that (op, status) |
| Status code handled in code but not in pact (Section 5) | Add a pact interaction for that status code, or verify the branch is covered via a provider state |
| ⚠ OAS has properties but no `required[]` (Sections 3/4 N/A) | Add `required:` to the OAS requestBody or response schema to enable field-level coverage |

After adding or modifying interactions, re-run to verify exit code 0.

---

## Scripts (CI / advanced)

For headless CI usage without the agent. Both scripts are in the `scripts/` directory inside the
pact-coverage skill and support `uv run` (self-installing dependencies).

```bash
# Step 1: discover consumer routes (Strategy 1 only — simple consumers)
uv run scripts/build_filtered_oas.py \
  --consumer-root ./consumer-src \
  --output consumer-routes.json

# Step 2: filter provider OAS + measure coverage (Sections 1-4)
uv run scripts/parse_pact_coverage.py \
  --spec provider-openapi.yaml \
  --pacts "pacts/*.json" \
  --consumer-routes "$(cat consumer-routes.json)"

# With Section 5 (consumer code status branch analysis)
uv run scripts/parse_pact_coverage.py \
  --spec provider-openapi.yaml \
  --pacts "pacts/*.json" \
  --consumer-routes "$(cat consumer-routes.json)" \
  --consumer-root ./consumer-src

# Fetch pacts from broker directly (no local files needed)
uv run scripts/parse_pact_coverage.py \
  --spec provider-openapi.yaml \
  --consumer OrderClient \
  --broker-url $PACT_BROKER_BASE_URL \
  --broker-token $PACT_BROKER_TOKEN
```

| Script | Purpose |
|--------|---------|
| `scripts/parse_pact_coverage.py` | Coverage checker (v2/v3/v4). Flags: `--spec`, `--pacts`, `--consumer-routes` (filtered OAS), `--consumer-root` (Section 5), `--exclude-codes`, `--json`, `--broker-url`/`--broker-token`/`--consumer` (broker fetch) |
| `scripts/build_filtered_oas.py` | CI tool: Strategy 1 route discovery only (outputs `--consumer-routes` JSON for `parse_pact_coverage.py`) |

**Exit codes for `parse_pact_coverage.py`:** `0` = full coverage across all 4 dimensions · `1` = gaps found · `2` = error (spec/pact unparseable, consumer-filtering failed). Section 5 gaps do **not** affect the exit code.

**Note:** `build_filtered_oas.py` runs Strategy 1 only. For consumers with class-based HTTP clients or unusual patterns, use the interactive agent which tries all strategies.

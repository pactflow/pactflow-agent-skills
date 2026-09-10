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

**Prerequisites:** `ripwire` must be on `PATH` for Steps 1 and 2.
If `command -v ripwire` fails, read [`references/install-ripwire.md`](references/install-ripwire.md)
and install it before continuing.

---

## Quickstart — single command (happy path)

When you have the consumer source and a pact glob, this is the only command needed:

```bash
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml \
  --pacts "pacts/*.json" \
  --consumer-root ./consumer-src
```

`--consumer-root` runs ripwire internally to discover which endpoints the consumer
calls and narrows the OAS to those paths before measuring coverage. Unused provider
endpoints never appear as gaps.

**Fallback — pre-built KG:**
```bash
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml --pacts "pacts/*.json" --kg kg.xml
```

**Fallback — unsupported HTTP client (aiohttp, net/http, HttpClient):**
```bash
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml --pacts "pacts/*.json" \
  --consumer-routes '[{"method":"GET","path":"/orders/{id}"},{"method":"POST","path":"/orders"}]'
```

**Machine-readable output + exclude status codes:**
```bash
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml --pacts "pacts/*.json" \
  --consumer-root ./consumer-src \
  --json --exclude-codes 500 501 502 503
```

**Exit codes:** `0` = full coverage · `1` = gaps found · `2` = error or filtering failed

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

## Two-step workflow (advanced)

When you need the filtered OAS as a standalone file (e.g. to inspect it or reuse it
in CI), run `build_filtered_oas.py` first to produce `filtered-oas.yaml`, then pass
`--spec filtered-oas.yaml` directly (omit `--consumer-root`).

Full instructions, ripwire iteration guidance, type resolution tiers, and the
`--routes` fallback for unsupported HTTP clients →
[`references/advanced-workflow.md`](references/advanced-workflow.md).

**Critical:** never pass the original `openapi.yaml` without a filtering flag or
`--consumer-root`. Every unused provider endpoint appears as a false gap.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/parse_pact_coverage.py` | Coverage checker — single command happy path (use this first) |
| `scripts/build_filtered_oas.py` | Advanced: build consumer-filtered OAS as a standalone file |

Both are `uv` inline scripts (`uv run scripts/<name>.py`); dependencies install automatically.

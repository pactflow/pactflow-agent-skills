---
name: pact-coverage
description: >
  Checks how well existing Pact consumer tests cover an OpenAPI specification.
  Use when the user asks which API operations, status codes, request body required
  fields, or response body required fields are not exercised by their Pact tests.
  Trigger when the user asks "what's not covered by my pacts?", "which endpoints
  are missing pact tests?", "do my pact files cover the full spec?", "how complete
  is my pact coverage?", or "which required fields aren't tested in my pacts?".
  Also trigger when the user has pact.json files (Pact v4 format) and wants to
  measure contract test coverage against an OpenAPI spec.
  Do NOT trigger for running provider verification, publishing pacts to a broker,
  or checking can-i-deploy — use the pactflow skill for those.
argument-hint: "[./consumer-src path/to/openapi.yaml \"pacts/*.json\"]"
metadata:
  context: fork
  agent: general-purpose
---

# Pact Coverage Skill

This skill analyses Pact v4 `Synchronous/HTTP` interactions against an OpenAPI spec
and reports coverage gaps across four dimensions. It never modifies the spec or pact files.

---

## Step 1: Build Consumer Knowledge Graph (ripwire)

Before running the coverage script, use ripwire to map which API endpoints the
consumer codebase calls and which response types it reads. This produces the
_consumer-filtered_ OAS used in Step 3 — coverage gaps are measured only against
what the consumer actually uses, not the whole spec.

### Run ripwire iteratively

```bash
ripwire ./consumer-src --for="HTTP API route calls and response types" > kg.xml
```

Check the `confidence=` attribute on the root element of `kg.xml`:
- `confidence="high"` — ranking is sharp; proceed
- `confidence="low"` — ranking is flat; re-run with a more specific task or drill into individual symbols

**If `over_ceiling="1"` or any section has `capped="1"`:** the result was truncated. Re-run
with `--token-budget=<higher>` or narrow the consumer root path.

**Repeat until:** `confidence="high"` AND no `over_ceiling` AND no `capped` on the routes section.
Use at most 3 iterations before proceeding with the best result.

### What ripwire extracts

ripwire finds HTTP call sites in the consumer codebase and emits `<route>` elements.
`build_filtered_oas.py` then expands each calling function's body to find its return
type, fetches that type's field declarations, and uses **only the required fields**
(not optional ones — TypeScript `field?: T`, Python `field: T = default`) as the
response coverage denominator.

### Two-strategy discovery

`build_filtered_oas.py` runs two discovery strategies automatically:

**Strategy 1 — HTTP call site** (`fetch`, `axios.*`, `requests.*`):
Finds HTTP calls directly. When this succeeds, routes come with a `from=` function
pointer that is expanded to extract the return type.

**Strategy 2 — Response-type construction** (fallback, all HTTP clients):
When strategy 1 finds nothing (e.g. the consumer uses `aiohttp`, `net/http`, `HttpClient`),
the script scans function bodies for patterns like `TypeName(**data)`,
`TypeName.model_validate(data)`, or `resp.data as TypeName`. The URL path and HTTP method
are then extracted from the same function body. This strategy works regardless of which
HTTP client the consumer uses.

If both strategies return nothing, fall back to `--routes` (see Step 2).

---

## Step 2: Build Filtered OAS

Run `build_filtered_oas.py` to produce an OAS containing only the operations the
consumer calls, with `required[]` narrowed to the fields the consumer's response
types actually declare.

```bash
uv run scripts/build_filtered_oas.py \
  --spec openapi.yaml \
  --kg kg.xml \
  --consumer-root ./consumer-src \
  --output filtered-oas.yaml
```

The script resolves response types through four tiers:

| Tier | What it tries | Result |
|------|--------------|--------|
| 1 | Consumer return type name matches OAS schema name exactly | Consumer type's fields become `required[]` |
| 2 | Normalised name matches (strips `Response`, `Dto`, `I` prefix, etc.) | Same |
| 3 | Consumer type's fields structurally overlap an OAS schema (≥ 80%) | Consumer fields become `required[]` |
| 4 | No type link found | OAS `required[]` used as-is (conservative fallback) |

Exit code 1 means some operations used Tier 4 — check the summary for which ones.
The filtered OAS includes `x-consumer-type-match` annotations showing which tier was used.

**If `--consumer-root` is omitted:** type resolution is skipped (all Tier 4).
**If `--kg` is omitted:** the script runs ripwire itself using `--consumer-root`.

**Optional fields are excluded from the denominator.** If the consumer type declares
`items?: OrderItems` (TypeScript) or `items: list = []` (Python), `items` is not
counted as a required field — a pact test that omits it is not a gap. Only fields
declared without a default or `?` marker are required.

### When ripwire doesn't support the HTTP client

ripwire recognises `fetch`, `axios.*`, and `requests.*` calls. If the consumer
uses a different HTTP client (e.g. Python `aiohttp`, Go `net/http`, Java
`HttpClient`), ripwire returns 0 routes.

**Do not use the pact files as a substitute.** The filtered OAS is the
denominator that the pact file is checked against — deriving it from the pact
would be circular (100% path coverage by construction, no real gaps visible).

Instead, **read the consumer source code** and identify which endpoints it
calls, then supply them with `--routes`:

```bash
# Example: aiohttp consumer that calls GET /orders/{id} and POST /orders
uv run scripts/build_filtered_oas.py \
  --spec openapi.yaml \
  --routes '[{"method":"GET","path":"/orders/{id}"},{"method":"POST","path":"/orders"}]' \
  --output filtered-oas.yaml
```

This is a Tier 4 fallback — `required[]` fields are not narrowed (OAS values
used as-is) — but the filtered OAS still gives the correct path/method
denominator by excluding every provider endpoint the consumer doesn't use.

---

## Scripts

- `scripts/build_filtered_oas.py` — Filter an OAS to only consumer-called endpoints with
  `required[]` narrowed to consumer-declared response fields. Input for Step 3. Requires
  `pyyaml` (installed automatically via `uv`).
- `scripts/parse_pact_coverage.py` — Coverage checker: reads Pact v4 pact.json files and
  an OpenAPI spec, then reports which operations, status codes, required request body fields,
  and required response body fields are missing test coverage. Requires `pyyaml` (installed
  automatically via `uv`).

---

## Step 3: Run Coverage Check

`parse_pact_coverage.py` can filter the spec itself. Pass the consumer source root
with `--consumer-root` (or a pre-built `--kg` / manual `--consumer-routes`) and it
builds the filtered view internally — no intermediate `filtered-oas.yaml` file needed:

```bash
# Auto-filter via ripwire (single command)
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml \
  --pacts "path/to/pacts/*.json" \
  --consumer-root ./consumer-src

# Auto-filter from a pre-built KG
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml \
  --pacts "path/to/pacts/*.json" \
  --kg kg.xml

# Manual fallback (aiohttp / unsupported client)
uv run scripts/parse_pact_coverage.py \
  --spec openapi.yaml \
  --pacts "path/to/pacts/*.json" \
  --consumer-routes '[{"method":"GET","path":"/orders/{id}"},{"method":"POST","path":"/orders"}]'
```

**When a filtered OAS file is already on disk** (e.g. produced by Step 2), pass it
directly as `--spec` — that is equally correct and slightly faster:

```bash
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml \
  --pacts "path/to/pacts/*.json"

# Machine-readable output
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml \
  --pacts "path/to/pacts/*.json" \
  --json

# Exclude specific status codes (e.g. 500-503)
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml \
  --pacts "path/to/pacts/*.json" \
  --exclude-codes 500 501 502 503
```

**Critical:** never pass the original `openapi.yaml` without a filtering flag.
Doing so makes the denominator the entire provider spec — Section 1 shows `4/119`
instead of `4/4`, Section 4 shows `7/363` instead of `7/12`, and every provider
endpoint the consumer never calls appears as a gap.

**Exit codes:**
- `0` — full coverage (all four dimensions)
- `1` — gaps found
- `2` — error (bad spec, malformed pact JSON, or consumer-filtering returned no routes)

---

## What It Covers

The coverage report shows gaps across four dimensions:

### ① PATH / METHOD

The script checks whether each OpenAPI operation (method + path) is covered by at least one Pact interaction.

**Coverage rule:** An OAS operation is covered if ≥1 pact interaction matches that method and path template.

**When items are NOT COVERED:** An entire operation has no pact test.

**Recommended action:** Use the `pact-generator` agent to add at least one happy-path interaction for that operation.

### ② STATUS CODES

For covered operations, the script compares response status codes present in pact interactions against those documented in the OpenAPI spec.

**Coverage rule:** For each covered operation, every documented status code must appear in at least one pact interaction's response.

**Default exclusions:** 500, 501, 502, 503 (server errors requiring infrastructure or bugs; excluded by default).

**When items are NOT COVERED:** A documented status code has no pact test.

**Recommended action:**
- Add a pact interaction for each missing status code
- For 401/403: strip auth and test with an invalid or missing token
- For 404: use a guaranteed-nonexistent path

### ③ REQUEST BODY REQUIRED FIELDS

The script extracts the `required: [...]` list from the OpenAPI requestBody schema (resolving `$ref`, merging `allOf`, and taking the union of `anyOf`/`oneOf` branches). It then checks whether all top-level required keys are present in at least one pact interaction's request body content.

**Coverage rule:** All required fields declared in the OAS requestBody schema must appear as keys in at least one interaction's request body.

**Note:** A single interaction with all required fields satisfies this dimension — you do not need to repeat them across interactions.

**Note:** Matching rules in pact do not add fields to `body.content`; only actual request body payloads count.

**When items are NOT COVERED:** A required field is missing from all pact interactions.

**Recommended action:** Enrich an existing interaction's request body to include all required fields.

### ④ RESPONSE BODY REQUIRED FIELDS

Per (operation, status code) pair, the script extracts the `required: [...]` list from the OpenAPI response body schema and checks whether all top-level keys are present in at least one pact interaction's response body for that status code.

**Coverage rule:** For each (operation, status code), all required response fields declared in the OAS schema must appear as keys in at least one interaction's response body.

**When items are NOT COVERED:** A required response field is missing for a specific (operation, status code) combination.

**Recommended action:** Enrich an existing interaction's response body for that operation+status to include all required fields.

---

## Understanding Path Matching

Pact interactions contain concrete paths (e.g. `/orders/123`), while OpenAPI specs use path templates (e.g. `/orders/{id}`).

The script converts OAS path templates to regex patterns:
- `{param}` becomes `[^/]+` (matches any non-slash characters)
- Literal path segments match exactly

Example:
- OAS: `GET /orders/{orderId}/items/{itemId}` → regex `^/orders/[^/]+/items/[^/]+$`
- Pact: `GET /orders/123/items/456` → matches the regex ✓

Pact interactions with paths that do not match any OAS path template are silently ignored.

---

## Filling Coverage Gaps

After running the coverage script, use this table to determine the fix:

| Gap type | Recommended action |
|---|---|
| Entire operation not covered | Invoke the `pact-generator` agent to write a test for this operation |
| Missing status code | Add a pact interaction with the target status code; use the pactflow skill for provider state hints |
| Missing required request field | Enrich an existing interaction's request body with the missing field |
| Missing required response field | Enrich an existing interaction's response body for that status code with the missing field |

After adding or modifying interactions, re-run `parse_pact_coverage.py` to verify exit code 0.

---

## Limitations

- **Only Synchronous/HTTP interactions are checked.** `Asynchronous/Messages` and `Synchronous/Messages` interactions are skipped.
- **Top-level field coverage only.** Required field analysis checks only the top level of request and response bodies, not nested objects.
- **Conservative anyOf/oneOf interpretation.** When the schema contains `anyOf` or `oneOf`, the script takes the union of all `required` lists across branches. This may report more gaps than strictly necessary (because a conformant response could satisfy just one branch).
- **No value validation.** The script does not verify that pact body values conform to the OpenAPI schema (e.g. type correctness, enum membership, pattern matching). Use provider verification for that.
- **Required fields (Sections 3 and 4) are checked field-by-field across all matching interactions:** a field counts as covered if it appears in any interaction's body, not necessarily in a single interaction that includes all required fields at once.
- **Only 2xx and 4xx status codes from the spec are checked;** 3xx, 5xx, wildcard codes (`2XX`, `4XX`), and `default` responses are silently ignored. Use `--exclude-codes` to skip specific 2xx or 4xx codes (e.g. to omit 400 from checks).


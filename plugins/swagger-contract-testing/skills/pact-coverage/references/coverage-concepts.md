# Coverage Concepts

## What each dimension checks

### ① PATH / METHOD

Each OpenAPI operation (method + path combination) must be covered by at least one
Pact interaction. An operation is covered when ≥1 pact interaction matches that
method and path template.

**When NOT COVERED:** no interaction at all for that operation.  
**Fix:** Use the `pact-generator` agent to add a happy-path interaction.

### ② STATUS CODES

For every covered operation, each status code documented in the spec must appear in
at least one pact interaction's response.

**Default exclusions:** 500, 501, 502, 503. Override with `--exclude-codes`.  
**Only 2xx and 4xx codes are checked** — 3xx, 5xx, wildcard codes (`2XX`, `4XX`),
and `default` responses are silently ignored.

**When NOT COVERED:** a documented code has no pact test.  
**Fix:**
- 401/403: strip auth and test with an invalid or missing token
- 404: use a guaranteed-nonexistent path parameter

### ③ REQUEST BODY REQUIRED FIELDS

All top-level `required: [...]` fields from the OAS requestBody schema must appear
as keys in at least one pact interaction's request body content.

The script resolves `$ref`, merges `allOf`, and takes the union of `anyOf`/`oneOf`
branches (conservative — may over-report gaps when branches are disjoint).

**Note:** Matching rules in pact do not add fields to `body.content` — only actual
request body payloads count.

**When NOT COVERED:** a required field never appears in any interaction's request body.  
**Fix:** Enrich an existing interaction's request body to include the missing field.

### ④ RESPONSE BODY REQUIRED FIELDS

Per (operation, status code) pair, all top-level `required` fields from the OAS
response body schema must appear as keys in at least one matching pact interaction's
response body.

**When NOT COVERED:** a required response field is missing for a specific
(operation, status code) combination.  
**Fix:** Enrich an existing interaction's response body for that status.

### ⑤ CONSUMER CODE STATUS BRANCHES (optional)

When `--consumer-root` is passed to `parse_pact_coverage.py`, the script greps the consumer
source for explicit status-code checks (e.g. `response.status == 404`, `status(401)`) and
flags any status code the consumer branches on that isn't exercised in any pact interaction.

Supported file types: `.rb`, `.ts`, `.js`, `.py`, `.go`, `.java`, `.kt`.

**When NOT COVERED:** the consumer's source code contains `status == N` (or equivalent) but
no pact interaction tests that status code for the operation.

**Fix:** add a pact interaction for that status code or verify the branch is covered via a
provider state in provider verification.

**Note:** Section 5 findings do not affect the script's exit code.

---

## Schema quality warnings (⚠)

When an OAS requestBody or response schema has **properties defined but no `required: [...]`
array**, the script cannot measure field coverage (Sections 3/4 will show N/A for that
operation). Instead, it emits a ⚠ warning:

- Lists how many properties the OAS schema has
- Shows which fields the pact already sends (for request) or returns (for response)
- Lists which OAS properties are not yet in any pact
- Suggests adding `required:` to the schema

These warnings appear inline in the Section 3 / Section 4 output and do not affect the exit
code. To resolve: add a `required: [field1, field2, ...]` array to the OAS schema for the
fields that the consumer is expected to always provide or receive.

---

## Optional fields are never a gap

TypeScript `field?: T` and Python `field: T = default` are optional — the
consumer type doesn't always read them. The script excludes them from the
denominator, so a pact that omits an optional field is not a gap.

Only fields declared without a `?` marker or default value are required.

---

## Path matching: templates vs. concrete paths

Pact interactions contain concrete paths (e.g. `/orders/123`); OAS specs use
templates (e.g. `/orders/{id}`).

The script converts templates to regexes:
- `{param}` → `[^/]+` (any non-slash characters)
- Literal segments match exactly

```
OAS:  GET /orders/{orderId}/items/{itemId}
      → regex ^/orders/[^/]+/items/[^/]+$
Pact: GET /orders/123/items/456  ✓
```

Pact interactions with paths that match no OAS template are silently ignored.

---

## Limitations

- **Top-level field coverage only.** Required field analysis does not recurse into
  nested objects.
- **Conservative anyOf/oneOf interpretation.** The script takes the union of all
  `required` lists across branches, which may report more gaps than strictly
  necessary when a conformant response only needs to satisfy one branch.
- **No value validation.** The script does not check that body values conform to the
  OAS schema (type, enum, pattern). Use provider verification for that.
- **Field coverage across interactions.** A field counts as covered if it appears in
  any matching interaction's body — it does not need to appear in one single
  interaction that has all required fields at once.
- **Section 5 is grep-based.** Consumer code status branch detection uses a regex
  pattern (`\bstatus\b[\s=!<>]*[\s(]*(\d{3})\b`) and may produce false positives
  (e.g. a constant defined as `MAX_STATUS = 200`) or miss branches expressed through
  variables. Treat Section 5 output as advisory.
- **Pact v2/v3/v4 detection is per-interaction.** Interactions with `type =
  "Synchronous/HTTP"` are treated as v4 (body under `content` key); interactions
  with no `type` field are treated as v2/v3 (body is inline JSON). Non-HTTP
  interactions (e.g. `Asynchronous/Messages`) are silently skipped.

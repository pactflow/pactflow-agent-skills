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

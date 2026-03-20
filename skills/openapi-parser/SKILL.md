---
name: openapi-parser
description: >
  Parses complex OpenAPI specs and generates Drift test cases from them.
  Use whenever the user wants to generate, write, or scaffold Drift tests
  from an OpenAPI spec — especially when the spec contains complex schemas:
  anyOf/oneOf/allOf, discriminators, polymorphism, inheritance, $ref chains, regex
  patterns, enums, or optional fields. Use when the user asks to "create tests
  for an endpoint", "cover all response variants", "generate test cases from the spec",
  or says anything like "each viable combination of responses". Use when the
  user is trying to understand what values are valid for a complex schema field, or
  when they paste a spec path and ask what tests to write.

argument-hint: "[path/to/openapi-spec.yaml]"
metadata:
  context: fork
  agent: general-purpose
---

# OpenAPI Parser Skill

## Reference files

- [`references/schema-patterns.md`](references/schema-patterns.md) — how to interpret and enumerate every complex pattern
  (anyOf / oneOf / allOf / discriminator / $ref / enum / pattern / nullable / optional),
  with real examples from snyk, digitalocean, posthog, and front/core specs
- [`references/drift-mapping.md`](references/drift-mapping.md) — how to map enumerated schema variants to Drift YAML,
  including datasets, expressions, lifecycle hooks for stateful cases, and expected
  response matchers for each pattern type

## Workflow

> **OpenAPI version:** This skill targets OpenAPI 3.x. Swagger 2.0 specs use the same structural patterns (`$ref`, `allOf`, `oneOf`) but different envelope syntax — you may need to adapt field names manually.
> If working from the `konfig-sdks/openapi-examples` collection, see [`references/example-repos.md`](references/example-repos.md) for navigation commands.

### 1. Locate the endpoint

Extract only what's needed:

```bash
# Find the line number of the endpoint (macOS/Linux/Git Bash/WSL)
grep -n "^  /path/to/endpoint" spec.yaml

# Read just that block (adjust line range as needed)
# Then follow each $ref to components/schemas
grep -n "SchemaName:" spec.yaml
```

```powershell
# PowerShell equivalents (Windows)
Select-String -Path spec.yaml -Pattern "^  /path/to/endpoint" | Select-Object LineNumber, Line
Select-String -Path spec.yaml -Pattern "SchemaName:" | Select-Object LineNumber, Line
```

Extract: path/query/header parameters, request body schema, and each response status code's schema.

### 2. Resolve $refs recursively

1. Grep for `Foo:` in the spec to find its definition block
2. If Foo itself contains refs, resolve those too
3. Stop at primitive types (`string`, `integer`, `boolean`, `array`, `object`)

`allOf: [$ref: Base, properties: {...}]` is inheritance — merge Base fields with local
properties to get the full schema. See `references/schema-patterns.md` for all patterns.

### 3. Enumerate viable combinations

For **each response status code**, enumerate structurally distinct schema variants. Aim for minimum tests that maximise schema coverage — not a combinatorial explosion of optional field permutations.

| Pattern                               | Tests to generate                                                          |
| ------------------------------------- | -------------------------------------------------------------------------- |
| `oneOf` / `anyOf` with N branches     | N tests — one per branch                                                   |
| `discriminator` with N mapping values | N tests — one per discriminator value                                      |
| `allOf` (composition / inheritance)   | 1 test — merge all schemas into one payload                                |
| `enum`                                | 1 test covers it; add boundary variants only if the value drives behaviour |
| Optional field cluster                | 2 tests: one with all optional fields, one without                         |
| `nullable` field                      | Covered by happy path; add null variant only if it changes behaviour       |
| `pattern` (regex)                     | 1 valid example matching the pattern; 1 invalid for negative testing       |

### 4. Generate Drift test cases

For each combination produce a Drift operation block. See `references/drift-mapping.md`
for full patterns. Key conventions:

- Name operations as `{operationId}_{variant}` — e.g. `getImage_byId`, `getImage_bySlug`
- For discriminated unions, set the discriminator property explicitly in the request body
- For `anyOf` path parameters, write one test per type variant
- Use `dataset` for test data; use inline `parameters` only for static, non-variant values (e.g. a fixed enum query param like `type: user`)
- For 401 tests, strip global auth with `exclude: [auth]` and pass an invalid bearer token explicitly
- Add `ignore: { schema: true }` to any operation that sends an intentionally invalid request body
- Tag each test to indicate which schema branch it covers
- Omitting `body` from `expected` lets Drift validate the response against the OpenAPI schema automatically; add explicit `body` matchers only when asserting a specific field value (e.g. the discriminator property came back correctly)

### 5. Output format

Always produce:

1. **Analysis** — number of status codes, which schemas are polymorphic, how many tests
   will be generated and why
2. **Drift operations YAML** — the complete `operations:` block, ready to paste
3. **Dataset YAML** (if needed) — the `datasets:` block for any referenced test data
4. **Gaps** — schema combinations intentionally excluded, with the reason

### Example

Given `GET /v2/images/{image_id}` where `image_id: anyOf: [integer, string]`:

```yaml
operations:
  getImage_byId:
    target: source-oas:getImage
    tags: [images, param-integer]
    parameters:
      path:
        image_id: ${image-data:images.existing.id}
    expected:
      response:
        statusCode: 200

  getImage_bySlug:
    target: source-oas:getImage
    tags: [images, param-string]
    parameters:
      path:
        image_id: ${image-data:images.existing.slug}
    expected:
      response:
        statusCode: 200

  getImage_notFound:
    target: source-oas:getImage
    parameters:
      path:
        image_id: ${image-data:notIn(images.*.id)}
    expected:
      response:
        statusCode: 404
```


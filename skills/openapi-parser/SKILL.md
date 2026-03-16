---
name: openapi-parser
description: >
  Expert at parsing complex OpenAPI specs and generating Drift test cases from them.
  Use this skill whenever the user wants to generate, write, or scaffold Drift tests
  from an OpenAPI spec — especially when the spec contains complex schemas:
  anyOf/oneOf/allOf, discriminators, polymorphism, inheritance, $ref chains, regex
  patterns, enums, or optional fields. Trigger when the user asks to "create tests
  for an endpoint", "cover all response variants", "generate test cases from the spec",
  or says anything like "each viable combination of responses". Also trigger when the
  user is trying to understand what values are valid for a complex schema field, or
  when they paste a spec path and ask what tests to write. Works alongside the Drift
  skill — this skill handles spec analysis and test case generation; Drift handles
  running and iterating on them.
---

# OpenAPI Parser Skill

Parses complex OpenAPI specs — including those with polymorphism, discriminated unions,
deep `$ref` chains, enums, regex patterns, and optional fields — and generates Drift
test cases that cover each viable schema combination.

## Reference files

Read these when you need deeper detail:

- `references/schema-patterns.md` — how to interpret and enumerate every complex pattern
  (anyOf / oneOf / allOf / discriminator / $ref / enum / pattern / nullable / optional),
  with real examples from snyk, digitalocean, posthog, and front/core specs
- `references/drift-mapping.md` — how to map enumerated schema variants to Drift YAML,
  including datasets, expressions, lifecycle hooks for stateful cases, and expected
  response matchers for each pattern type

## Workflow

### 1. Locate the endpoint

Large specs (40k–70k+ lines) cannot be read in full. Extract only what's needed:

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

Extract: path/query/header parameters, request body schema, and each response status
code's schema. Resolve every `$ref` before analysing — see step 2.

### 2. Resolve $refs recursively

`$ref: '#/components/schemas/Foo'` means Foo's definition substitutes inline.

1. Grep for `Foo:` in the spec to find its definition block
2. If Foo itself contains refs, resolve those too
3. Stop at primitive types (`string`, `integer`, `boolean`, `array`, `object`)

`allOf: [$ref: Base, properties: {...}]` is inheritance — merge Base fields with local
properties to get the full schema. See `references/schema-patterns.md` for all patterns.

### 3. Enumerate viable combinations

For **each response status code**, identify how many distinct schema variants exist.
The key principle:

> A "viable combination" is one structurally distinct payload the server could legally
> return. Aim for minimum tests that maximise schema coverage — not a combinatorial
> explosion of optional field permutations.

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
- Use `dataset` for test data; use inline `parameters` only for trivial cases
- Tag each test to indicate which schema branch it covers

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
    tags: [images, param-variant-integer]
    parameters:
      path:
        image_id: ${image-data:images.byId.id}
    expected:
      response:
        statusCode: 200

  getImage_bySlug:
    target: source-oas:getImage
    tags: [images, param-variant-string]
    parameters:
      path:
        image_id: ${image-data:images.bySlug.slug}
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

## Working with konfig-sdks/openapi-examples

Specs live at `<repo-root>/<provider>/openapi.yaml` (sometimes nested, e.g.
`atlassian/jira/openapi.yaml`). The most complex specs — all five patterns simultaneously
— are: `snyk`, `digitalocean`, `posthog`, `front/core`.

```bash
# List all endpoints in a spec (macOS/Linux/Git Bash/WSL)
grep "^  /" spec.yaml

# Find endpoints with polymorphic schemas
grep -n "oneOf\|anyOf\|discriminator" spec.yaml

# Find specs using all five complexity patterns
for f in $(find . -name "openapi.yaml"); do
  score=0
  grep -q "anyOf" "$f" && score=$((score+1))
  grep -q "oneOf" "$f" && score=$((score+1))
  grep -q "allOf" "$f" && score=$((score+1))
  grep -q "discriminator" "$f" && score=$((score+1))
  grep -q "pattern:" "$f" && score=$((score+1))
  [ $score -ge 4 ] && echo "$score $f"
done | sort -rn
```

```powershell
# PowerShell equivalents (Windows)

# List all endpoints in a spec
Select-String -Path spec.yaml -Pattern "^  /" | Select-Object -ExpandProperty Line

# Find endpoints with polymorphic schemas
Select-String -Path spec.yaml -Pattern "oneOf|anyOf|discriminator" | Select-Object LineNumber, Line

# Find specs using all five complexity patterns
Get-ChildItem -Recurse -Filter "openapi.yaml" | ForEach-Object {
  $f = $_.FullName
  $score = 0
  if (Select-String -Path $f -Pattern "anyOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "oneOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "allOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "discriminator" -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "pattern:"     -Quiet) { $score++ }
  if ($score -ge 4) { "$score $f" }
} | Sort-Object -Descending
```

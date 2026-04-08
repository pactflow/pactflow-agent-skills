# Schema Patterns Reference

How to interpret and enumerate each complex OpenAPI schema pattern, with real examples
from the konfig-sdks/openapi-examples collection.

---

## Table of contents

- [oneOf](#oneof)
- [anyOf](#anyof)
- [allOf](#allof)
- [discriminator](#discriminator)
- [$ref resolution](#ref-resolution)
- [enum](#enum)
- [pattern (regex)](#pattern-regex)
- [nullable and optional fields](#nullable-and-optional-fields)
- [Nested / combined patterns](#nested--combined-patterns)
- [Determining test count](#determining-test-count)

---

## oneOf

**Semantics**: exactly one of the listed schemas is valid. Mutually exclusive variants.

**How many tests**: one per branch.

**Real example** — Snyk `RiskFactor`:

```yaml
RiskFactor:
  discriminator:
    mapping:
      deployed: "#/components/schemas/DeployedRiskFactor"
      os_condition: "#/components/schemas/OSConditionRiskFactor"
      public_facing: "#/components/schemas/PublicFacingRiskFactor"
    propertyName: name
  oneOf:
    - $ref: "#/components/schemas/DeployedRiskFactor"
    - $ref: "#/components/schemas/OSConditionRiskFactor"
    - $ref: "#/components/schemas/PublicFacingRiskFactor"
```

Resolve each ref and write one test per branch. Where a `discriminator` is present (as
here), set the discriminator property (`name`) to the mapping key for that branch.

**Enumeration**:

- Branch 1 → `DeployedRiskFactor`, `name: "deployed"`
- Branch 2 → `OSConditionRiskFactor`, `name: "os_condition"`
- Branch 3 → `PublicFacingRiskFactor`, `name: "public_facing"`

---

## anyOf

**Semantics**: one or more of the listed schemas is valid. Less strict than `oneOf` —
schemas can overlap. In practice, treat each branch as a separate variant for test
coverage unless the branches are clearly additive.

**Special case — primitive type union**: Very common for parameters:

```yaml
image_id:
  anyOf:
    - type: integer
    - type: string
```

Write one test per type variant (one sending an integer, one sending a string).

**Special case — ref union** (response can be one of several resource types):

```yaml
result:
  anyOf:
    - $ref: "#/components/schemas/ResourcePathRepresentation"
    - $ref: "#/components/schemas/PackageRepresentation"
```

Write one test per ref, constructing a payload that matches only that schema.

**When branches share fields**: If branches differ only in optional fields, two tests
are enough — one with the minimal schema, one with all optional fields present.

---

## allOf

**Semantics**: all listed schemas must be satisfied simultaneously. This is OpenAPI's
primary mechanism for inheritance and schema composition — not branching.

**How many tests**: typically 1. Merge all referenced schemas into a single combined
object and write one test with the full merged payload.

**Inheritance pattern**:

```yaml
DigitalDroplet:
  allOf:
    - $ref: "#/components/schemas/BaseResource" # id, created_at, status
    - properties:
        name:
          type: string
        size:
          $ref: "#/components/schemas/DropletSize"
      required: [name, size]
```

The full schema is BaseResource fields + `name` + `size`. One test covering all required
fields is sufficient unless the inherited base has its own `oneOf`/`anyOf` inside it
(in which case enumerate those independently).

**Mixin pattern** (multiple allOf refs, all required):

```yaml
CreateDropletRequest:
  allOf:
    - $ref: "#/components/schemas/DropletBase"
    - $ref: "#/components/schemas/NetworkConfig"
    - $ref: "#/components/schemas/StorageConfig"
```

Resolve all three, merge their required fields, write one test.

---

## discriminator

**Semantics**: an explicit property value tells you which branch of a `oneOf`/`anyOf`
applies. Provides a clean enumeration — one test per mapping entry.

**Structure**:

```yaml
discriminator:
  propertyName: type # the field whose value selects the branch
  mapping:
    circle: "#/components/schemas/Circle"
    rectangle: "#/components/schemas/Rectangle"
    triangle: "#/components/schemas/Triangle"
oneOf:
  - $ref: "#/components/schemas/Circle"
  - $ref: "#/components/schemas/Rectangle"
  - $ref: "#/components/schemas/Triangle"
```

**Enumeration**: for each key in `mapping`, resolve the target schema and write one test where `type` equals that key.

**When `mapping` is absent**: the discriminator property value is the schema name itself.

```yaml
discriminator:
  propertyName: animal_type
# implies mapping: {Dog: Dog, Cat: Cat, Bird: Bird}
oneOf:
  - $ref: "#/components/schemas/Dog"
  - $ref: "#/components/schemas/Cat"
  - $ref: "#/components/schemas/Bird"
```

**Snyk real-world example** — `RiskFactor` with three factor types:
Tests should include `name: "deployed"`, `name: "os_condition"`, `name: "public_facing"`
respectively, each with the fields required by that variant's resolved schema.

---

## $ref resolution

`$ref: '#/components/schemas/Foo'` is a pointer — substitute it with the full definition
of `Foo`. This is recursive: `Foo` may itself contain `$ref`s.

**Extraction strategy for large files**:

```bash
# Step 1: find the schema definition line
grep -n "^  Foo:" spec.yaml        # top-level component
grep -n "^    Foo:" spec.yaml      # nested under a key

# Step 2: read from that line until the next peer-level key
# (look for the next line that starts at the same indentation level)
```

**Circular refs**: occasionally specs have `$ref` cycles (e.g. a `Comment` schema
that contains `replies: [Comment]`). Stop resolving when you hit a type you've already
resolved in the current chain — just note it as "recursive/self-referential".

**External refs** (`$ref: './schemas/foo.yaml'` or `$ref: 'https://...'`):

- Local file refs: read the referenced file from the same directory
- Remote refs: fetch the URL if needed, or note it as an unresolvable external dependency

---

## enum

```yaml
status:
  type: string
  enum: [pending, active, suspended, deleted]
```

**How many tests**: usually one — pick the most common/default value. Add additional
tests when the enum value drives meaningfully different behaviour:

- A `status` filter parameter that returns different data shapes per value → one test per value
- A `format` parameter that changes the response content-type → one test per format
- A `type` discriminator (see above) → covered under discriminator rules

**Enum in response**: validate the enum field in the `expected.body` matcher.

---

## pattern (regex)

```yaml
id:
  type: string
  pattern: "^[a-z]{2,4}-[0-9]{6}$" # e.g. "ab-123456"
```

**What to do**:

1. Construct one valid example that satisfies the pattern. Use the simplest string that
   matches — avoid creative interpretations that could pass locally but fail validation.
2. For negative testing, construct one string that intentionally violates the pattern
   (wrong format, wrong length) and expect a 400/422 response.

**Common patterns and valid examples**:
| Pattern | Example |
|---|---|
| `^[a-z0-9-]+$` | `"hello-world"` |
| `^\d{4}-\d{2}-\d{2}$` | `"2024-01-15"` |
| `^[A-Z]{2}[0-9]{6}$` | `"AB123456"` |
| UUID `^[0-9a-f]{8}-...$` | Use `${functions:generate_uuid}` in Drift |
| ISO 8601 datetime | `"2024-01-15T10:30:00Z"` |

**`minLength` / `maxLength`**: pick a value in the middle of the range for happy-path;
test at exactly `minLength` and `maxLength` only if boundary behaviour matters.

---

## nullable and optional fields

### nullable

A field that can be `null` in addition to its normal type:

```yaml
# OpenAPI 3.0 style
middle_name:
  type: string
  nullable: true

# OpenAPI 3.1 style
middle_name:
  type: [string, 'null']
```

**How many tests**: cover `null` as a separate variant only when it drives different
behaviour (e.g. a nullable `parent_id` that makes the resource a root node vs. a child).
Otherwise include it in the happy-path test as an optional field.

### optional fields

**How many tests**: 2 per meaningful optional cluster:

- One test with all optional fields included (validates the server accepts and returns them)
- One test with no optional fields (validates the server works without them)

Avoid testing every permutation of individual optional fields — group into a "with extras" / "minimal" pair unless a specific field changes behaviour.

**Required-field violations** (negative testing):

```yaml
operations:
  createFoo_missingRequired:
    target: source-oas:createFoo
    parameters:
      request:
        body:
          optional_field_only: "value" # omit required fields
    ignore:
      schema: true # suppress Drift schema validation on the bad request
    expected:
      response:
        statusCode: 400
```

---

## Nested / combined patterns

Work from the outside in:

**Example** — DigitalOcean droplet create response:

```yaml
CreateDropletResponse:
  oneOf:
    - $ref: "#/components/schemas/SingleDroplet" # returns one droplet
    - $ref: "#/components/schemas/MultipleDroplets" # returns an array
```

Where `SingleDroplet` itself is:

```yaml
SingleDroplet:
  allOf:
    - $ref: "#/components/schemas/DropletBase"
    - properties:
        networks:
          anyOf:
            - $ref: "#/components/schemas/IPv4Networks"
            - $ref: "#/components/schemas/IPv6Networks"
```

Resolution order:

1. Outer `oneOf` → 2 tests (single vs. multiple)
2. For the single-droplet branch, the `allOf` is composition → merge `DropletBase` + properties
3. The `networks` `anyOf` inside → 2 sub-variants (IPv4, IPv6) within the single-droplet test

Total: 3 tests — single/IPv4, single/IPv6, multiple. The multiple-droplet test doesn't
need network variants unless the array element schema also has that `anyOf`.

**Rule of thumb**: enumerate branching patterns (`oneOf`, `anyOf`, `discriminator`)
independently. For each branch, resolve `allOf` compositions. Only recurse into nested
`oneOf`/`anyOf` if the nesting adds a structurally distinct payload shape.

---

## Determining test count

Before writing any YAML, produce this analysis for each endpoint:

```
GET /orgs/{org_id}/issues
  Path params:
    - org_id: string (no variants)
  Query params:
    - version: string, pattern ^\d{4}-\d{2}-\d{2}$ (1 valid, 1 invalid)
    - type: enum [issue, vulnerability] (1 test; same response shape)

  Responses:
    200:
      IssueList → data[]: IssueItem
      IssueItem → oneOf [SnykCodeIssue, SnykOpenSourceIssue, SnykIacIssue]  (3 variants)
    400: ErrorDocument  (2 tests — invalid version format + missing required param)
    401: ErrorDocument  (1 test — no auth)
    404: ErrorDocument  (1 test — invalid org_id)

  Total tests: 3 (200 variants) + 2 (400: invalid version + missing param) + 1 (401) + 1 (404) = 7
```

Output this analysis before any YAML.

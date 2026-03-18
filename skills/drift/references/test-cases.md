# Drift Test Cases — Full Reference

## Contents

- [File Structure](#file-structure)
- [Targeting Operations](#targeting-operations)
- [Full Operation Schema](#full-operation-schema)
- [Common Patterns](#common-patterns)
- [Tags](#tags)
- [Stateful Operations](#stateful-operations)
- [Datasets](#datasets)
- [Expressions](#expressions)

---

## File Structure

```yaml
# yaml-language-server: $schema=https://download.pactflow.io/drift/schemas/drift.testcases.v1.schema.json
drift-testcase-file: v1 # Required. Must be literal "v1".
title: "My API Tests" # Optional. Descriptive suite name.

sources:
  - name: source-oas # Unique identifier — used in target: and expressions
    path: ./openapi.yaml # Local path
    # uri: https://...           # OR remote URL
    # auth:                      # Optional remote auth
    #   username: user
    #   secret: ${env:DATA_SECRET}
  - name: product-data
    path: ./product.dataset.yaml
  - name: functions
    path: ./product.lua

plugins:
  - name: oas # OpenAPI plugin (required for spec-first)
  - name: json # JSON validation
  - name: data # Dataset support
  - name: http-dump # Optional: log HTTP traffic for debugging
  - name: junit-output # Optional: JUnit XML reports for CI

global: # Applied to ALL operations unless excluded
  auth:
    apply: true
    parameters:
      authentication:
        scheme: bearer # bearer | basic | api-key
        token: ${env:API_TOKEN}
        # For api-key scheme:
        # header: X-API-Key
        # token: ${env:API_KEY}

operations:
  operationName: # Unique key — used with --operation flag
    target: source-oas:operationId
    # ... see patterns below
```

---

## Targeting Operations

### By operationId (preferred)

```yaml
target: source-oas:getAllProducts
```

### By method + path (when no operationId)

```yaml
target: source-oas:get:/products/{id}
target: source-oas:post:/products
```

### Pact interactions (by description)

```yaml
target: my-pact:a request to get a product
```

---

## Full Operation Schema

```yaml
operations:
  exampleOperation:
    target: source-oas:operationId # Required
    description: "Human readable" # Optional — supports expressions
    tags: # Optional — for --tags filtering
      - smoke
      - products
    dataset:
      product-data # Optional — declares dataset in scope
      # (must match name inside dataset file)
    exclude: # Strip named global config blocks
      - auth
    include: # Activate optional global blocks
      - extra-headers
    parameters:
      path:
        id: 10
        slug: "my-product"
      query:
        format: json
        page: 1
      headers:
        authorization: "Bearer ${functions:token}"
        x-custom: value
      request:
        body: ${product-data:products.newProduct}
      ignore:
        schema: true # Suppress request schema validation errors
    expected:
      response:
        statusCode: 200
        body: ${equalTo(product-data:products.newProduct)}
```

---

## Common Patterns

### Happy path — minimal

```yaml
getAllProducts_Success:
  target: source-oas:getAllProducts
  expected:
    response:
      statusCode: 200
```

Drift auto-reads the request schema and uses the first OpenAPI example as the body.

### Happy path — with dataset body

```yaml
createProduct_Success:
  target: source-oas:createProduct
  dataset: product-data
  parameters:
    request:
      body: ${product-data:products.newProduct}
  expected:
    response:
      statusCode: 201
      body: ${equalTo(product-data:products.newProduct)}
```

### 401 — exclude auth, send bad token

```yaml
createProduct_Unauthorized:
  target: source-oas:createProduct
  exclude:
    - auth
  parameters:
    headers:
      authorization: "Bearer invalid-token"
    request:
      body:
        name: "test"
  expected:
    response:
      statusCode: 401
```

### 403 — authenticated but insufficient permissions

```yaml
deleteProduct_Forbidden:
  target: source-oas:deleteProduct
  parameters:
    headers:
      authorization: "Bearer ${functions:readonly_token}"
    path:
      id: 10
  expected:
    response:
      statusCode: 403
```

### 404 — guaranteed non-existent ID

```yaml
getProductByID_NotFound:
  target: source-oas:getProductByID
  dataset: product-data
  parameters:
    path:
      id: ${product-data:notIn(products.*.id)}
  expected:
    response:
      statusCode: 404
```

### 400 — invalid input, suppress schema validation

```yaml
getProductByID_InvalidID:
  target: source-oas:getProductByID
  parameters:
    path:
      id: "invalid-not-a-number"
    ignore:
      schema: true
  expected:
    response:
      statusCode: 400
```

### 400 — missing required field

```yaml
createProduct_MissingRequired:
  target: source-oas:createProduct
  parameters:
    request:
      body:
        price: 9.99 # intentionally omitting required fields
    ignore:
      schema: true
  expected:
    response:
      statusCode: 400
```

### Using OpenAPI spec metadata as values

```yaml
getProduct_WithSpecExample:
  target: source-oas:getProductByID
  parameters:
    path:
      id: ${source-oas:operation.parameters.id.example}
  expected:
    response:
      statusCode: 200
```

Available metadata: `tags`, `summary`, `description`, `operationId`,
`parameters.<name>.example`, `parameters.<name>.examples`, `deprecated`, `extensions` (via `ext`)

---

## Tags

```yaml
# Add tags to operations
operations:
  getAllProducts_Success:
    tags: [smoke, read-only, products]

# Run by tag
drift verify -f drift.yaml -u https://... --tags smoke
drift verify -f drift.yaml -u https://... --tags products,write   # OR logic
drift verify -f drift.yaml -u https://... --tags '!security'      # exclude
```

Common tag strategies:

- **Functional**: `products`, `users`, `orders`
- **Test type**: `smoke`, `regression`, `integration`
- **Stability**: `stable`, `flaky`
- **Concern**: `security`, `validation`, `auth`
- **Mutation**: `read-only`, `write`, `destructive`

---

## Stateful Operations

When an operation requires pre-existing data (e.g., deleting a resource), use lifecycle hooks
instead of hoping the data exists. See `lua-api.md` for full hook documentation.

| Scenario                         | Approach                    |
| -------------------------------- | --------------------------- |
| Stateless / read-only            | Declarative test, no hooks  |
| Stable test data exists          | Dataset expressions         |
| Must create data before test     | `operation:started` hook    |
| Must clean up after test         | `operation:finished` hook   |
| Dynamic values (UUID, timestamp) | `exported_functions` in Lua |
| Guaranteed missing ID            | `${notIn(...)}` expression  |

---

## Datasets

Datasets decouple test logic from test data. Define them in a separate YAML file and
reference values with dot-notation expressions.

```yaml
# my-api.dataset.yaml
drift-dataset-file: V1
datasets:
  - name: product-data # used in ${product-data:...}
    data:
      products:
        existing:
          id: 10
          name: "cola"
          price: 10.99
        new:
          id: 25
          name: "chips"
          price: 5.49
      orgs:
        existing: { id: "59d6d97e-3106-4ebb-b608-352fad9c5b34" }
        forbidden: { id: "00000000-0000-0000-0000-000000000001" }
```

Register the dataset as a source in `drift.yaml`:

```yaml
sources:
  - name: product-data
    path: ./my-api.dataset.yaml
```

Reference in an operation — the `dataset` field must match the `name` inside the dataset file:

```yaml
getProduct_Success:
  target: source-oas:getProductByID
  dataset: product-data # activates expressions for this dataset
  parameters:
    path:
      id: ${product-data:products.existing.id}
```

**Naming convention** — organise by resource, then by role. This prevents key collisions in
large datasets and makes expressions readable at a glance:

```yaml
data:
  orgs:
    existing: { id: "..." } # the org you own
    forbidden: { id: "..." } # an org the token cannot access (for 403 tests)
  projects:
    existing: { id: "...", org_id: "..." }
    toDelete: { id: "..." } # DISPOSABLE — throwaway resource only
  invites:
    new: { email: "test@example.com", role_id: "..." }
    existing: { id: "..." } # a pending invite (for cancel tests)
```

---

## Expressions

Expressions inject dynamic values anywhere a string is accepted (except file headers,
operation keys, and tags).

| Syntax                                              | Example                                       | Purpose                       |
| --------------------------------------------------- | --------------------------------------------- | ----------------------------- |
| `${env:VAR}`                                        | `${env:API_TOKEN}`                            | Environment variable          |
| `${dataset-name:path}`                              | `${product-data:products.existing.id}`        | Dataset value                 |
| `${functions:fn_name}`                              | `${functions:generate_uuid}`                  | Call a Lua exported function  |
| `${source-name:operation.parameters.field.example}` | `${api-spec:operation.parameters.id.example}` | Value from OpenAPI spec       |
| `${notIn(path)}`                                    | `${product-data:notIn(products.*.id)}`        | Generate value NOT in dataset |

Use glob `*` to reference all items: `${product-data:products.*}` or `${product-data:products.*.id}`

**Execution order:** sources → descriptions → datasets → parameters/expected. You cannot
reference a later-resolved field from an earlier stage.

**`notIn()` and UUID IDs:** `${dataset:notIn(path.*.id)}` generates an integer value not in
the dataset. For UUID-format IDs, use a nil UUID instead — it is always non-existent and
format-valid:

```yaml
org_id: "00000000-0000-0000-0000-000000000000"
```

For IDs with custom `pattern` constraints (e.g. `^sha256:[a-f0-9]{64}$`), the nil UUID won't
satisfy the pattern. Use a correctly-formatted but non-existent value:

```yaml
image_id: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
```

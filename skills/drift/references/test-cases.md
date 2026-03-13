# Drift Test Cases — Full Reference

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

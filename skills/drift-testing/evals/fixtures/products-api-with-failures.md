# Failing Drift Test

## Spec

The API is described in `evals/fixtures/simple-products-api.yaml`.

## Test configuration (drift.yaml excerpt)

```yaml
getProduct_Success:
  target: source-oas:getProduct
  parameters:
    path:
      id: 10
  expected:
    response:
      statusCode: 200
```

## Failure output

```
FAIL  getProduct_Success
  Expected status: 200
  Received status: 404
  GET /products/10 → 404 Not Found
```

The test is running against a clean test environment with an empty database.
The product with id 10 does not exist until it is explicitly created.

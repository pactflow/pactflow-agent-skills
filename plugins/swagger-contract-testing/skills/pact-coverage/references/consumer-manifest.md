# Consumer discovery manifest (1.0.0)

Discovery (the agent, using ripwire / codebase-memory / graphify / plain search) writes this file for one
commit. `scripts/consumer_coverage.py` calculates coverage from it with no further code analysis, so the
same commit always gives the same artifact. **Never put code snippets or function bodies in it.**

```json
{
  "manifestVersion": "1.0.0",
  "tool": "ripwire",
  "commit": "9f2c1ab",
  "consumer": { "name": "checkout-web", "repository": "github.com/example/checkout-web" },
  "provider": { "name": "product-api" },
  "calls": [
    {
      "method": "GET",
      "path": "/products/{id}",
      "callSite": { "file": "src/api/products.ts", "line": 14, "symbol": "getProduct", "hash": "c0ffee01a1b2c3d4" },
      "successStatus": "200",
      "handledStatuses": ["404"],
      "handlers": [{ "file": "src/api/products.ts", "line": 21, "symbol": "getProduct" }],
      "nearestTest": { "file": "tests/products.pact.test.ts", "line": 10, "symbol": "get product" },
      "inputs": {
        "parameters": [{ "name": "category", "in": "query", "values": ["books", "games"] }],
        "body": [{ "name": "quantity" }]
      },
      "responseFields": { "200": ["id", "price.amount"], "404": ["message"] }
    },
    { "unresolvedReason": "URL built from a runtime string", "callSite": { "file": "src/x.ts", "line": 5 } }
  ],
  "tests": { "<pact interaction description>": { "file": "tests/x.test.ts", "line": 30, "symbol": "..." } }
}
```

Rules for discovery:

| Field | Rule |
|-------|------|
| `path` | The path template built in the code (`/products/{id}`), not a concrete URL. |
| `successStatus` | Omit if the code does not pin one; coverage then treats any 2xx as the success response (or uses the spec's lowest 2xx). |
| `handledStatuses` | Only statuses checked **in the code that handles this call** (the handler/wrapper), never repo-wide. 5xx/3xx may be listed; they are reported as Excluded. |
| `inputs.*.values` | Only values the code genuinely varies, taken from its types (enums, unions). Omit `values` for free-form inputs. More than 5 values are cut (large-enum limit). |
| `responseFields` | Fields the code reads. A `oneOf` variant's fields are listed only once the code reaches that variant (its discriminator check). Keys: a status, or `2XX`/`success` for the success response. |
| `hash` | Optional. Hash of the call (never its source). Computed from file + symbol when absent. |
| `unresolvedReason` | Set when the target operation cannot be worked out. The call is listed as unresolved, never dropped. |

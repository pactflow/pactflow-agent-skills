# Local Testing with a Mock Server (Prism)

When you don't have a live server, [Prism](https://stoplight.io/open-source/prism) serves a
mock API directly from the OpenAPI spec. This lets you run the full Drift feedback loop
locally — no backend needed.

## Setup

```bash
# Install Prism
npm install -g @stoplight/prism-cli

# Start the mock server
prism mock ./openapi.yaml
# Listening on http://localhost:4010 by default

# Point Drift at it
drift verifier --test-files drift.yaml --server-url http://localhost:4010
```

---

## Forcing HTTP status codes with `Prefer`

Prism returns 200/201/204 by default. To test error scenarios, send the
`Prefer: code=<status>` header — Prism responds with that status code regardless of the
request:

```yaml
getOrg_NotFound:
  target: source-oas:Orgs_getDetails
  parameters:
    path:
      org_id: "00000000-0000-0000-0000-000000000000"
    query:
      version: "2024-01-04"
    headers:
      Prefer: "code=404" # ← Prism returns 404
  ignore:
    schema: true # ← Prism body may not match the spec's error schema
  expected:
    response:
      statusCode: 404
```

**Always pair `Prefer: code=X` with `ignore: { schema: true }` for error scenarios.**
Prism generates the response body from the spec's example for that status code. If the spec
doesn't have a matching body example, Prism may return an empty or incorrect body — triggering
response schema validation failures that are not relevant to what you're testing.

---

## Common `Prefer` patterns

| Scenario | Header               | Also add                                     |
| -------- | -------------------- | -------------------------------------------- |
| 404      | `Prefer: "code=404"` | `ignore: {schema: true}`                     |
| 401      | `Prefer: "code=401"` | `ignore: {schema: true}` + `exclude: [auth]` |
| 403      | `Prefer: "code=403"` | `ignore: {schema: true}`                     |
| 400      | `Prefer: "code=400"` | `ignore: {schema: true}`                     |
| 204      | `Prefer: "code=204"` | (usually no body, no schema check needed)    |

---

## Spec quality issues surfaced by Drift + Prism

When Drift validates a response against the spec schema and reports something like:

```
"4a72d1db-b465-4764-99e1-ecedad03b06aX" is not a "uuid"
```

this usually means the spec's own response example is invalid — not your test data. Drift
is correctly identifying a bug in the spec. Prism faithfully serves whatever example is in
the spec, and Drift faithfully validates it.

**`ignore: { schema: true }` does NOT help here** — it suppresses request schema validation
only. There is no per-operation bypass for response schema validation.

Options when you hit a spec quality issue:

1. Fix the spec upstream (best outcome — Drift is doing its job)
2. Document the failure as a known spec bug and exclude that specific operation from the
   CI gate with a comment explaining why
3. Add a comment in the test file noting the spec defect so future maintainers understand
   why it's failing

---

## Dynamic base URL in Lua hooks

If your Lua hooks make setup/teardown requests, they need to know the server URL. Pass it
via an environment variable:

```bash
SERVER_URL=http://localhost:4010 drift verifier --test-files drift.yaml --server-url http://localhost:4010
```

```lua
-- drift.lua
local server_url = os.getenv("SERVER_URL") or "http://localhost:8080"

local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      http({ url = server_url .. "/products", method = "POST",
             body = { id = 10, name = "Test Product", price = 9.99 } })
    end
  }
}
return exports
```

---

## Limitations of mock server testing

- Prism doesn't enforce authentication — use `Prefer: code=401` to simulate it
- Prism's 404 response body may use the spec's example for the first response, not the 404
- Response validation errors may point to spec bugs, not API bugs
- Stateful tests (CREATE → READ → DELETE) don't work with a stateless mock — use `Prefer`
  headers to force each desired outcome independently

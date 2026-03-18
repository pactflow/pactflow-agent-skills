# Drift Authentication Reference

## Contents

- [Global auth block](#global-auth-block)
- [Dynamic tokens (retrieved at runtime)](#dynamic-tokens-retrieved-at-runtime)
- [Non-standard auth prefix](#non-standard-auth-prefix)
- [Testing 401 — unauthenticated requests](#testing-401--unauthenticated-requests)
- [Testing 403 — authenticated but forbidden](#testing-403--authenticated-but-forbidden)
- [PactFlow auth (for publishing results)](#pactflow-auth-for-publishing-results)

---

## Global auth block

Configure auth once in `drift.yaml` — it applies to every operation by default:

```yaml
global:
  auth:
    apply: true
    parameters:
      authentication:
        scheme: bearer      # bearer | basic | api-key
        token: ${env:API_TOKEN}
```

`scheme: bearer` emits `Authorization: Bearer <token>`. If the API uses a different prefix
(e.g. `token`, `ApiKey`), see **Non-standard auth prefix** below.

### Basic auth

```yaml
authentication:
  scheme: basic
  username: ${env:API_USER}
  password: ${env:API_PASS}
```

### API key

```yaml
authentication:
  scheme: api-key
  header: X-API-Key        # header name
  token: ${env:API_KEY}
```

---

## Dynamic tokens (retrieved at runtime)

Use an exported Lua function when the token must be fetched from an auth endpoint:

```lua
-- drift.lua
local cached_token = nil

local function get_token()
  if cached_token then return cached_token end
  local res = http({
    url    = "http://localhost:8080/auth/token",
    method = "POST",
    body   = { username = "test", password = os.getenv("TEST_PASSWORD") }
  })
  cached_token = res.body.token
  return cached_token
end

local exports = {
  exported_functions = {
    bearer_token  = get_token,
    readonly_token = function() return os.getenv("READONLY_TOKEN") end
  }
}
return exports
```

Reference in `drift.yaml`:

```yaml
global:
  auth:
    parameters:
      authentication:
        scheme: bearer
        token: ${functions:bearer_token}
```

---

## Non-standard auth prefix

`scheme: bearer` always emits `Authorization: Bearer <token>`. If the API requires a different
prefix (e.g. `token`, `ApiKey`, `AWS4-HMAC-SHA256`), inject the header directly via the
`http:request` hook and skip the global auth block:

```lua
-- drift.lua
["http:request"] = function(event, data)
  data.headers["Authorization"] = "token " .. os.getenv("API_TOKEN")
  return data
end
```

Or set it per-operation with `exclude: [auth]` + manual header:

```yaml
operations:
  getOrg_Success:
    target: source-oas:getOrg
    exclude:
      - auth
    parameters:
      headers:
        authorization: "token ${env:API_TOKEN}"
    expected:
      response:
        statusCode: 200
```

---

## Testing 401 — unauthenticated requests

Strip global auth and send a bad token. Always pair with `Prefer: code=401` when using a mock
server (Prism), since the mock can't actually validate tokens.

```yaml
getOrg_Unauthorized:
  target: source-oas:getOrg
  exclude:
    - auth
  parameters:
    path:
      org_id: "59d6d97e-3106-4ebb-b608-352fad9c5b34"
    query:
      version: "2024-01-04"
    headers:
      authorization: "Bearer invalid-token"
      Prefer: "code=401"    # only needed with Prism mock servers
  ignore:
    schema: true            # Prism error body may not match spec schema
  expected:
    response:
      statusCode: 401
```

---

## Testing 403 — authenticated but forbidden

Keep global auth active but point the request at a resource the token cannot access. Store a
`forbidden` entry in your dataset:

```yaml
# dataset
orgs:
  existing:   { id: "59d6d97e-..." }   # owned by the test account
  forbidden:  { id: "00000000-..." }   # an org the token cannot administer
```

```yaml
listProjects_Forbidden:
  target: source-oas:listProjects
  dataset: my-data
  parameters:
    path:
      org_id: ${my-data:orgs.forbidden.id}
    headers:
      Prefer: "code=403"    # only needed with Prism mock server
  ignore:
    schema: true
  expected:
    response:
      statusCode: 403
```

---

## PactFlow auth (for publishing results)

```bash
export PACTFLOW_BASE_URL="https://your-workspace.pactflow.io"
export PACTFLOW_TOKEN="your-api-token"   # Settings → API Tokens in PactFlow UI
```

Use a **System Account Token** in CI (not a personal token) — it needs publish permissions.

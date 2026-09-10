---
name: oas-generator
description: >
  Generates an OpenAPI 3.x YAML spec from a provider codebase using ripwire when no spec exists.
  Invoke this skill whenever the user needs an OpenAPI spec for a service that doesn't have one
  published — phrases like "generate an openapi spec from the code", "there's no oas for this
  service", "create a spec from the codebase", "the provider doesn't have a spec", or any time
  a pact-coverage or contract testing workflow is blocked because the provider spec is missing.
  Uses ripwire to extract HTTP route definitions and handler schemas across Ruby (Rails/Sinatra),
  Node.js (Express/Fastify), Python (Flask/FastAPI), and other ripwire-supported languages.
  Always ask for the codebase path if not provided. Requires ripwire on PATH.
---

# OAS Generator

Generates an OpenAPI 3.x YAML spec by statically analysing a provider codebase with ripwire.
The spec may be incomplete (stubs for unresolvable schemas), but it will always be valid OAS
and immediately usable for path-coverage testing.

**Prerequisites:** `ripwire` on PATH. If absent, check `pact-coverage/references/install-ripwire.md`.

---

## Step 1 — Identify the framework

Run ripwire to get oriented, then infer the framework from the ranked output and config files:

```bash
ripwire <provider-root> --for="HTTP route definitions and request handlers"
```

Also check for framework config files in the project root:
- `Gemfile` with `sinatra` or `rails` → Ruby
- `package.json` with `express`, `fastify`, `koa`, or `hapi` → Node.js
- `pyproject.toml` / `requirements.txt` with `flask` or `fastapi` → Python

If the framework is still ambiguous after these checks, ask the user.

---

## Step 2 — Extract all routes

Use framework-specific grep patterns to find every route registration. Run all applicable
patterns and deduplicate results.

### Ruby — Rails
```bash
ripwire <root> --grep="resources\|get '\|post '\|put '\|patch '\|delete '\|namespace"
```
Also expand `config/routes.rb` to get the full route DSL, then trace each action to its
controller method to find what each path actually maps to.

### Ruby — Sinatra
```bash
ripwire <root> --grep="get '\|post '\|put '\|patch '\|delete '"
```
Each match is a route; the enclosing block is the handler. Note the `in=` attribute from grep
hits to get the enclosing symbol name, then `--expand` it for the full handler body.

### Node.js — Express / Fastify / Koa
```bash
ripwire <root> --grep="\.get(\|\.post(\|\.put(\|\.patch(\|\.delete(\|\.route("
```
Also check for `router` objects (e.g. `router.get(`) and `app.use(` with sub-routers.

### Python — Flask
```bash
ripwire <root> --grep="@app\.route\|@blueprint\.\|@bp\."
```

### Python — FastAPI
```bash
ripwire <root> --grep="@router\.\|@app\.get\|@app\.post\|@app\.put\|@app\.patch\|@app\.delete"
```

### Fallback — any language
```bash
ripwire <root> --for="HTTP route handler path method registration"
```
Take the top-ranked symbols. For each one, check if it looks like a route definition (contains
a path string starting with `/`). Expand promising symbols for confirmation.

---

## Step 3 — Build the route inventory

For each route found, record:
- **Path template** — normalise concrete values to `{param}` placeholders
  (e.g. `/users/:id` → `/users/{id}`, `/users/<int:user_id>` → `/users/{user_id}`)
- **HTTP method** — `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
- **Handler symbol** — the enclosing function/method name (for schema extraction in Step 4)

Deduplicate: same method + path = one entry, keep the first handler found.

---

## Step 4 — Extract schemas per route

For each route, `--expand` its handler symbol and look for:

**Request body**: fields set from the incoming request
- Ruby: `params[:field]`, `request.body.read`, `JSON.parse(request.body)`
- Express: `req.body.field`, `req.params.field`, `req.query.field`
- Flask: `request.json.get('field')`, `request.form.get('field')`
- FastAPI: function parameter with a Pydantic model type hint → extract model fields

**Response body**: what the handler returns
- Ruby: `render json: { field: value }`, `.to_json`
- Express: `res.json({ field: value })`, `res.send()`
- Flask: `jsonify({ 'field': value })`
- FastAPI: `return` statement or `response_model=` annotation

**Status codes**: explicit codes set in the handler
- Look for `status:`, `.status(N)`, `HTTPException(status_code=N)`, `abort(N)`
- Default: 200 for GET, 201 for POST, 204 for DELETE/PUT/PATCH when no body returned

**When inference fails**: emit an empty schema stub — do not skip the route. A path with no
schema is still useful for path-coverage testing. Mark it with `x-schema-source: stub`.

---

## Step 5 — Assemble the OpenAPI YAML

Build a valid OAS 3.x document. Use this structure:

```yaml
openapi: "3.0.3"
info:
  title: "<ServiceName> API"
  version: "0.0.0-generated"
  description: "Auto-generated from source by oas-generator. Review and refine before production use."
paths:
  /resource/{id}:
    get:
      summary: "GET /resource/{id}"
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: "Success"
          content:
            application/json:
              schema:
                type: object
                properties: {}      # stub — expand if fields found
        "404":
          description: "Not found"
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
    post:
      summary: "POST /resource"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties: {}        # stub — expand if fields found
      responses:
        "201":
          description: "Created"
          content:
            application/json:
              schema:
                type: object
                properties: {}
```

**Schema hints**:
- If you found field names from Step 4, list them under `properties` with `type: string` (or
  a more specific type if the code makes it obvious — integer literals, boolean flags, array
  literals).
- Mark inferred fields with `x-schema-source: inferred`; mark stubs with `x-schema-source: stub`.
- Use `required: [field1, field2]` only when the handler clearly fails/errors without a field.
- Resolve path parameters: every `{param}` in the path gets a `parameters` entry with `in: path`.

---

## Step 6 — Write and report

Save the spec to a file the user can use immediately:
- Default location: `<provider-root>/openapi-generated.yaml`
- Or wherever the user specifies

After writing, print a summary:
```
Generated OAS written to: <path>
Routes:       N
  Inferred:   N  (schemas extracted from handler code)
  Stubs:      N  (no schema found — empty schema emitted)
Status codes: inferred / defaulted breakdown
```

Remind the user that the generated spec is a starting point: stub schemas and missing required
fields will create false gaps in coverage checks. They should review and fill in schemas before
using it for production BDCT.

---

## Tips for accuracy

- **Rails routes are indirect** — `resources :users` generates 7 standard actions; trace each to
  the controller to find what's actually implemented. Use `--expand=UsersController` and look for
  `def index`, `def show`, etc.
- **Nested routes** multiply paths — `namespace :api { resources :users }` → `/api/users`, `/api/users/{id}`.
- **Middleware / concerns** can add routes — grep for `include`, `concern`, `prepend_before_action`.
- **Versioned APIs** often use a prefix (`/v1/`, `/api/v2/`) — preserve it in the path.
- **ripwire `--callers=handler_sym`** helps when a router delegates to a class method — find the
  registration site to confirm the path and method.
- If ripwire returns `over_ceiling=1`, narrow the root path to just the controllers/routes directory
  and re-run.

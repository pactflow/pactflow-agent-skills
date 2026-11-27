# Consumer discovery manifest (1.0.0)

Discovery (the agent, using ripwire / codebase-memory / graphify / plain search) writes this file for one
commit and **one consumer→provider pair**. `scripts/consumer_coverage.py` calculates coverage from it with no further
code analysis, so the same commit always gives the same artifact. **Never put code snippets or function bodies in it.**
Paths are relative to the repository root. If the working tree is dirty, say so in `notes`: the manifest is tied to the
commit, not to uncommitted edits.

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
        "parameters": [
          { "name": "id", "in": "path" },
          { "name": "category", "in": "query", "values": ["books", "games"], "optional": true }
        ],
        "headers": [{ "name": "x-api-key" }],
        "body": [{ "name": "quantity" }]
      },
      "responseFields": { "200": ["id", "price.amount", "roles[].name"], "404": ["message"] }
    },
    { "unresolvedReason": "URL built from a runtime string", "callSite": { "file": "src/x.ts", "line": 5, "symbol": "load" } }
  ],
  "tests": { "<pact interaction description>": { "file": "tests/x.test.ts", "line": 30, "symbol": "it title" } }
}
```

## Rules for discovery

| Field | Rule |
|-------|------|
| `path` | The path template built in the code (`/products/{id}`), not a concrete URL. Parameter names need not match the spec or the pact: `{id}` matches `{productId}` and `/products/7`. Move a query string into `inputs.parameters`. Never leave template syntax (`${id}`, `{{id}}`) in a path: the script warns and matches it literally. |
| `callSite` | **Always** `file`, `line` and `symbol`. Point at the endpoint-specific method (`getUserDetails`), not the shared helper that sends the request (`gitHubGet`); list the helper under `handlers`. `hash` is optional (a hash of the call, never its source); when absent it is computed from kind, file, line and symbol. |
| `successStatus` | Omit if the code does not pin one. Then any 2xx counts as the success response: with a spec, the documented 2xx that an interaction returns (else the lowest), without one `2XX`. Pin it when the code accepts one specific code. |
| `handledStatuses` | Only statuses checked **in the code that handles this call** (the handler or wrapper), never repo-wide or in global middleware. `4XX` means the code treats any client error alike: it is Tested by any 4xx interaction. `non-2XX` (or `error`) means any non-success is one error branch: Tested by any non-2xx interaction. A specific code the code names is Tested by that status. 5xx, 3xx, other ranges and `default` are reported as Excluded. A generic wrapper that throws on any non-2xx and never names a code is `non-2XX`; if there is no check at all, leave the list empty. |
| `handlers` | Locations of the code that checks the statuses, listed against non-success responses and response fields. A shared handler used by several operations is one location. |
| `nearestTest` | One location of the closest existing test for the call. Not required when `tests` places the interactions. |
| `inputs.parameters` | `name`, `in` (`query`, `header`, `cookie`; `path` is accepted but not counted, because a path parameter is part of the operation's identity), optional `values` and `optional`. List `values` only where the code genuinely varies the input, taken from its types (enums, unions; a boolean is a two-value union, written `"true"`/`"false"`). Omit `values` for free-form inputs. More than 5 values are cut (large-enum limit). `optional: true` means the code sometimes leaves it out and drives the present/absent pairwise axis. |
| `inputs.headers` | The same as a parameter with `in: header`. List auth headers the code sets (`x-api-key`); leave out transport headers (`Host`, `Content-Length`). |
| `inputs.body` | Top-level and nested field names the code sends (`quantity`, `address.city`), with optional `values`/`optional`. Form-urlencoded bodies are parsed from the pact, so list the form fields by name. A body forwarded whole from the caller has no named fields: list none. |
| `responseFields` | Fields the code reads. Keys are a status, or `2XX`/`success` for the success response (they resolve to the same status as the success item, so `200` and `2XX` on two call sites merge). Dotted names descend into objects; a name through an array writes `roles[].name` (or plain `roles.name`: the script takes the first element). A `oneOf` variant's fields are listed only once the code reaches that variant. A runtime validator's required fields (zod, valibot, pydantic) are reads only if you decide they are; say which in `notes`. Fields read inside a helper (`page.number` read by `paginate()`) are reads too. |
| `readsNothing` | `true` when the code awaits the call and discards the body. The success status gets an empty read set, so every pact field is reported as over-specified. Without it, omitted `responseFields` mean "reads not recorded": no observations, and Response fields shows n/a. |
| `passThrough` | `true` (or a list of statuses) when the body is returned to the caller unread. No observations for those statuses: the code may well use any field downstream. |
| `unresolvedReason` | Set when the target operation cannot be worked out (a URL built from a runtime string, a URL handed back by the server such as a polling `status_url`). The call is listed as unresolved, never dropped. It may also carry `method`/`path`. When the spec or a pact shows the template (`/api/ai/status/{session_id}`), you may instead write the call with that template and say so in `notes`. |
| `tests` | Pact interaction → test location, so each item names the test that covers it. Keys, most specific first: `<pact file>#<description>`, `<description>#<providerState>`, `<description>`. Use the first two when descriptions repeat (a 200 and a 404 with the same description). A description with an interpolated value must match the pact's resolved text exactly. Use the test's `it()` title, or the `uponReceiving` line, as `symbol`, and say which in `notes`. An interaction with no entry gets no test location (a warning lists them). |
| `notes` | Free text for the next reader: assumptions, guessed provider names, what was left out. Never code. Not published. |

## Situations

- **A method chosen at runtime** (`isNew ? post : put`): write two calls sharing the `callSite`.
- **One call site, several templates** (an optional trailing segment): write one call per template.
- **A provider reached through two hosts** under one pact provider name: one pair, calls listed with their own paths.
- **A public client method with no production caller**: include it if you consider the client the consumer; say so in `notes`.
- **Calls with no pact and no broker name**: pair them under the name the code or config implies and record the guess in
  `notes`. Do not invent a name that looks confirmed.
- **Message pacts** (events, queues): not supported. The script skips them and reports `notMeasured: messagePacts`.
- **Third-party SDKs and hosts outside the pair** (AWS SDK, Slack, Segment): leave out.
- **A pact that expects a status the code does not handle** (a 409 the code never checks): it is reported as an
  `unhandledResponseStatus` observation, not as a response item.
- **Pacts for another commit**: the artifact records each pact's consumer version and sha256 under `source.pacts` and
  flags a mismatch with the manifest commit.

## Answers to questions discovery runs kept hitting

- **Paths**: relative to the repository root, including a monorepo subdirectory prefix (`app_saas/src/x.ts`).
- **`tool`**: free text naming what drafted the manifest (`ripwire`, `grep`, `manual`). It is not validated.
- **Several client classes, one provider**: merge them into one `calls` array. Calls with the same method and path
  (from any module) merge into one operation, and their `responseFields` are unioned.
- **Same method and path, different purpose** (`createUser` vs `createOrUpdate`): write both calls; they merge. A client
  method with no production caller is your call; say which in `notes`.
- **Array responses**: a top-level array body is written `[].login`. Observation paths print collapsed
  (`users.roles.name`); it is the same field as `users[].roles[].name`.
- **Body forwarded whole / a fixed literal query value** (`embed=entitlements`): list neither. Only inputs the code
  varies are measured, so a constant is not an input.
- **Shared handler** (a `fetch` wrapper that checks statuses for every call): list it under `handlers` on each call it
  serves; the same location is stored once.
- **Two success codes** (200 result or 202 poll): leave `successStatus` out and list the other in `handledStatuses`.
  A wrapper that throws on any non-2xx is `non-2XX`; 5xx stays Excluded even then, unless a pact interaction returns
  it and the wrapper is `non-2XX`, in which case that interaction counts as Tested.
- **`readsNothing` vs `passThrough`**: `readsNothing` if the call site discards the body, even when a helper parsed it;
  `passThrough` if the body is returned to a caller unread. Record it on the call that sends it on. For 204, use
  `readsNothing`.
- **Test symbols**: the test's own name: `it()` title (JS), test function name (pytest, JUnit), or the `uponReceiving`
  line when there is none. Say which in `notes`. Match pact descriptions exactly (interpolated values resolved).
  `<description>#<providerState>` uses the provider state's `name`.
- **Stale pact** (interaction with no test in the repo): the script warns. Treat the pact as stale, not the code as
  untested, and say so in `notes`.
- **`passThrough` with `responseFields`**: both may be set. `responseFields` records what the code reads before the body is
  passed on; `passThrough` only stops over-specified-field observations for those statuses.
- **Runtime validators** (zod, valibot, pydantic, decorators): a field the code never reads outside validation is not a
  read. List only fields the code uses; say so in `notes`.
- **Typed-error wrappers** that name codes themselves (`HttpError4xx`): handled statuses are those the wrapper or the
  call site names; a bare 4xx/5xx class means `4XX` and Excluded 5xx.
- **Query built from an object** (`qs.stringify`, ternary tails): list the keys the code varies, with `optional: true`
  for keys it sometimes omits. A key sent on every call is not varied: leave it out. Auth headers (`Authorization`) are
  inputs only if the code varies them.
- **A 2xx body carrying an error** (`200` with `error=`): not expressible; say so in `notes`.
- **Optional path tail** (two templates): one call each, both with the same `callSite`.
- **Consumer name**: the name the pact test config uses, not the repo name.
- **Enumerating a large client**: a regex scan of call sites is fine; check multi-line templates and ternary path tails by hand.
- **No provider version on the broker** (or 404 on the contract): run without `--spec`. Pact-less providers: run with
  `--no-pacts` if the code calls them, skip providers the code does not call.
- **Several providers**: one manifest and one script run per pair. Name guessed providers in `notes`.
- **`notes`** (manifest-level or per call) is for the next reader: allowed, ignored by the script, never published.

## Getting pacts and a spec

- The PactFlow MCP returns only pact links. Let the script fetch them:
  `--broker-url "$PACT_BROKER_BASE_URL" --broker-token "$PACT_BROKER_TOKEN" --consumer C --provider P` (latest pact,
  read-only; add `--save-pacts DIR` to keep the pact file). Do not curl by hand.
- A pact from another consumer version than the manifest commit gives a `commitMismatch` warning. Accept it and keep the
  manifest (discovery reads HEAD); the warning is for the reader. Re-discover only if the code changed in the area.
- No pacts at all: `--no-pacts` (every item is Not tested; that reflects missing pacts, not test quality).
- No spec: try `get_bdct_provider_contract` once; on 404 or no provider version, run without `--spec`. A BDCT contract
  returned inline can be written to a file as is (do not hand-trim it).
- Folders may hold pacts for other consumers or providers; the script skips them by name.

## Script checks

`consumer_coverage.py` lists in the artifact's `warnings`: unknown manifest keys (they are ignored, not guessed at), template syntax in a path, a
`callSite` without file, line or symbol, `tests` keys that match no interaction, interactions with no `tests` entry, and
pacts built from another commit. `--check` validates the artifact against the schema (`jsonschema` is a script dependency, so it always runs). A malformed manifest prints `consumer coverage skipped, NO artifact written` and still exits 0; read stderr.

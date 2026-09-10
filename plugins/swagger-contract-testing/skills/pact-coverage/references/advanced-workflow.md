# Advanced: Two-Step Workflow

Use this when you need to inspect or reuse the filtered OAS as a standalone file,
or when you want to separate the filtering step from the coverage check (e.g. in CI).

---

## Step 1: Build Consumer Knowledge Graph (ripwire)

```bash
ripwire ./consumer-src --for="HTTP API route calls and response types" > kg.xml
```

Check `confidence=` on the root element:
- `confidence="high"` — sharp ranking; proceed
- `confidence="low"` — re-run with a more specific task, or use `--token-budget=<higher>`

If `over_ceiling="1"` or any section has `capped="1"`, re-run with a larger budget or
narrower consumer root. Use at most 3 iterations before proceeding with the best result.

### Two-strategy discovery

`build_filtered_oas.py` tries two strategies automatically:

**Strategy 1 — HTTP call site** (`fetch`, `axios.*`, `requests.*`):
Finds HTTP calls directly; the calling function is expanded to extract the return type.

**Strategy 2 — Response-type construction** (fallback, all HTTP clients):
When strategy 1 finds nothing (e.g. the consumer uses `aiohttp`, `net/http`,
`HttpClient`), the script scans function bodies for patterns like `TypeName(**data)`,
`TypeName.model_validate(data)`, or `resp.data as TypeName`. URL path and HTTP method
are then extracted from the same function body.

If both strategies return nothing, use `--routes` (see below).

---

## Step 2: Build Filtered OAS

```bash
uv run scripts/build_filtered_oas.py \
  --spec openapi.yaml \
  --kg kg.xml \
  --consumer-root ./consumer-src \
  --output filtered-oas.yaml
```

Type resolution tiers:

| Tier | What it tries | Result |
|------|--------------|--------|
| 1 | Consumer type name matches OAS schema name exactly | Consumer fields become `required[]` |
| 2 | Normalised name matches (strips `Response`, `Dto`, `I` prefix, etc.) | Same |
| 3 | Consumer fields structurally overlap an OAS schema (≥ 80%) | Consumer fields become `required[]` |
| 4 | No type link found | OAS `required[]` used as-is (conservative fallback) |

Exit code 1 means some operations used Tier 4 — check the summary for which ones.
The filtered OAS includes `x-consumer-type-match` annotations showing which tier was used.

**If `--consumer-root` is omitted:** type resolution is skipped (all Tier 4).  
**If `--kg` is omitted:** the script runs ripwire itself using `--consumer-root`.

### When ripwire doesn't support the HTTP client

ripwire recognises `fetch`, `axios.*`, and `requests.*`. For other clients (Python
`aiohttp`, Go `net/http`, Java `HttpClient`), ripwire returns 0 routes.

Read the consumer source, identify the endpoints it calls, and supply them manually:

```bash
uv run scripts/build_filtered_oas.py \
  --spec openapi.yaml \
  --routes '[{"method":"GET","path":"/orders/{id}"},{"method":"POST","path":"/orders"}]' \
  --output filtered-oas.yaml
```

**Do not use the pact files as a route source.** The filtered OAS is the denominator
the pact is checked against — deriving it from the pact makes path coverage trivially
100% with no real gaps visible.

---

## Step 3: Run Coverage Check Against the Filtered OAS

```bash
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml \
  --pacts "pacts/*.json"

# Machine-readable output
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml --pacts "pacts/*.json" --json

# Exclude status codes
uv run scripts/parse_pact_coverage.py \
  --spec filtered-oas.yaml --pacts "pacts/*.json" --exclude-codes 500 501 502 503
```

**Never pass the original `openapi.yaml` here** — that makes the denominator the full
provider spec, so every unused provider endpoint appears as a false gap.

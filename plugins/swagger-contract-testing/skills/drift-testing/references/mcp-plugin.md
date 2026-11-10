# Drift MCP Plugin

Verifies a Model Context Protocol (MCP) server against its declared definition: tools, resources, resource templates and prompts.

Docs: https://support.smartbear.com/swagger/contract-testing/docs/en/drift/plugins/mcp-plugin.html

## Setup

- Install the `mcp` plugin in the Drift plugin directory.
- If any tool declares an `inputSchema` or `outputSchema`, also install/enable the `json` plugin.
- The definition file must be named `.mcp.yaml`, `.mcp.yml` or `.mcp.json`. Drift identifies MCP definitions by this extension and accepts **only the SmartBear Studio MCP format**.
- Never modify the MCP definition you are testing.

## Coverage

```bash
uv run scripts/check_coverage.py --spec notes.mcp.yaml --test-files drift.yaml
```

Auto-detected from the `.mcp.*` extension. Requires `drift/all` (or all six individual `drift/*` checks) plus a `tool/`, `resource/` or `prompt/` test for every declared item. Resource templates are covered by the drift check only. Verified against a real definition (smartbear-mcp's `src/pactflow/drift/pactflow.mcp.yaml`: top-level `tools:`/`prompts:` lists with `name`); the parser also tolerates maps and `resources` keyed by `uri`.

## Test file skeleton

```yaml
drift-testcase-file: v1
title: "Notes MCP server"

sources:
  - name: notes
    path: ./notes.mcp.yaml

plugins:
  - name: mcp
  - name: json # only if tools declare inputSchema/outputSchema

operations:
  drift_all:
    target: notes:drift/all

  createNote_Success:
    target: notes:tool/create_note
    parameters:
      arguments:
        title: "hello"
    expected:
      result:
        structuredContent:
          title: "hello"
```

Targets have the form `<source-name>:<kind>/<name>`.

## Drift checks (no tool calls — safe against production)

| Target | Checks |
| --- | --- |
| `drift/all` | Runs tools, resources, resourceTemplates and prompts. Use it **or** the individual checks, not both |
| `drift/tools` | Declared tools vs `tools/list` |
| `drift/resources` | Declared resources vs `resources/list` |
| `drift/resourceTemplates` | Declared templates vs `resources/templates/list` |
| `drift/prompts` | Declared prompts vs `prompts/list` |
| `drift/capabilities` | Advertised capabilities are actually served |
| `drift/discover` | Reachability and protocol version negotiation |

A server offering **less** than declared fails. Offering **more** warns, unless `fail-on-undeclared` is set.

## Invocation tests

One operation per declared item:

| Target | JSON-RPC method | Parameters |
| --- | --- | --- |
| `tool/<name>` | `tools/call` | `parameters.arguments` |
| `resource/<uri>` | `resources/read` | `parameters.uri` |
| `prompt/<name>` | `prompts/get` | `parameters.arguments` |

Drift does **not** expand resource templates; target a concrete URI.

## Assertions

```yaml
# Protocol error (e.g. JSON-RPC invalid params -32602)
expected:
  error:
    code: -32602

# Tool error (tool ran and reported failure)
expected:
  result:
    isError: true
    content: # optional
      - contains: "not found"   # matcher applies directly to each content block

# Success
expected:
  result:
    structuredContent:
      id: 1
```

If a tool declares an `outputSchema`, Drift validates `structuredContent` against it automatically.

## Transports

```bash
# Streamable HTTP
drift verify --test-files drift.yaml --server-url http://localhost:3000/mcp

# stdio, inline command (repeat the singular `arg` query parameter for each argument)
drift verify --test-files drift.yaml --server-url "stdio:///node?arg=server.js"

# stdio, configured alias
drift verify --test-files drift.yaml --server-url stdio://notes
```

Alias config in `drift.config.toml`:

```toml
[plugin_config.mcp.servers.notes]
command = "node"
args = ["server.js"]
```

## Plugin configuration (`[plugin_config.mcp]` in `drift.config.toml`)

| Option | Default | Effect |
| --- | --- | --- |
| `fail-on-undeclared` | `false` | Fail (not warn) on undeclared tools/resources/prompts |
| `fail-on-description-change` | `false` | Fail when descriptions differ |
| `fail-on-undocumented-output` | `false` | Fail when a result has fields not in `outputSchema` |
| `fail-on-undocumented-input` | `false` | Fail when arguments have fields not in `inputSchema` |
| `stdio-shutdown-timeout-ms` | `5000` | Time a stdio server has to exit before Drift stops it |

## Limitations

- **No authentication.** Drift cannot authenticate to the MCP server. Test unauthenticated HTTP endpoints, or use stdio and pass credentials via the server process environment.
- Lua scripting is not documented for the MCP plugin.

## Publishing to PactFlow (BDCT)

```bash
drift verify \
  --test-files drift.yaml \
  --server-url http://localhost:3000/mcp \
  --generate-result \
  --output-dir ./drift-results
EXIT_CODE=$?   # must be the real Drift exit code, even on failure

RESULTS="$(find ./drift-results/results -name 'verification.*.result' | sort | tail -n 1)"

pact pactflow publish-provider-contract notes.mcp.yaml \
  --provider notes-server \
  --provider-app-version "$(git rev-parse --short HEAD)" \
  --branch "$(git branch --show-current)" \
  --content-type application/yaml \
  --specification mcp \
  --verification-exit-code $EXIT_CODE \
  --verification-results "$RESULTS" \
  --verification-results-content-type application/vnd.smartbear.drift.result \
  --verifier drift
```

The key MCP-specific flag is `--specification mcp`; the verification flags follow `references/pactflow-and-cicd.md`. Working example: smartbear-mcp's `scripts/ci/drift-publish-provider-contract` and `src/pactflow/drift/README.md` (note PactFlow stores `mcp` contracts as published; they can't satisfy can-i-deploy).

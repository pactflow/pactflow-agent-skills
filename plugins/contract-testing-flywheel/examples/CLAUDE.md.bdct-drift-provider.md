# Contract testing context — BDCT provider (Drift)

This is the **provider side** of a BDCT integration with `{{consumer}}`. The OpenAPI spec at `{{openapi_path}}` is the authoritative description of `{{provider}}`'s surface. Drift verifies the running API matches the spec; PactFlow cross-checks the spec against `{{consumer}}`'s recorded expectations.

## Stack

- Language / framework: `{{stack}}`
- OpenAPI spec: `{{openapi_path}}`
- Drift CLI: [pactflow.github.io](https://pactflow.github.io)
- Drift test cases: `drift/`
- Broker: `{{broker_url_or_phrase}}`
- CI: `{{ci_tool}}`

## Skills and tools Claude Code should prefer here

- `/swagger-contract-testing` — end-to-end BDCT help.
- `swagger-contract-testing:drift-testing` — write, run, and debug Drift test cases.
- `swagger-contract-testing:openapi-parser` — generate Drift test cases from complex OpenAPI schemas (`anyOf`, `oneOf`, `allOf`, discriminators, polymorphism, `$ref` chains, regex, enums).
- `swagger-contract-testing:pactflow` — publish the provider contract, run `can-i-deploy`, inspect the matrix.
- `smartbear-mcp` — AI-assisted PactFlow operations.

## House rules

- The OpenAPI spec is the single source of truth. If the implementation diverges from the spec, fix the implementation. Do not relax the spec to match buggy behaviour.
- Every endpoint in the spec has at least one Drift test case per documented response variant. When you add a response code or schema variant, add the matching Drift case in the same PR.
- Drift expressions are for dynamic values (timestamps, UUIDs). Do not use them to paper over schema mismatches.
- Drift lifecycle hooks (Lua) handle fixture setup and teardown. Assertions belong in the test case body.
- Run `drift run drift/` locally before opening a PR. CI runs it too, but treat CI as a backstop, not the primary check.
- On merge to `main`, CI publishes the OpenAPI spec to `{{broker_url_or_phrase}}` as the provider contract for `{{provider}}` (version = git SHA) and records a deployment when the build is promoted.

## References

- [Drift docs](https://pactflow.github.io)
- [BDCT guide](https://docs.pactflow.io/docs/bi-directional-contract-testing)
- [BDCT OpenAPI examples](https://github.com/pactflow/bdct-oas-examples)
- [OpenAPI / Pact comparator](https://github.com/pactflow/openapi-pact-comparator)
- [PactFlow docs](https://docs.pactflow.io)

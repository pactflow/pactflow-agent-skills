# Drift / BDCT link bundle + skill footer

Appended by SKILL.md Step 4 to the Helpful-links section of 03b, 04b, and 05 templates when `{{ct_mode}}` is `BDCT` or `Both`.

## Links to append

- Drift docs — https://pactflow.github.io
- Bi-Directional Contract Testing guide — https://docs.pactflow.io/docs/bi-directional-contract-testing
- BDCT OpenAPI examples — https://github.com/pactflow/bdct-oas-examples
- OpenAPI / Pact comparator — https://github.com/pactflow/openapi-pact-comparator

## Skill footer to append (replaces the default skill footer for BDCT-tagged tickets)

```
---
*If you're using Claude Code:*
- *`/swagger-contract-testing` — end-to-end help with BDCT flows (generate, publish, verify).*
- *`swagger-contract-testing:drift-testing` skill — write, run, and debug Drift test cases; drive towards full endpoint coverage and a passing Drift run against your live API.*
- *`swagger-contract-testing:openapi-parser` skill — generate Drift test cases from complex OpenAPI schemas (`anyOf`, `oneOf`, `allOf`, discriminators, polymorphism, `$ref` chains, regex patterns, enums).*
- *`swagger-contract-testing:pactflow` skill — publish provider contracts, run `can-i-deploy`, inspect the cross-contract matrix.*
- *`smartbear-mcp` server — AI-assisted operations on PactFlow.*
```

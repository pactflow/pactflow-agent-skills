# Drift Mapping Reference

How to map each OpenAPI schema pattern to Drift test case YAML. Read alongside
`schema-patterns.md` which covers how to enumerate the variants in the first place.

---

## Table of contents

- [Naming conventions](#naming-conventions)
- [oneOf / anyOf branches](#oneof--anyof-branches)
- [discriminator variants](#discriminator-variants)
- [allOf (composition)](#allof-composition)
- [Primitive type unions in parameters](#primitive-type-unions-in-parameters)
- [enum parameters](#enum-parameters)
- [regex (pattern) fields](#regex-pattern-fields)
- [optional field variants](#optional-field-variants)
- [nullable fields](#nullable-fields)
- [Negative / error cases](#negative--error-cases)
- [Dataset structure](#dataset-structure)
- [Lifecycle hooks for stateful variants](#lifecycle-hooks-for-stateful-variants)
- [Expected response matchers](#expected-response-matchers)
---

## Naming conventions

```
{operationId}_{variant}
```

Variant suffixes:

| Situation                | Suffix pattern                                                     |
| ------------------------ | ------------------------------------------------------------------ |
| oneOf/anyOf branch       | `_typeA`, `_typeB` or use the schema name: `_snykCodeIssue`        |
| Discriminator value      | `_deployed`, `_publicFacing` (camelCase the mapping key)           |
| Parameter type variant   | `_byId`, `_bySlug`, `_byName`                                      |
| Optional fields included | `_withOptionals`                                                   |
| Optional fields omitted  | `_minimal`                                                         |
| Null variant             | `_nullParent`                                                      |
| Error case               | `_notFound`, `_unauthorized`, `_missingRequired`, `_invalidFormat` |

---

## oneOf / anyOf branches

Each branch becomes a separate operation. Use a dataset to hold the payload for each
branch and reference it with an expression.

```yaml
# drift.yaml operations block

operations:
  listIssues_snykCode:
    target: source-oas:listOrgIssues
    tags: [issues, variant-snyk-code]
    dataset: issues-data
    parameters:
      path:
        org_id: ${issues-data:orgs.default.id}
    expected:
      response:
        statusCode: 200

  listIssues_snykOss:
    target: source-oas:listOrgIssues
    tags: [issues, variant-snyk-oss]
    dataset: issues-data
    parameters:
      path:
        org_id: ${issues-data:orgs.ossOnly.id}
    expected:
      response:
        statusCode: 200
```

If the server doesn't have deterministic org-type data, use a lifecycle hook to create the resource first (see [Lifecycle hooks](#lifecycle-hooks-for-stateful-variants)).

---

## discriminator variants

Set the discriminator property explicitly in the request body. The dataset should hold
one entry per discriminator value.

```yaml
# Snyk RiskFactor discriminator: propertyName = "name"
# mapping: deployed | os_condition | public_facing

operations:
  getRiskFactors_deployed:
    target: source-oas:getIssueRiskFactors
    tags: [risk-factors, discriminator-deployed]
    dataset: risk-data
    parameters:
      path:
        issue_id: ${risk-data:issues.withDeployedFactor.id}
    expected:
      response:
        statusCode: 200

  getRiskFactors_osCondition:
    target: source-oas:getIssueRiskFactors
    tags: [risk-factors, discriminator-os-condition]
    dataset: risk-data
    parameters:
      path:
        issue_id: ${risk-data:issues.withOsConditionFactor.id}
    expected:
      response:
        statusCode: 200
```

For POST/PUT operations where the discriminator is in the request body:

```yaml
createRiskFactor_publicFacing:
  target: source-oas:createRiskFactor
  tags: [risk-factors, discriminator-public-facing]
  parameters:
    request:
      body:
        name: public_facing # discriminator value
        resource_id: "app-123" # fields from PublicFacingRiskFactor schema
        exposure_level: external
  expected:
    response:
      statusCode: 201
```

---

## allOf (composition)

One test covering the full merged schema. Include all required fields from all `allOf`
branches. Optional fields go in the `_withOptionals` variant.

```yaml
operations:
  createDroplet_success:
    target: source-oas:createDroplet
    tags: [droplets, smoke]
    dataset: droplet-data
    parameters:
      request:
        body: ${droplet-data:droplets.basic} # pre-built payload with all required fields
    expected:
      response:
        statusCode: 202
```

Dataset entry `droplets.basic` must include all required fields from all `allOf` branches.

---

## Primitive type unions in parameters

`anyOf: [integer, string]` in a path or query param → one test per type:

```yaml
operations:
  getImage_byId:
    target: source-oas:getImage
    tags: [images, param-integer]
    parameters:
      path:
        image_id: ${image-data:images.existing.id} # integer
    expected:
      response:
        statusCode: 200

  getImage_bySlug:
    target: source-oas:getImage
    tags: [images, param-string]
    parameters:
      path:
        image_id: ${image-data:images.existing.slug} # string
    expected:
      response:
        statusCode: 200
```

---

## enum parameters

One happy-path test is usually enough. Add extra tests only when the enum value drives
a different response structure.

```yaml
# Single test (enum value doesn't change response shape)
operations:
  listDroplets_typeUser:
    target: source-oas:listDroplets
    tags: [droplets, smoke]
    parameters:
      query:
        type: user
    expected:
      response:
        statusCode: 200

  # Multiple tests (enum value changes response)
  getMetrics_cpu:
    target: source-oas:getDropletMetrics
    tags: [metrics, type-cpu]
    parameters:
      query:
        type: cpu
    expected:
      response:
        statusCode: 200

  getMetrics_memory:
    target: source-oas:getDropletMetrics
    tags: [metrics, type-memory]
    parameters:
      query:
        type: memory
    expected:
      response:
        statusCode: 200
```

---

## regex (pattern) fields

Generate one valid example matching the pattern and put it in the dataset.
For negative testing, construct a clearly invalid value.

```yaml
# Spec: version parameter, pattern: ^\d{4}-\d{2}-\d{2}$

operations:
  listIssues_validVersion:
    target: source-oas:listIssues
    tags: [issues, smoke]
    parameters:
      query:
        version: "2024-01-15" # valid: matches ^\d{4}-\d{2}-\d{2}$
    expected:
      response:
        statusCode: 200

  listIssues_invalidVersion:
    target: source-oas:listIssues
    tags: [issues, negative, regex-violation]
    parameters:
      query:
        version: "not-a-date" # invalid: violates pattern
    ignore:
      schema: true
    expected:
      response:
        statusCode: 400
```

For UUID fields, use a Lua exported function:

```yaml
parameters:
  path:
    resource_id: ${functions:generate_uuid}
```

---

## optional field variants

Two tests: one with all optional fields, one with only required fields.

```yaml
operations:
  createProject_withOptionals:
    target: source-oas:createProject
    tags: [projects, full-payload]
    dataset: project-data
    parameters:
      request:
        body: ${project-data:projects.full} # all required + optional fields
    expected:
      response:
        statusCode: 201

  createProject_minimal:
    target: source-oas:createProject
    tags: [projects, minimal-payload]
    dataset: project-data
    parameters:
      request:
        body: ${project-data:projects.minimal} # required fields only
    expected:
      response:
        statusCode: 201
```

---

## nullable fields

Include a null-value variant only when null drives different server behaviour.

```yaml
operations:
  createIssue_withParent:
    target: source-oas:createIssue
    tags: [issues, with-parent]
    parameters:
      request:
        body:
          title: "Child issue"
          parent_id: ${issue-data:issues.parent.id}
    expected:
      response:
        statusCode: 201

  createIssue_rootLevel:
    target: source-oas:createIssue
    tags: [issues, null-parent]
    parameters:
      request:
        body:
          title: "Root issue"
          parent_id: null # nullable: true — creates a root-level issue
    expected:
      response:
        statusCode: 201
```

---

## Negative / error cases

Cover each documented error status code with at least one test.

```yaml
operations:
  # 400 — missing required field
  createFoo_missingRequired:
    target: source-oas:createFoo
    parameters:
      request:
        body:
          non_required_field: "value" # omit required fields intentionally
    ignore:
      schema: true # suppress Drift schema validation on bad request
    expected:
      response:
        statusCode: 400

  # 401 — no auth
  getFoo_unauthorized:
    target: source-oas:getFoo
    exclude:
      - auth # strip global auth from drift.yaml
    parameters:
      headers:
        authorization: "Bearer invalid-token"
    expected:
      response:
        statusCode: 401

  # 404 — resource not found
  getFoo_notFound:
    target: source-oas:getFoo
    parameters:
      path:
        id: ${foo-data:notIn(foos.*.id)} # guaranteed non-existent ID
    expected:
      response:
        statusCode: 404

  # 422 — invalid field value (regex / enum violation)
  createFoo_invalidFormat:
    target: source-oas:createFoo
    parameters:
      request:
        body:
          name: "valid name"
          code: "TOOSHORT" # violates pattern '^[A-Z]{8,12}$'
    ignore:
      schema: true
    expected:
      response:
        statusCode: 422
```

---

## Dataset structure

One entry per test variant:

```yaml
# drift-datasets/issues.dataset.yaml
drift-dataset-file: V1
datasets:
  - name: issue-data
    data:
      orgs:
        default:
          id: "org-abc123"
        ossOnly:
          id: "org-def456"
      issues:
        withDeployedFactor:
          id: "issue-001"
        withOsConditionFactor:
          id: "issue-002"
        withPublicFacingFactor:
          id: "issue-003"
        parent:
          id: "issue-100"
      projects:
        full:
          name: "Full Project"
          description: "Optional description"
          owner_id: "user-xyz"
          tags: ["team-a", "production"]
        minimal:
          name: "Minimal Project"
```

**Dataset naming rules** — the `name` inside the dataset file must match the `dataset:`
field in the operation block. It does NOT need to match the source name in `drift.yaml`.

---

## Lifecycle hooks for stateful variants

When test data can't be pre-seeded (e.g. the discriminator variant depends on server
state that only exists after a specific create call), use `operation:started` hooks to
set up the right resource before each test.

```lua
-- drift.lua
local state = {}

local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      -- Create an issue with a 'deployed' risk factor before the test
      if data.operation == "getRiskFactors_deployed" then
        local res = http({
          url = data.server_url .. "/orgs/" .. os.getenv("TEST_ORG_ID") .. "/issues",
          method = "POST",
          body = {
            data = {
              type = "issue",
              attributes = {
                risk_factors = {{ name = "deployed", resource_id = "app-xyz" }}
              }
            }
          }
        })
        state.deployed_issue_id = res.body.data.id
      end
    end,

    ["operation:finished"] = function(event, data)
      -- Clean up after each test
      if state.deployed_issue_id then
        http({
          url = data.server_url .. "/issues/" .. state.deployed_issue_id,
          method = "DELETE"
        })
        state.deployed_issue_id = nil
      end
    end,
  },

  exported_functions = {
    deployed_issue_id = function()
      return state.deployed_issue_id
    end,
  }
}

return exports
```

```yaml
getRiskFactors_deployed:
  target: source-oas:getIssueRiskFactors
  parameters:
    path:
      issue_id: ${functions:deployed_issue_id}
```

---

## Expected response matchers

### Validate specific field values

```yaml
expected:
  response:
    statusCode: 200
    body:
      data:
        type: "issue"
        attributes:
          severity: "high"
```

### Validate against dataset value

```yaml
expected:
  response:
    statusCode: 200
    body: ${equalTo(issue-data:issues.expected)}
```

### Validate discriminator property in response

```yaml
expected:
  response:
    statusCode: 200
    body:
      data:
        attributes:
          risk_factors:
            - name: "deployed" # assert the discriminator came back correctly
```

### Let Drift validate schema automatically

Omitting `body` from `expected` causes Drift to validate the response against the OpenAPI schema automatically.

For a full worked example, see the "Determining test count" section in `schema-patterns.md`.

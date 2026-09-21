---
name: asyncapi-parser
description: >
  Parses AsyncAPI 3.x specs and generates Drift test cases from them.
  Use whenever the user wants to generate, write, or scaffold Drift tests
  from an AsyncAPI spec — especially when the spec contains complex message
  schemas: oneOf/anyOf/allOf, discriminators, polymorphism, $ref chains,
  or multiple message variants. Use when the user wants to test async
  event-driven services (Kafka, SNS, SQS), when they ask to "create tests
  for a channel", "cover all message variants", "generate test cases from
  the AsyncAPI spec", or says anything like "each viable combination of
  messages". Use when the user is trying to understand what payload variants
  a message schema produces, or when they paste an AsyncAPI operation and
  ask what tests to write.

argument-hint: "[path/to/asyncapi.yaml]"
metadata:
  context: fork
  agent: general-purpose
---

# AsyncAPI Parser Skill

> **AsyncAPI version:** This skill targets AsyncAPI 3.x (3.0 and 3.1). AsyncAPI 2.x is NOT supported by Drift — if the spec has `asyncapi: "2.x.x"`, tell the user and stop.

## Reference files

- [`references/asyncapi-schema-patterns.md`](references/asyncapi-schema-patterns.md) — how to read and enumerate AsyncAPI 3.x message schemas (oneOf / anyOf / allOf / discriminator / const / correlationId / optional payload fields)
- [`references/asyncapi-drift-mapping.md`](references/asyncapi-drift-mapping.md) — how to map each execution mode and payload variant to Drift YAML, including trigger/probe patterns, `expected` structure per mode, and naming conventions

## Workflow

### 1. Locate the operation

Extract only what's needed:

```bash
# Find the operation block
grep -n "sendOrderCreated\|receiveInventoryAdjusted" asyncapi.yaml

# Read the operations block and its channel/messages refs
grep -n "^operations:" asyncapi.yaml
```

From the operation block extract:
- `action` — `send` or `receive`
- `channel.$ref` — resolves to a channel name in `channels:`
- `messages[]` — list of `$ref` to message objects
- `reply` block — present only for request-reply interactions

From the channel block:
- `address` — the topic/queue name

From the message block (via `components.messages`):
- `correlationId.location` — where Drift finds the correlation ID
- `headers` schema — header fields
- `payload` schema — the message payload (may be complex: oneOf, anyOf, allOf)

### 2. Resolve $refs recursively

1. Grep for `MessageName:` in `components.messages` to find the definition
2. If the payload itself contains refs, follow those into `components.schemas`
3. Stop at primitive types (`string`, `integer`, `boolean`, `array`, `object`, `const`)

`allOf: [$ref: Base, properties: {...}]` is composition — merge all schemas into one full payload. See `references/asyncapi-schema-patterns.md` for all patterns.

### 3. Determine execution mode

Auto-selected by Drift based on `action` + presence of `reply` block:

| operation.action | reply block | mode | Drift role |
|---|---|---|---|
| `send` | absent | `async-observe` | Drift subscribes and captures |
| `receive` | absent | `async-inject` (+ probe) or `async-inject-capture` (+ probe-topic) | Drift publishes |
| `send` | present | `async-request-reply` | Drift publishes request, captures reply |

**Critical:** `action` reflects the **application's** perspective, not Drift's. `send` means your service publishes — Drift subscribes. `receive` means your service consumes — Drift publishes.

### 4. Enumerate payload variants

For **each operation** that has multiple message variants, enumerate structurally distinct schema variants. Aim for minimum tests that maximise schema coverage.

| Pattern | Tests to generate |
|---|---|
| `oneOf` / `anyOf` with N branches in payload | N tests — one per branch |
| `discriminator` with N mapping values | N tests — one per discriminator value |
| `allOf` (composition) | 1 test — merge all schemas into one payload |
| `const` field | 1 test (const is a fixed value — no variants) |
| Optional field cluster in payload | 2 tests: one with all optional fields, one with required only |
| `nullable` payload field | 1 null variant only if it changes behaviour |

See `references/asyncapi-schema-patterns.md` for worked examples.

### 5. Generate Drift test cases

For each variant produce a Drift operation block. See `references/asyncapi-drift-mapping.md` for full patterns. Key conventions:

- Name single-variant operations as `{operationId}_{mode}` — e.g. `SendOrderCreated_Observe`
- Name multi-variant operations as `{operationId}_{variant}` — e.g. `ReceiveInventoryAdjusted_commandType`, `ReceiveInventoryAdjusted_minimal`
- Always include `correlation-id` in `parameters` — it is required for message matching
- Always set `timeout-ms` (default 5000ms; increase for slow services)
- For `async-observe` and `async-request-reply`: include a `trigger` hook — Drift cannot make your service publish
- For `async-inject`: include a `probe` hook to verify side effects, OR use `probe-topic` for race-condition-free capture
- `expected.headers` + `expected.payload` for message capture modes; `expected` matches probe stdout JSON for `async-inject` mode
- Omitting an `expected.payload` field lets Drift validate it against the AsyncAPI message schema automatically; add explicit field assertions only when asserting specific variant values (e.g. the discriminator property came back correctly)

### Output format

Always produce:

1. **Analysis** — operation name, action, channel address, execution mode, message schema patterns found, how many test variants will be generated and why
2. **Drift operations YAML** — the complete `operations:` block, ready to paste into a test file
3. **Trigger/probe hooks** — shell scripts or Lua function stubs if needed (label as FILL_IN where service-specific)
4. **Gaps** — payload combinations intentionally excluded, with reason

### Example

Given `sendOrderCreated` (action: send, payload has `const: order.created` on `eventType`):

```yaml
operations:
  SendOrderCreated_Observe:
    target: async-send:sendOrderCreated:orderCreated
    description: "Observe the order.created event after trigger fires"
    parameters:
      correlation-id: send-order-created-001
      timeout-ms: 5000
      orderId: ORD-100
      customerId: CUST-9
    trigger:
      executable-type: command
      value: python3
      parameters:
        args:
          - ./hooks/trigger-send.py
          - --correlation-id
          - ${parameters.correlation-id}
          - --order-id
          - ${parameters.orderId}
          - --customer-id
          - ${parameters.customerId}
      timeout-ms: 2000
    expected:
      headers:
        correlation-id: ${parameters.correlation-id}
      payload:
        eventType: order.created
        orderId: ${parameters.orderId}
        customerId: ${parameters.customerId}
        status: created
```

# AsyncAPI Schema Patterns

How to read and enumerate AsyncAPI 3.x message schemas to determine how many Drift test variants to generate. Read alongside `asyncapi-drift-mapping.md` which covers how to turn enumerated variants into Drift YAML.

---

## AsyncAPI 3.x document structure

```
asyncapi: 3.1.0
info: ...
servers: ...           # broker connection (Kafka, SNS, SQS)
channels:              # topic/queue definitions
  <channelId>:
    address: <topic>   # actual topic/queue name
    messages:
      <msgId>: { $ref: "#/components/messages/<MsgName>" }
operations:            # what the application does
  <operationId>:
    action: send | receive
    channel: { $ref: "#/channels/<channelId>" }
    messages:
      - { $ref: "#/channels/<channelId>/messages/<msgId>" }
    reply: ...         # only present for request-reply
components:
  messages:
    <MsgName>:
      correlationId: { location: "$message.header#/correlation-id" }
      headers: <schema>
      payload: <schema>
  schemas:
    <SchemaName>: <schema>
```

---

## correlationId

Tells Drift where to find the message correlation identifier used for test-run matching.

```yaml
correlationId:
  location: "$message.header#/correlation-id"
```

`$message.header#/correlation-id` means: look in the message headers, at the key `correlation-id`.
`$message.payload#/correlationId` means: look in the payload body.

If no `correlationId` is declared in the message, Drift generates a UUID. You can override with `correlation-id` in the operation's `parameters` block.

---

## const fields

A `const` value is fixed — it never varies between tests. Do not generate variants for it.

```yaml
payload:
  type: object
  properties:
    eventType:
      type: string
      const: order.created    # always "order.created" — no variants needed
    orderId:
      type: string
```

Generate 1 test. The `expected.payload` should assert `eventType: order.created` explicitly.

---

## oneOf / anyOf in payload

Each branch is a structurally distinct message type. Generate N tests — one per branch.

```yaml
payload:
  oneOf:
    - $ref: "#/components/schemas/StandardShipment"
    - $ref: "#/components/schemas/ExpressShipment"
    - $ref: "#/components/schemas/InternationalShipment"
```

→ 3 tests: one per schema branch. Use a discriminator property (e.g. `shipmentType`) to distinguish if present.

---

## discriminator in payload

When `oneOf`/`anyOf` uses a discriminator, generate N tests — one per mapping value.

```yaml
payload:
  oneOf:
    - $ref: "#/components/schemas/AdjustmentCommand"
    - $ref: "#/components/schemas/ReservationCommand"
  discriminator:
    propertyName: commandType
    mapping:
      adjustment: "#/components/schemas/AdjustmentCommand"
      reservation: "#/components/schemas/ReservationCommand"
```

→ 2 tests: `commandType: adjustment` and `commandType: reservation`.

---

## allOf (composition)

Merge all referenced schemas and local properties into one full payload. Generate 1 test.

```yaml
payload:
  allOf:
    - $ref: "#/components/schemas/BaseEvent"
    - type: object
      properties:
        sku: { type: string }
        quantityDelta: { type: integer }
```

→ 1 test. Payload must include all required fields from `BaseEvent` plus `sku` and `quantityDelta`.

---

## Optional payload fields

Generate 2 tests: one with all optional fields included, one with required fields only.

```yaml
payload:
  type: object
  required: [commandType, sku]
  properties:
    commandType: { type: string }
    sku: { type: string }
    reason: { type: string }        # optional
    warehouseId: { type: string }   # optional
```

→ 2 tests: `_withOptionals` (includes reason + warehouseId) and `_minimal` (commandType + sku only).

---

## Nested $ref chains

Follow each `$ref` to its definition in `components.schemas`. Stop at primitive types.

```bash
# Find schema definition
grep -n "^  StandardShipment:" asyncapi.yaml
# Follow nested refs
grep -n "BaseShipment:\|ShipmentAddress:" asyncapi.yaml
```

After resolving, treat the merged schema as a flat set of properties for variant enumeration.

---

## Multiple messages on one operation

An operation may declare multiple message types (polymorphic channel):

```yaml
operations:
  receiveCommand:
    messages:
      - $ref: "#/channels/commands/messages/adjustmentMsg"
      - $ref: "#/channels/commands/messages/reservationMsg"
```

Treat each message ref as a separate oneOf branch → generate one test per message type.

---

## Determining test count

| Scenario | Formula |
|---|---|
| 1 message, const eventType, no variants | 1 test |
| 1 message, oneOf with N branches in payload | N tests |
| 1 message, discriminator with N values | N tests |
| 1 message, optional field cluster | 2 tests (with + without optionals) |
| N message refs on one operation | N tests |
| allOf composition | 1 test |
| send with reply (request-reply) | 1 test per request variant |

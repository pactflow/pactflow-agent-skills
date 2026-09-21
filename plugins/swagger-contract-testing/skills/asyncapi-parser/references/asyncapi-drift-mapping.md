# AsyncAPI Drift Mapping Reference

How to map each AsyncAPI execution mode and payload pattern to Drift test case YAML. Read alongside `asyncapi-schema-patterns.md` which covers how to enumerate the variants.

---

## Naming conventions

Single variant:
```
{operationId}_{Mode}
```
e.g. `SendOrderCreated_Observe`, `ReceiveInventoryAdjusted_Inject`, `RequestPriceQuote_SendReceive`

Multiple payload variants:
```
{operationId}_{variantName}
```
e.g. `ReceiveCommand_adjustment`, `ReceiveCommand_reservation`, `ReceiveShipment_express`, `ReceiveShipment_minimal`

---

## async-observe (send action, no reply)

Your service publishes; Drift subscribes, waits for the trigger, then captures and validates.

Required: a `trigger` hook that causes your service to publish.

```yaml
operations:
  SendOrderCreated_Observe:
    target: <source>:sendOrderCreated:orderCreated
    description: "Observe the order.created event after the trigger fires"
    parameters:
      correlation-id: send-order-created-001   # must be unique per test run
      timeout-ms: 5000
      # add any payload-influencing params the trigger needs
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

**Rules:**
- `trigger` fires AFTER Drift subscribes — no race condition for the capture
- The trigger MUST propagate `${parameters.correlation-id}` into the published message's header; if it does not, Drift times out
- Omit fields from `expected.payload` to let Drift validate them against the AsyncAPI schema automatically; add them only when asserting specific values

---

## async-inject (receive action, probe command)

Drift publishes the message; your service consumes it; a `probe` command reads side effects and emits JSON to stdout.

```yaml
operations:
  ReceiveInventoryAdjusted_Inject:
    target: <source>:receiveInventoryAdjusted:inventoryAdjusted
    description: "Publish an inventory.adjusted command and verify recorded state"
    parameters:
      correlation-id: receive-inventory-adjusted-001
      payload:
        commandType: inventory.adjusted
        sku: SKU-RED-CHAIR
        quantityDelta: -2
        reason: reservation
    probe:
      executable-type: command
      value: python3
      parameters:
        args:
          - ./hooks/probe-receive.py
          - --correlation-id
          - ${parameters.correlation-id}
      timeout-ms: 3000
    expected:
      status: processed
      correlationId: ${parameters.correlation-id}
      sku: ${parameters.payload.sku}
      quantityDelta: ${parameters.payload.quantityDelta}
      reason: ${parameters.payload.reason}
```

**Rules:**
- `expected` matches the JSON the probe writes to stdout — not the message schema
- The probe must emit JSON on stdout; anything else on stdout causes a parse error (use stderr for logs)
- Probe receives the correlation-id as an argument; service must record state keyed by it
- There is an inherent race condition: probe may execute before the service has finished processing; add sleep or retry in the probe script if needed

---

## async-inject-capture (receive action, probe-topic)

Race-condition-free alternative to `async-inject`. Drift subscribes to a secondary topic before publishing; your service publishes a result there.

```yaml
operations:
  ReceiveInventoryAdjusted_InjectCapture:
    target: <source>:receiveInventoryAdjusted:inventoryAdjusted
    description: "Inject inventory.adjusted and capture probe-topic result"
    parameters:
      probe-topic: drift.examples.inventory-adjusted-probe
      correlation-id: receive-inventory-adjusted-capture-001
      timeout-ms: 5000
      payload:
        commandType: inventory.adjusted
        sku: SKU-RED-CHAIR
        quantityDelta: -2
        reason: reservation
    expected:
      headers:
        correlation-id: ${parameters.correlation-id}
      payload:
        status: processed
        sku: ${parameters.payload.sku}
        quantityDelta: ${parameters.payload.quantityDelta}
        reason: ${parameters.payload.reason}
```

**Rules:**
- `probe-topic` must be on the same broker as the main channel
- `expected` matches the message captured from the probe-topic (headers + payload), not probe stdout
- Use this mode when your service already publishes a result/acknowledgement message

---

## async-request-reply (send action, reply block present)

Drift publishes the request with a reply-to header; your service publishes the correlated reply; Drift captures it.

No `trigger` needed — Drift is the publisher.

```yaml
operations:
  RequestPriceQuote_SendReceive:
    target: <source>:requestPriceQuote:priceQuoteRequest
    description: "Publish price.quote request and capture correlated reply"
    parameters:
      correlation-id: request-price-quote-001
      timeout-ms: 5000
      payload:
        requestType: price.quote
        sku: SKU-RED-CHAIR
        quantity: 3
      headers:
        correlation-id: ${parameters.correlation-id}
    expected:
      payload:
        responseType: price.quote
        sku: ${parameters.payload.sku}
        quantity: ${parameters.payload.quantity}
        quotedUnitPrice: 149.0
        quotedTotalPrice: 447.0
        currency: USD
        availability: in-stock
      headers:
        correlation-id: ${parameters.correlation-id}
```

**Rules:**
- `expected` describes the **reply** message, not the request
- `target` names the **request** operation; Drift derives the reply channel from the operation's `reply` block
- If the reply channel is not declared in the AsyncAPI document, add `reply-channel: <topic>` under `parameters`
- Drift captures only the first matching reply; it does not verify reply streams

---

## Multiple payload variants

When the message payload has oneOf/anyOf or multiple message refs, generate one operation per variant.

```yaml
operations:
  ReceiveCommand_adjustment:
    target: <source>:receiveCommand:adjustmentMsg
    parameters:
      correlation-id: receive-command-adjustment-001
      payload:
        commandType: adjustment
        sku: SKU-RED-CHAIR
        quantityDelta: -2
    probe:
      executable-type: command
      value: python3
      parameters:
        args:
          - ./hooks/probe-command.py
          - --correlation-id
          - ${parameters.correlation-id}
      timeout-ms: 3000
    expected:
      status: processed
      commandType: ${parameters.payload.commandType}

  ReceiveCommand_reservation:
    target: <source>:receiveCommand:reservationMsg
    parameters:
      correlation-id: receive-command-reservation-001
      payload:
        commandType: reservation
        sku: SKU-BLUE-TABLE
        quantity: 1
    probe:
      executable-type: command
      value: python3
      parameters:
        args:
          - ./hooks/probe-command.py
          - --correlation-id
          - ${parameters.correlation-id}
      timeout-ms: 3000
    expected:
      status: processed
      commandType: ${parameters.payload.commandType}
```

---

## Lua function hooks

Preferred when the trigger/probe logic belongs with the test suite rather than external scripts.

Declare the Lua file in `sources`:

```yaml
sources:
  - name: hooks
    path: ./hooks.lua
```

Then reference as `executable-type: lua-function`:

```yaml
trigger:
  executable-type: lua-function
  value: trigger_order_created
  timeout-ms: 2000
```

```lua
local function trigger_order_created(correlation_id, order_id, customer_id)
  -- call your service's REST API or publish directly via a Lua Kafka client
  return true
end

return {
  exported_functions = {
    trigger_order_created = trigger_order_created
  }
}
```

---

## Test file top-level structure

Every AsyncAPI Drift test file must include:

```yaml
# yaml-language-server: $schema=https://download.pactflow.io/drift/schemas/drift.testcases.v1.schema.json
drift-testcase-file: v1
title: "<service> AsyncAPI verification"

sources:
  - name: <source-name>              # referenced in target field
    path: ./asyncapi/<service>.asyncapi.yaml

plugins:
  - name: asyncapi     # reads the AsyncAPI document
  - name: kafka        # transport; use aws-messaging for SNS/SQS
  - name: json         # payload validation

operations:
  # operations go here
```

AWS SNS/SQS: replace `kafka` with `aws-messaging`. SNS/SQS do not support request-reply.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Capture timeout after trigger ran | Trigger published a different correlation ID | Verify trigger propagates `${parameters.correlation-id}` |
| Capture timeout, trigger did not run | Wrong path to trigger script (relative to test file) | Use path relative to the test case YAML file |
| Probe false positive | Prior state not cleared between runs | Add state-clearing step at start of probe |
| Intermittent probe failures | Probe runs before service finishes | Add retry loop or sleep in probe |
| `async-observe` when `reply` expected | Operation has no reply block | Add `reply-channel` to parameters, or add reply block to AsyncAPI spec |
| Schema validation failure on publish | Payload missing required field | Check `components.messages.<name>.payload.required` |

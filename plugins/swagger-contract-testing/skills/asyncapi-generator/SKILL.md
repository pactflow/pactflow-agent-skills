---
name: asyncapi-generator
description: >
  Generates an AsyncAPI 3.x YAML spec from a service codebase using ripwire when no spec exists.
  Invoke this skill whenever the user needs an AsyncAPI spec for an event-driven service that
  doesn't have one published — phrases like "generate an asyncapi spec from the code", "there's
  no asyncapi for this service", "document our Kafka topics as a spec", "create a spec from the
  producers and consumers", "reverse-engineer the event contract", or any time a Drift/AsyncAPI
  testing workflow (asyncapi-parser, drift-testing) is blocked because the spec is missing.
  Uses ripwire to find message producers and consumers and extract topics/queues and payload
  shapes across Kafka, SNS/SQS, RabbitMQ/AMQP, NATS, Google Pub/Sub, MQTT, Redis and WebSocket
  clients in Node.js, Python, Java/Kotlin, Go, Ruby and other ripwire-supported languages.
  Always ask for the codebase path if not provided. Requires ripwire on PATH.
---

# AsyncAPI Generator

Generates an AsyncAPI **3.x** spec by statically analysing a service codebase with ripwire.
The spec may be incomplete (stub payloads where the shape can't be resolved), but it is always
valid AsyncAPI 3.x and immediately usable as input to `asyncapi-parser` and Drift.

This is the async counterpart of `oas-generator`. The key difference: HTTP routes are declared in
one place, but messaging topology is scattered — a topic name appears in a producer call, a
consumer decorator, a config file and an env var. Most of the work is finding every send/receive
site and resolving the channel name behind it.

**Prerequisites:** `ripwire` on PATH. If absent, see `pact-coverage/references/install-ripwire.md`.
AsyncAPI 2.x is not supported by Drift, so always emit `asyncapi: "3.0.0"`.

Read [`references/broker-patterns.md`](references/broker-patterns.md) for grep patterns per
broker/library. Read it in Step 2; don't load it earlier.

---

## Step 1 — Identify broker and language

```bash
ripwire <service-root> --for="message producers and consumers publishing and subscribing to topics queues"
```

Confirm with dependency manifests (`package.json`, `pom.xml`/`build.gradle`, `requirements.txt`/
`pyproject.toml`, `go.mod`, `Gemfile`): `kafkajs`, `spring-kafka`, `confluent-kafka`, `aws-sdk`
SNS/SQS clients, `boto3`, `amqplib`/`pika`, `nats`, `google-cloud-pubsub`, `mqtt`, `ws`.

A service often uses more than one broker; record all of them. If nothing messaging-related is
found, tell the user — don't invent channels.

---

## Step 2 — Find every send and receive site

Use the patterns in `references/broker-patterns.md` for the detected broker(s), passed to
`ripwire <root> --regex='<pattern>'`. Use `--regex`, not `--grep`: `--grep` is a literal match, so a
pattern with `|` alternation returns zero hits, and ripwire reports that zero as complete. If a
search returns `files="0"`, the root path is wrong or unindexed, not proof that nothing publishes.
Run each applicable pattern and deduplicate. For every hit, note the enclosing symbol (`in=`) and
classify it:

- **send** — this service publishes (producer, `publish`, `send`, `emit`, `sendMessage`)
- **receive** — this service consumes (listener, handler, `subscribe`, `@KafkaListener`, `consume`)

Direction matters: AsyncAPI 3 `action` is from *this application's* point of view, and getting it
backwards makes Drift test the wrong side. A consumer is `receive`, even though the topic is
"produced to" by someone else.

Fallback for unfamiliar libraries:

```bash
ripwire <root> --for="publish subscribe topic queue message handler"
```

Expand top-ranked symbols and keep those that take a topic/queue name plus a payload.

---

## Step 3 — Resolve channel addresses

The channel name is usually not a literal at the call site. Resolve in this order and stop at the
first that works:

1. **String literal** at the call site.
2. **Constant/enum** — `--expand` the referenced symbol, or `ripwire <root> --grep="<CONST_NAME>"`.
3. **Config / env** — check `application.yml`, `.env*`, `config/`, `docker-compose.yml`,
   Terraform/CDK/CloudFormation (SNS topic and SQS queue names are often defined there).
4. **Templated** (`orders.${env}.created`) — keep the template in `address` and add a `parameters`
   entry only if the variable is clearly a runtime parameter; otherwise substitute the most
   likely default and add a comment.
5. **Unresolvable** — use a placeholder address named after the entity or env var, not the enclosing function (`TODO.unresolved.sent-topic` for `SENT_TOPIC_ARN`, not `TODO.unresolved.poll`)
   and set `x-address-source: unresolved`. Don't drop the channel: a known-but-unnamed channel
   is more useful than a silent gap.

Mark the result with `x-address-source`, choosing by where the **final `address` string** came from:

| value | meaning | example |
| --- | --- | --- |
| `literal` | the string is written at the call site | `topic: 'orders.created'` |
| `constant` | defined once in code and referenced by name | `ORDER_CREATED` in `topics.js` |
| `config` | defined in a checked-in config/IaC file (`application.yml`, Terraform, CDK) | `app.topics.invoice-issued` |
| `inferred` | only a hint exists, such as a comment, example or docs; the name is a best guess | the last segment of an example queue URL in a comment |
| `unresolved` | no usable name exists in the repo; the value lives in an env var or secret | `SENT_TOPIC_ARN` read from `os.environ` |

Never copy a raw env reference (`${SENT_TOPIC_ARN}`) or an example URL into `address`. Drift will
try to use whatever is there, so a guess must be labelled `inferred` and a missing name must use
the `TODO.unresolved.*` placeholder. For SQS, use the queue **name** (final URL segment), not the URL.

---

## Step 4 — Build the operation inventory

One row per (action, channel, message):

| operationId | action | channel address | handler/producer symbol | broker |
| --- | --- | --- | --- | --- |

- `operationId`: camelCase verb + entity, e.g. `publishOrderCreated`, `onPaymentFailed`. Make them
  unique and stable — Drift test names derive from them.
- Same channel with both send and receive sites → two operations, one channel.
- Same action + channel from several call sites → one operation (keep the first symbol).

---

## Step 5 — Extract message payload and headers

For each operation, `--expand` the producer or handler symbol and read the payload shape:

**Send (producer)** — the object passed to publish:
- Object literal / dict / `Map.of` / builder → list its keys.
- A typed DTO/event class, protobuf/Avro/JSON-Schema file → `--expand` the type and use its fields.
- Serialisation (`JSON.stringify`, `json.dumps`, `ObjectMapper.writeValueAsString`, `Buffer.from`)
  tells you the `contentType` (`application/json`, `application/avro`, `application/x-protobuf`).

**Receive (consumer)** — what the handler reads:
- Fields accessed on the parsed message (`msg.orderId`, `event["total"]`, `record.value().getId()`).
- A typed parameter (`@Payload OrderCreated e`, `data: OrderCreatedModel`) → expand the type.
- Validation (`@NotNull`, Pydantic required fields, `if (!msg.id) throw`) → `required`.

**Headers and correlation**: look for `headers:` / `properties` / `MessageAttributes` and for any
correlation or trace id (`correlationId`, `correlation-id`, `traceparent`). If one exists, emit
`correlationId.location` — Drift uses it to match test messages.

**Discriminators**: a handler that switches on `type`/`eventType` handles several message
variants. Emit one message per variant and `oneOf` them on the channel, rather than one muddy
union object — `asyncapi-parser` enumerates variants from exactly this structure.

**When inference fails**: emit `payload: { type: object }` with `x-schema-source: stub`. Never skip
the operation. Types follow the same rules as `oas-generator`: default to `string` unless code makes
it obvious; mark discovered fields `x-schema-source: inferred`; use `required` only when the code
clearly fails without the field.

**Reply**: only emit `reply` when the code genuinely does request-reply (RPC over a reply-to
queue, Kafka reply topic, `correlationId` + `replyTo`). Otherwise, don't invent it.

---

## Step 6 — Assemble the AsyncAPI YAML

Use `$ref`s into `components` so messages are reusable — a message that is sent by one service and
received by another should be defined once.

```yaml
asyncapi: "3.0.0"
info:
  title: "<ServiceName> Events"
  version: "0.0.0-generated"
  description: "Auto-generated from source by asyncapi-generator. Review and refine before production use."
servers:
  primary:
    host: "localhost:9092"          # from config if found, else placeholder
    protocol: kafka                 # kafka | amqp | mqtt | nats | sns | sqs | googlepubsub | ws
channels:
  orderCreated:
    address: "orders.created"
    x-address-source: literal
    messages:
      OrderCreated:
        $ref: "#/components/messages/OrderCreated"
operations:
  publishOrderCreated:
    action: send
    channel:
      $ref: "#/channels/orderCreated"
    messages:
      - $ref: "#/channels/orderCreated/messages/OrderCreated"
components:
  messages:
    OrderCreated:
      contentType: application/json
      correlationId:
        location: "$message.header#/correlation-id"
      payload:
        $ref: "#/components/schemas/OrderCreatedPayload"
  schemas:
    OrderCreatedPayload:
      type: object
      x-schema-source: inferred
      required: [orderId]
      properties:
        orderId: { type: string }
        total: { type: number }
```

Structure rules that commonly go wrong:
- Operation `channel` is a `$ref` to `#/channels/<id>`; operation `messages` are refs to
  `#/channels/<id>/messages/<id>`, not to `components`. Channel `messages` ref `components`.
- `address` is the real topic/queue name; the channel key is just an identifier.
- Protocol-specific details (Kafka partitions/keys, SQS visibility timeout, AMQP exchange/routing
  key) go under `bindings` only when the code sets them. Don't add speculative bindings.
- Declare every distinct broker as its own entry under `servers`; omit credentials and secrets.

---

## Step 7 — Validate, write and report

If `asyncapi` CLI or `npx @asyncapi/cli` is available, validate: `asyncapi validate <file>`.
Otherwise self-check: every `$ref` resolves, every operation's channel exists, `asyncapi` is 3.x.

Save to `<service-root>/asyncapi-generated.yaml` unless the user gives a path, then report:

```
Generated AsyncAPI written to: <path>
Channels:     N   (literal: N, constant: N, config: N, inferred: N, unresolved: N)
Operations:   N   (send: N, receive: N)
Messages:     N
  Inferred:   N   (payload fields extracted from code)
  Stubs:      N   (no schema found — empty payload emitted)
Brokers:      kafka, sqs, …
```

List unresolved channel addresses and stub payloads explicitly, since those are what the user must
fix. Remind them that stubs create false gaps in coverage and weak Drift tests, and that
send/receive direction is inferred from code and worth a quick review. Offer to hand the spec to
`asyncapi-parser` to scaffold Drift tests.

---

## Tips for accuracy

- **Producers wrap clients.** Services often hide `producer.send` inside an `EventPublisher` class.
  Use `--callers=<wrapper>` to find the real topics and payloads at each call site.
- **Framework magic hides topology.** Spring Cloud Stream binds channels by name in YAML
  (`spring.cloud.stream.bindings.*`), NestJS uses `@EventPattern`/`@MessagePattern`, Celery uses
  task names — check config as well as code.
- **Dead letter / retry topics** (`*.dlq`, `*.retry`) are real channels; include them if code
  publishes to them explicitly, skip ones created implicitly by the framework.
- **Test and mock code** produces false positives. Exclude `test/`, `spec/`, `__tests__/`, `mocks/`.
- If ripwire returns `over_ceiling=1`, narrow the root to the `src/` (or messaging) directory.

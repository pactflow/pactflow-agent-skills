# Broker Patterns

ripwire patterns for locating send/receive sites, and what each tells you. Run
`ripwire <root> --regex='<pattern>'`; use the `in=` attribute of a hit as the enclosing symbol,
then `--expand` it.

**Use `--regex=`, not `--grep=`.** `--grep=` is a literal search, so alternation like `a\|b`
silently returns zero hits (and `complete=1` makes that zero look authoritative). In `--regex=`
patterns `|` is alternation and a literal `(` or `.` must be escaped (`\(`, `\.`). Wrap the
pattern in double quotes if it contains a single quote. If a search returns `files="0"`, check
the root path before concluding there are no producers.

## Contents

- Kafka
- AWS SNS / SQS
- RabbitMQ / AMQP
- NATS
- Google Pub/Sub
- MQTT
- Redis pub/sub and streams
- WebSocket
- Framework abstractions
- Protocol → `servers.protocol` value

______________________________________________________________________

## Kafka

- **Node (kafkajs)**
  - send: `producer\.send\(|\.sendBatch\(` — topic in `{ topic: ..., messages: [...] }`
  - receive: `consumer\.subscribe\(|eachMessage|eachBatch` — topic in `subscribe({ topic })`
- **Python**
  - send: `\.produce\(|KafkaProducer|\.send\(`
  - receive: `\.subscribe\(|KafkaConsumer|\.poll\(`
- **Java/Kotlin**
  - send: `kafkaTemplate\.send\(|ProducerRecord|@SendTo`
  - receive: `@KafkaListener|@StreamListener|ConsumerRecord` — `topics =` attribute
- **Go**
  - send: `kafka\.Writer|WriteMessages|sarama\.ProducerMessage`
  - receive: `kafka\.Reader|ReadMessage|ConsumePartition`

Message key → `bindings.kafka.key` only if the code sets it. Value serialisation: Avro/Protobuf
usually means a schema registry; look for `.avsc`/`.proto` files and reference the type name.

## AWS SNS / SQS

- **Node**
  - send: `PublishCommand|sns\.publish\(|SendMessageCommand|sqs\.sendMessage\(`
  - receive: `ReceiveMessageCommand|sqs\.receiveMessage\(|Consumer\.create\(` (sqs-consumer)
- **Python**
  - send: `\.publish\(TopicArn|send_message\(|\.send_messages\(`
  - receive: `receive_message\(|\.receive_messages\(|@sqs_listener`
- **Java**
  - send: `snsClient\.publish|sqsTemplate\.send|@SendTo`
  - receive: `@SqsListener|@JmsListener`

Topic ARNs and queue URLs are usually in env/config or IaC (`aws_sns_topic`, `aws_sqs_queue`,
CDK `new Topic\(`/`new Queue\(`). Use the resource name as `address`, protocol `sns` or `sqs`.
An SNS→SQS subscription means the service *receives* from the queue, not from the topic.
`MessageAttributes` → message `headers`.

## RabbitMQ / AMQP

- **Node (amqplib)**
  - send: `channel\.publish\(|sendToQueue\(`
  - receive: `channel\.consume\(`
- **Python (pika)**
  - send: `basic_publish\(`
  - receive: `basic_consume\(|start_consuming`
- **Java**
  - send: `rabbitTemplate\.convertAndSend|AmqpTemplate`
  - receive: `@RabbitListener`

Channel `address` = queue name for consume, or routing key for publish. Exchange and routing key
go under `bindings.amqp` only when set in code.

## NATS

`nc\.publish\(|\.request\(` / `\.subscribe\(|\.queueSubscribe\(`. The subject is the channel
address; wildcards (`orders.*`, `orders.>`) stay in `address`. `.request\(` is request-reply →
emit `reply`.

## Google Pub/Sub

`topic\.publish|publishMessage|PublisherClient` / `subscription\.on\('message'|subscribe\(|StreamingPull|SubscriberClient`.
Protocol `googlepubsub`.

## MQTT

`client\.publish\(` / `client\.subscribe\(|on\('message'`. Topic strings often contain `+`/`#`
wildcards and `{id}`-like segments; convert variable segments to `parameters`.

## Redis pub/sub and streams

`\.publish\(|XADD|xadd` / `\.subscribe\(|psubscribe|XREAD|xreadgroup`. AsyncAPI has no
dedicated Redis protocol; use `redis` as the protocol string.

## WebSocket

`ws\.send\(|socket\.emit\(|io\.emit\(` / `ws\.on\('message'|socket\.on\(|io\.on\(`. Event names
(`socket.emit('chat:message')`) become channel addresses; protocol `ws`.

______________________________________________________________________

## Framework abstractions

| Framework | Where the topology lives |
| --- | --- |
| Spring Cloud Stream | `spring.cloud.stream.bindings.<name>.destination` in YAML; `Function<..>` beans are the handlers (input = receive, output = send) |
| NestJS | `@EventPattern(...)`, `@MessagePattern(...)` (receive); `client.emit(`/`client.send(` (send) |
| Celery | `@app.task` names + `delay(`/`apply_async(` |
| MassTransit / NServiceBus (.NET) | `IConsumer<T>` / `IHandleMessages<T>` — message type name is the channel |
| Axon / Eventuate | event classes + `@EventHandler` |

## Protocol → `servers.protocol`

kafka → `kafka` · SNS → `sns` · SQS → `sqs` · RabbitMQ → `amqp` · NATS → `nats` ·
Pub/Sub → `googlepubsub` · MQTT → `mqtt` · WebSocket → `ws` · Redis → `redis`

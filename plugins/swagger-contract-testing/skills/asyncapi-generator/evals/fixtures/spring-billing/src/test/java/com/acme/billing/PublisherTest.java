// test noise: must NOT produce a channel
class PublisherTest { void t() { kafkaTemplate.send("test.only.topic", "k", "v"); } }

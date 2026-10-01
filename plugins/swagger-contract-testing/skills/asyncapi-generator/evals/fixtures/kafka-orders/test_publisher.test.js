// test noise: must NOT produce a channel
producer.send({ topic: 'test.fake.topic', messages: [] });

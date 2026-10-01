const { PAYMENT_EVENTS } = require('./topics');

async function start(consumer, orders) {
  await consumer.subscribe({ topic: PAYMENT_EVENTS });
  await consumer.run({
    eachMessage: async ({ message }) => {
      const event = JSON.parse(message.value.toString());
      if (!event.orderId) throw new Error('orderId required');
      switch (event.type) {
        case 'payment.succeeded': return orders.markPaid(event.orderId, event.amount);
        case 'payment.failed': return orders.markFailed(event.orderId, event.reason);
      }
    },
  });
}
module.exports = { start };

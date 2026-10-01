const { ORDER_CREATED } = require('./topics');

async function publishOrderCreated(producer, order) {
  await producer.send({
    topic: ORDER_CREATED,
    messages: [{
      key: order.id,
      headers: { 'correlation-id': order.correlationId },
      value: JSON.stringify({ orderId: order.id, customerId: order.customerId, total: order.total, items: order.items }),
    }],
  });
}
module.exports = { publishOrderCreated };

package com.acme.billing;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class PaymentListener {
    private final InvoiceService invoices;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    public PaymentListener(InvoiceService invoices, KafkaTemplate<String, Object> kafkaTemplate) {
        this.invoices = invoices;
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "${app.topics.payment-received}", groupId = "billing")
    public void onPayment(PaymentReceivedEvent event) {
        try {
            invoices.markPaid(event.invoiceId(), event.amountCents());
        } catch (RuntimeException e) {
            kafkaTemplate.send("billing.payments.received.dlq", event.invoiceId(), event);
        }
    }
}

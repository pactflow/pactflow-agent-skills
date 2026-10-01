package com.acme.billing;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class InvoiceEventPublisher {
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final TopicProperties topics;

    public InvoiceEventPublisher(KafkaTemplate<String, Object> kafkaTemplate, TopicProperties topics) {
        this.kafkaTemplate = kafkaTemplate;
        this.topics = topics;
    }

    public void publishIssued(Invoice invoice) {
        kafkaTemplate.send(topics.getInvoiceIssued(), invoice.getId(),
            new InvoiceIssuedEvent(invoice.getId(), invoice.getCustomerId(), invoice.getAmountCents(), invoice.getCurrency(), invoice.getDueDate()));
    }

    public void publishVoided(Invoice invoice, String reason) {
        kafkaTemplate.send(topics.getInvoiceVoided(), invoice.getId(),
            new InvoiceVoidedEvent(invoice.getId(), reason));
    }
}

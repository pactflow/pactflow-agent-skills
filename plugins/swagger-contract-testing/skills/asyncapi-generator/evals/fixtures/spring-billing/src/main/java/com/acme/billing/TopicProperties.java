package com.acme.billing;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.topics")
public class TopicProperties {
    private String invoiceIssued;
    private String invoiceVoided;
    private String paymentReceived;
    // getters/setters omitted
    public String getInvoiceIssued() { return invoiceIssued; }
    public String getInvoiceVoided() { return invoiceVoided; }
    public String getPaymentReceived() { return paymentReceived; }
}

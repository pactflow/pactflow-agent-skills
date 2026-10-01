package com.acme.billing;

import org.springframework.stereotype.Service;

@Service
public class InvoiceService {
    private final InvoiceEventPublisher publisher;
    public InvoiceService(InvoiceEventPublisher publisher) { this.publisher = publisher; }

    public void issue(Invoice invoice) { publisher.publishIssued(invoice); }
    public void voidInvoice(Invoice invoice, String reason) { publisher.publishVoided(invoice, reason); }
    public void markPaid(String invoiceId, long amountCents) { /* persistence */ }
}

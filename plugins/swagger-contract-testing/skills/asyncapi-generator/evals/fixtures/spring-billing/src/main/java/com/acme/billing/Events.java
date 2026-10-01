package com.acme.billing;

import jakarta.validation.constraints.NotNull;

record InvoiceIssuedEvent(String invoiceId, String customerId, long amountCents, String currency, String dueDate) {}
record InvoiceVoidedEvent(String invoiceId, String reason) {}
record PaymentReceivedEvent(@NotNull String invoiceId, @NotNull Long amountCents, String method, String receiptUrl) {}

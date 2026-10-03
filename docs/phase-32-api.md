# Phase 32: Financial REST API Specification

All endpoints are hosted under `/api/v1` and adhere to OAuth2 Bearer token authentication.

---

## 1. Invoice APIs

### `POST /api/v1/patients/{patient_id}/invoices`
- **Description**: Create a new draft invoice.
- **Permission**: `INVOICE_CREATE`
- **Request Body**:
  ```json
  {
    "patient_id": "pat_12345",
    "organization_id": "org_aiims",
    "facility_id": "fac_delhi",
    "currency": "INR",
    "due_at": "2026-10-15T00:00:00Z",
    "notes": "General Consultation & CBC",
    "items": [
      {
        "description": "General OPD Consultation",
        "category": "CONSULTATION",
        "unit_price_in_minor_units": 50000,
        "quantity": 1,
        "tax_in_minor_units": 0,
        "discount_in_minor_units": 0,
        "currency": "INR",
        "appointment_id": "appt_123"
      }
    ]
  }
  ```
- **Response**: `201 Created` (`InvoiceResponse`)

### `GET /api/v1/patients/{patient_id}/invoices`
- **Description**: List authorized patient invoices with status filtering.
- **Permission**: `INVOICE_READ`

### `POST /api/v1/patients/{patient_id}/invoices/{invoice_id}/issue`
- **Description**: Transitions invoice from `DRAFT` to `ISSUED`.
- **Permission**: `INVOICE_ISSUE`

### `POST /api/v1/patients/{patient_id}/invoices/{invoice_id}/cancel`
- **Description**: Cancels an unpaid invoice with mandatory audit reason.
- **Permission**: `INVOICE_CANCEL`

---

## 2. Payment APIs

### `POST /api/v1/patients/{patient_id}/invoices/{invoice_id}/payments`
- **Description**: Initiates a payment transaction. Supports header `Idempotency-Key`.
- **Permission**: `PAYMENT_CREATE`
- **Request Body**:
  ```json
  {
    "invoice_id": "inv_abc123",
    "amount_in_minor_units": 50000,
    "currency": "INR",
    "payment_method": "UPI",
    "idempotency_key": "idemp_unique_key_001"
  }
  ```
- **Response**: `201 Created` (`PaymentResponse`)

### `POST /api/v1/patients/{patient_id}/payments/{payment_id}/verify`
- **Description**: Authoritatively verifies payment status with the gateway.
- **Permission**: `PAYMENT_READ`
- **Request Body**:
  ```json
  {
    "provider_transaction_id": "mock_tx_12345"
  }
  ```

---

## 3. Refund APIs

### `POST /api/v1/patients/{patient_id}/payments/{payment_id}/refund`
- **Description**: Initiates a partial or full refund against a `SUCCEEDED` payment.
- **Permission**: `PAYMENT_REFUND`
- **Request Body**:
  ```json
  {
    "payment_id": "pay_abc123",
    "amount_in_minor_units": 20000,
    "reason": "Overpayment adjustment",
    "idempotency_key": "ref_idemp_key_001"
  }
  ```

---

## 4. Webhook Ingestion API

### `POST /api/v1/webhooks/payments/{provider}`
- **Description**: Receives inbound gateway events (e.g. `MOCK`, `RAZORPAY`).
- **Headers**:
  - `X-Mock-Signature: <hmac-sha256-hex>`
- **Response**: `200 OK`
  ```json
  {
    "status": "ACCEPTED",
    "event_id": "mock_ev_001",
    "provider": "MOCK",
    "transaction_id": "pay_abc123",
    "message": "Webhook event processed successfully"
  }
  ```

---

## 5. Administrative Financial APIs

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin/billing/status` | `ADMIN_BILLING_VIEW` | System flags & parameters |
| `GET` | `/api/v1/admin/billing/providers` | `ADMIN_BILLING_VIEW` | Configured gateway adapters |
| `GET` | `/api/v1/admin/billing/provider-status` | `ADMIN_BILLING_VIEW` | Real-time provider health |
| `POST` | `/api/v1/admin/billing/providers/{provider}/test` | `ADMIN_BILLING_VIEW` | Provider test ping |
| `GET` | `/api/v1/admin/billing/failures` | `ADMIN_BILLING_VIEW` | List failed/unknown transactions |
| `GET` | `/api/v1/admin/billing/reconciliation` | `ADMIN_PAYMENT_RECONCILE` | List discrepancies |
| `POST` | `/api/v1/admin/billing/payments/{payment_id}/reconcile` | `ADMIN_PAYMENT_RECONCILE` | Manual reconciliation |
| `GET` | `/api/v1/admin/billing/refunds` | `ADMIN_REFUND_MANAGE` | All platform refunds |

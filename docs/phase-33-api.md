# Phase 33: Insurance, Prior Auth & Claims REST API Specification

All endpoints are hosted under `/api/v1` and protected with OAuth2 Bearer token authentication.

---

## 1. Insurance Coverage APIs

### `POST /api/v1/patients/{patient_id}/insurance`
- **Description**: Registers a new insurance policy for the patient.
- **Permission**: `INSURANCE_CREATE`

### `GET /api/v1/patients/{patient_id}/insurance`
- **Description**: Lists all insurance coverages for the patient.
- **Permission**: `INSURANCE_READ`

### `GET /api/v1/patients/{patient_id}/insurance/{coverage_id}`
- **Description**: Fetches single policy details with sensitive numbers masked.
- **Permission**: `INSURANCE_READ`

---

## 2. Eligibility & Benefit APIs

### `POST /api/v1/patients/{patient_id}/insurance/eligibility-check`
- **Description**: Performs real-time point-in-time eligibility check via clearinghouse.
- **Permission**: `ELIGIBILITY_CHECK`

### `POST /api/v1/patients/{patient_id}/insurance/benefits`
- **Description**: Queries live benefit coverage, copay, and deductible balances.
- **Permission**: `BENEFITS_READ`

---

## 3. Pre-Authorization APIs

### `POST /api/v1/patients/{patient_id}/authorizations`
- **Description**: Creates a draft prior authorization request.
- **Permission**: `AUTHORIZATION_CREATE`

### `POST /api/v1/patients/{patient_id}/authorizations/{authorization_id}/submit`
- **Description**: Submits the authorization request to the payer.
- **Permission**: `AUTHORIZATION_SUBMIT`

---

## 4. Medical Claims APIs

### `POST /api/v1/patients/{patient_id}/claims`
- **Description**: Drafts a medical claim with validated billable line items.
- **Permission**: `CLAIM_CREATE`

### `POST /api/v1/patients/{patient_id}/claims/{claim_id}/submit`
- **Description**: Submits the claim to the payer clearinghouse idempotently.
- **Header**: `Idempotency-Key` (optional)
- **Permission**: `CLAIM_SUBMIT`

### `POST /api/v1/patients/{patient_id}/claims/{claim_id}/reconcile`
- **Description**: Triggers audit reconciliation against clearinghouse records.
- **Permission**: `CLAIM_RECONCILE`

---

## 5. Webhook Ingestion API

### `POST /api/v1/webhooks/payers/{provider}`
- **Description**: Ingests asynchronous clearinghouse adjudication and auth status updates.
- **Security**: Validates HMAC-SHA256 signature in `X-Payer-Signature` using `PAYER_WEBHOOK_SECRET`.

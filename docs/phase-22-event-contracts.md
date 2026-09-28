# Phase 22 — Versioned Domain Event Contracts

## 1. Event Envelope Contract (v1.0)

All domain events emitted by the HealthSetu backend conform to the following schema:

```json
{
  "event_id": "b8a9cf24-9dfb-4ecb-99f2-39c4fae9b389",
  "event_type": "DOCUMENT_PROCESSING_COMPLETED",
  "event_version": "1.0",
  "occurred_at": "2026-09-28T10:15:00.000000Z",
  "producer": "healthsetu-backend",
  "correlation_id": "req-98234-a1",
  "resource_type": "document",
  "resource_id": "doc-00129",
  "patient_id": "pat-55102",
  "payload": {
    "document_id": "doc-00129",
    "confidence": 0.96
  }
}
```

## 2. Supported Domain Events

1. `PATIENT_DOCUMENT_UPLOADED`: Document stream successfully stored in encrypted object store.
2. `DOCUMENT_PROCESSING_COMPLETED`: OCR extraction and structured entity resolution finished.
3. `DOCUMENT_PROCESSING_FAILED`: OCR or parsing failed; document flagged for manual review.
4. `PRESCRIPTION_CREATED`: Prescription authored or extracted into draft status.
5. `MEDICATION_NORMALIZED`: Clinical terminology matched to RxNorm code.
6. `MEDICATION_SAFETY_EVALUATION_COMPLETED`: Drug interaction check completed (`CLEAR` or `ALERT`).
7. `DISCHARGE_EXTRACTION_COMPLETED`: Structured discharge instructions extracted.
8. `CARE_PLAN_CREATED`: Personalized post-discharge plan created.
9. `INTEROPERABILITY_IMPORT_COMPLETED`: Inbound FHIR bundle ingested and reconciled.
10. `INTEROPERABILITY_EXPORT_COMPLETED`: Outbound clinical summary transmitted.

## 3. Consumer Deduplication & Idempotency

- Every consumer maintains an event audit tracker `(event_id, consumer_name)`.
- If an event is re-delivered (at-least-once transport), the consumer safely acknowledges and ignores the duplicate without repeating downstream side effects.

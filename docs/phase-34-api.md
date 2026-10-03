# HealthSetu — Phase 34: Diagnostic REST API Reference

## 1. Diagnostic Catalog APIs
- `GET /api/v1/diagnostics/catalog`: Search catalog tests by query, category, specimen type, or system.
- `GET /api/v1/diagnostics/catalog/{test_id}`: Retrieve full catalog test specification.
- `POST /api/v1/diagnostics/catalog/normalize`: Map raw test name to standardized concept. Returns `is_ambiguous=True` if multiple concepts match.

## 2. Diagnostic Order APIs
- `POST /api/v1/clinicians/me/patients/{patient_id}/diagnostic-orders`: Place diagnostic order for patient under clinician context.
- `POST /api/v1/diagnostic-orders`: Generic order creation endpoint.
- `GET /api/v1/patients/{patient_id}/diagnostic-orders`: List orders for patient (patient BOLA enforced).
- `GET /api/v1/patients/{patient_id}/diagnostic-orders/{order_id}`: Get single patient order.
- `GET /api/v1/clinicians/me/diagnostic-orders`: List orders placed by authenticated clinician.
- `GET /api/v1/clinicians/me/diagnostic-orders/{order_id}`: Get clinician order details.
- `GET /api/v1/diagnostic-orders/{order_id}`: Retrieve diagnostic order by ID.
- `POST /api/v1/diagnostic-orders/{order_id}/cancel`: Request order cancellation with documented reason.
- `POST /api/v1/diagnostic-orders/{order_id}/status`: Transition order status.
- `POST /api/v1/diagnostic-orders/{order_id}/specimens/{specimen_id}/collect`: Record specimen collection event.

## 3. Diagnostic Result APIs
- `POST /api/v1/diagnostic-results/ingest`: Ingest laboratory result with analyte measurements, units, ranges, and flags.
- `GET /api/v1/patients/{patient_id}/diagnostic-results`: Retrieve factual diagnostic results for patient.
- `GET /api/v1/patients/{patient_id}/diagnostic-results/{result_id}`: Retrieve single result for patient.
- `GET /api/v1/clinicians/me/diagnostic-results/{result_id}`: Clinician review of result with provenance and flags.
- `GET /api/v1/diagnostic-results/{result_id}`: General result retrieval.
- `GET /api/v1/diagnostic-results/{result_id}/history`: Retrieve full immutable version chain for amended results.
- `POST /api/v1/clinicians/me/diagnostic-results/{result_id}/verify`: Formally verify or reject result (Phase 10 integration).

## 4. Diagnostic Report APIs
- `POST /api/v1/diagnostic-reports`: Create and register diagnostic report (narrative impression is NOT a diagnosis).
- `GET /api/v1/patients/{patient_id}/diagnostic-reports`: List patient reports.
- `GET /api/v1/patients/{patient_id}/diagnostic-reports/{report_id}`: Get patient report.
- `GET /api/v1/diagnostic-reports/{report_id}`: General report retrieval.

## 5. External Webhook APIs
- `POST /api/v1/webhooks/diagnostics/{provider}`: Ingest laboratory status/result webhooks with cryptographic HMAC signature verification and replay prevention.

## 6. Administrative Governance APIs
- `GET /api/v1/admin/diagnostics/status`: Subsystem operational state and latency.
- `GET /api/v1/admin/diagnostics/providers`: Configured laboratory adapters.
- `GET /api/v1/admin/diagnostics/provider-status`: Real-time probe of lab gateway connectivity.
- `GET /api/v1/admin/diagnostics/failures`: List failed diagnostic orders.
- `GET /api/v1/admin/diagnostics/reconciliation`: List reconciliation summaries.
- `POST /api/v1/admin/diagnostics/providers/{provider}/test`: Execute connectivity ping test.
- `POST /api/v1/admin/diagnostic-results/{result_id}/reconcile`: Trigger order-result integrity audit.

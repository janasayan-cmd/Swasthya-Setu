# HealthSetu — Phase 34: Diagnostic Provider Integration & Adapters

## 1. Provider Abstraction Architecture
HealthSetu decouples domain logic from external laboratory interfaces via the `DiagnosticProvider` abstract base class located at `app/integrations/diagnostics/base.py`.

### Required Provider Operations
- `search_tests(query, category, limit)`: Catalog test lookup.
- `get_test(provider_test_id)`: Test specification details.
- `place_order(order)`: Electronic test order transmission.
- `get_order(provider_order_id)`: Order status query.
- `cancel_order(provider_order_id, reason)`: Electronic cancellation request.
- `get_order_status(provider_order_id)`: Synchronization of processing progress.
- `get_results(provider_order_id)`: Fetch analyte result sets.
- `get_report(provider_report_id)`: Fetch narrative diagnostic reports.
- `health_check()`: Connection latency and gateway operational state.
- `verify_webhook_signature(payload_bytes, signature_header)`: HMAC-SHA256 signature verification.

## 2. Mock Diagnostic Provider
Located at `app/integrations/diagnostics/providers/mock.py`, the `MockDiagnosticProvider` enables comprehensive testing without external network dependencies.
- Simulates realistic analyte outputs for standard panels (CBC, Lipid Profile, HbA1c, Serum Creatinine, SARS-CoV-2 RT-PCR, Chest X-Ray).
- Controllable failure modes:
  - `simulate_failure`: Simulates lab validation error.
  - `simulate_timeout`: Simulates network gateway timeout (returns `UNKNOWN`).
  - `simulate_unavailable`: Simulates service offline.
  - `simulate_critical`: Generates critical panic value (Hemoglobin 5.2 g/dL).
  - `simulate_abnormal`: Generates elevated analyte (Serum Creatinine 1.9 mg/dL).
  - `simulate_qualitative`: Generates qualitative result (SARS-CoV-2 RNA DETECTED).
  - `simulate_corrected`: Generates amended result version.

## 3. Failure Behavior Guidelines
- **Provider Timeout**: Order status transitions to `UNKNOWN` / `PENDING`, never `COMPLETED`.
- **Provider Unavailable**: Returns HTTP 503 / `ProviderState.UNAVAILABLE`.
- **Malformed Response**: Triggers `VALIDATION_FAILED`, never silently ingested.
- **Provider Authentication Failure**: Surfaces `DIAGNOSTIC_PROVIDER_AUTHENTICATION_FAILED`.
- **Safe Defaults**: Provider downtime never results in assumed normality or autonomous diagnosis.

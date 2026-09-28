# HealthSetu — Phase 25: Provider Configuration & Switching

## 1. Provider Selection Principles

HealthSetu integrates external specialized providers for medication safety, document OCR, generative AI, and healthcare interoperability. Provider selection is strictly configuration-driven:

```
Domain Request
      ↓
Check Provider Configuration
      ↓
Check Provider Kill Switch
      ↓
Validate Required Credentials (API Key, Base URL)
      ↓
Invoke Authoritative Provider
      ↓
Attach Provider & Version Metadata to Result (Provenance)
```

---

## 2. Supported Domain Providers & Requirements

| Domain | Setting | Supported Values | Required Credentials / Config |
|---|---|---|---|
| **Medication Safety** | `MEDICATION_SAFETY_PROVIDER` | `mock`, `licensed_provider` | `MEDICATION_SAFETY_API_KEY` (when non-mock) |
| **Artificial Intelligence** | `AI_PROVIDER` | `mock`, `openai`, `gemini` | `AI_API_KEY`, `AI_BASE_URL` (when non-mock) |
| **Document OCR** | `OCR_PROVIDER` | `mock`, `tesseract`, `google_vision` | Storage access & provider API keys |
| **Interoperability** | `INTEROPERABILITY_PROVIDER` | `internal`, `fhir_gateway` | `FHIR_VERSION` (default `R4`), `HL7_VERSION` |

---

## 3. Strict Fallback Boundaries (TRD Sec 12)

1. **No Silent Fallback to Mocks in Production**: If a licensed clinical safety provider experiences downtime or timeouts, the system must **NOT** silently fall back to an unverified mock provider and declare a prescription `CLEAR`.
2. **Explicit Error States**: Failures or unconfigured providers yield explicit operational error codes (`EXTERNAL_PROVIDER_UNAVAILABLE`, `AI_PROVIDER_NOT_CONFIGURED`) rather than converting uncertainty into false clinical safety.
3. **Historical Result Immutability (TRD Sec 48)**: Switching providers (e.g. from `mock` to `licensed_provider` or upgrading ruleset versions) **never** re-evaluates historical records. Every historical prescription or clinical assessment retains its immutable evaluation timestamp, engine name, and version.

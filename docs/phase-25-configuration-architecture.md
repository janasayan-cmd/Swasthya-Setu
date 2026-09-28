# HealthSetu — Phase 25: Configuration Governance Architecture

## 1. Overview & Objective

Phase 25 establishes a centralized, typed, layered, and auditable configuration governance and feature flag engine for HealthSetu. It enables safe, controlled feature activation, gradual rollout, and emergency shutdown without requiring redeployments or ad-hoc code alterations.

### Fundamental Architectural Invariants
1. **Configuration ≠ Authorization**: A feature being enabled never bypasses RBAC, ABAC, or ownership checks.
2. **Feature Flag ≠ Clinical Authority**: Disabling a feature produces an explicit `FEATURE_DISABLED` or unavailable response; it never fabricates clinical clearance, normal triage status, or synthetic confirmation.
3. **Provider Failure ≠ Success**: When external providers (e.g. licensed medication safety, OCR, AI) are unavailable or disabled, the system halts or degrades explicitly rather than converting failure to clearance.
4. **Configuration Change ≠ Historical Data Rewrite**: Altering provider selection or feature states never alters historical clinical assessments, prescriptions, or audit logs.

---

## 2. Configuration Precedence & Flow

```
Environment Variables / Deployment Secrets (.env / Railway / Cloud Vault)
                         ↓
            app/core/config.py (Typed Settings via Pydantic)
                         ↓
      Configuration Validation & Conditional Dependencies
                         ↓
      Feature Flag Service (Context, Dependencies & Kill Switches)
                         ↓
      Domain Services (Medication, Triage, Care Plans, Interop, AI)
                         ↓
             Audit & PHI-Safe Observability
```

Precedence hierarchy:
1. **Secure Runtime & Environment Configuration**: Active process environment variables take precedence.
2. **Dynamic In-Memory Overrides**: Administratively updated rollout rules and kill switches.
3. **Application Baseline Defaults**: Safe, immutable programmatic fallbacks (`DEFAULT_FEATURE_FLAGS`, `DEFAULT_KILL_SWITCHES`).

---

## 3. Configuration Categories (TRD Sec 7)

Settings and flags are grouped into 22 distinct namespaces to prevent configuration sprawl:
- `APPLICATION`: App metadata, environment, debug switches, and port bindings.
- `SECURITY`: Cryptographic keys, token lifetimes, TLS/CORS boundaries.
- `AUTHENTICATION`: Password policies, token issuers, MFA controls.
- `AUTHORIZATION`: Role-permission definitions, relationship requirements.
- `CONSENT`: Patient consent evaluation switches and purpose bindings.
- `DATABASE`: Connection pools, overflow limits, timeouts, and ping policies.
- `DOCUMENT_PROCESSING`: OCR engines, file size caps, and mime-type validators.
- `MEDICATION`: Normalization engines, RxNorm dictionaries.
- `MEDICATION_SAFETY`: Drug-drug, drug-allergy interaction engines and rules.
- `TRIAGE`: Acuity ruleset versions, timeout thresholds, and modes.
- `CARE_PLAN`: Discharge plan extraction, goal generators.
- `CLINICAL_WORKFLOW`: Note signing, assessments, and clinical workspace.
- `FACILITY_DISCOVERY`: Geo-spatial indexing, service discovery ranges.
- `TRANSFER`: Inter-facility handoff workflows, SLA timeouts.
- `INTEROPERABILITY`: FHIR R4 and HL7 v2.x gateway switches.
- `AI`: Model identifiers, temperature, token limits, grounding checks.
- `ASYNC_PROCESSING`: Worker concurrency, retry ceilings, dead-letter queues.
- `PRIVACY`: Data minimization, retention orchestration, de-identification.
- `OBSERVABILITY`: Metrics collection, log levels, health check routes.
- `RATE_LIMITING`: IP and user request rate boundaries.
- `STORAGE`: Object storage adapters, lifecycle tags, bucket names.
- `EXTERNAL_PROVIDERS`: API endpoints and credential bindings for third-party tools.

---

## 4. Operational Boundaries

- **Zero Secret Exposure**: Secret values (e.g. `SECRET_KEY`, `AI_API_KEY`, `MEDICATION_SAFETY_API_KEY`) are never stored in feature flag metadata, returned via capabilities endpoints, or printed in logs/audits.
- **Fail-Closed Policy**: If configuration dependencies are missing or unresolved in production, the system fails closed.

# HealthSetu — Business Continuity & Graceful Degradation Framework (Phase 19)

================================================================================
1. BUSINESS CONTINUITY OBJECTIVE & PRINCIPLES
================================================================================

HealthSetu's Business Continuity (BC) plan guarantees that the clinical platform
remains maximally resilient, safe, and transparent during external dependency outages,
partial infrastructure failures, and emergency operations.

CRITICAL CLINICAL SAFETY RULE:
    NEVER SILENTLY RETURN INCOMPLETE CLINICAL INFORMATION AS IF IT WERE COMPLETE.

When a subsystem, database, or external healthcare service fails, the platform
must enter an **EXPLICIT DEGRADED MODE**. Incomplete data must be clearly labeled,
and safety evaluation engines must fail closed according to established clinical
governance rules.

================================================================================
2. COMPONENT DEGRADED MODES & SAFE FALLBACK MATRIX
================================================================================

| Subsystem / Dependency | Failure State | Degraded Mode Behavior | Safe Fallback Action | Clinical Risk Mitigation |
|------------------------|---------------|------------------------|----------------------|--------------------------|
| **Supabase PostgreSQL**| Connection timeout / unreachable | Platform returns `503 Service Unavailable` on read/write endpoints; `/api/v1/ready` reports `not_ready`. | Backend refuses traffic; cached health probe alerts orchestrator; no uncommitted writes permitted. | Prevents silent data corruption, orphaned records, or stale clinical decisions. |
| **Medication Safety Engine** (Drug-Drug / Drug-Allergy) | Provider API down / unreachable | Safety check endpoint returns status `UNKNOWN` or `ERROR` with high-priority alert. | **Phase 7 Invariant**: System NEVER reports `CLEAR` or `SAFE`. UI displays banner: *"Automated safety check offline — clinician must manually verify interactions."* | Prevents fatal adverse drug interactions caused by false-negative "clear" evaluations. |
| **OCR Document Extraction Engine** | OCR cloud service unavailable | Uploaded medical documents are safely stored in object storage; processing state set to `PENDING` or `EXTRACTION_FAILED`. | Original scan remains viewable by clinicians; automated extraction delayed until worker retries. | Prevents fabricated or partial extractions from entering verified EHR tables. |
| **AI Assistive Extraction Engine** | Gemini / OpenAI API failure / timeout | AI endpoints return structured `503` or fall back to deterministic clinical parsers. | System provides raw document text without automated AI summarization. AI is strictly assistive. | Prevents hallucinations, invented diagnoses, or unverified clinical conclusions. |
| **External Interoperability** (FHIR / HL7 / ABDM) | Partner hospital / ABDM gateway down | Outbound transfers and synchronization queued in persistent retry buffer with exponential backoff. | System preserves local transaction; flags transfer as `PENDING_RETRY`; incoming imports paused. | Prevents record duplication, corrupted cross-facility synchronizations, or dropped referrals. |
| **Object Storage (S3)**| Storage bucket down / network partition | Document upload/download endpoints return `503 Document Service Unavailable`. | Clinical metadata, encounter notes, and vitals continue to operate normally via PostgreSQL. | Clinicians can view structured history even if historical attachment images are temporarily offline. |
| **Medication Terminology** (RxNorm / SNOMED) | Terminology server unreachable | Search falls back to internal cached terminology database. | Query results annotated with `cached_offline: true`; unknown drugs marked for verification. | Avoids unmapped drug strings while maintaining prescribing workflows. |
| **Facility Directory & Geolocation** | OSRM / Geocoding provider down | Distance calculation defaults to direct Euclidean/coordinate estimation. | Facility listings sorted with notice: *"Estimated straight-line distances only — routing engine offline."* | Ensures critical emergency referral lists remain accessible during transport crises. |

================================================================================
3. MEDICATION SAFETY RECOVERY & PHASE 7 GOVERNANCE
================================================================================

During a prospective medication safety check, clinicians evaluate new prescriptions
against existing active medications and documented patient allergies.

```
       [ Clinician Submits Prescription Check ]
                          │
                          ▼
            [ Is Provider Reachable? ]
              ├── YES ──> Evaluate Interactions -> Return ALERTS / CLEAR
              │
              └── NO (Outage / Timeout / HTTP 5xx)
                          │
                          ▼
             [ DEGRADED FAIL-CLOSED MODE ]
             status: "DEGRADED"
             interaction_check: "UNKNOWN"
             allergy_check: "UNKNOWN"
             clinical_warning: "AUTOMATED SAFETY CHECK UNAVAILABLE"
             DO NOT RETURN: "CLEAR" OR "SAFE"
```

Once the external provider recovers:
1. Automated synthetic health probe validates provider API handshake.
2. Probe submits a known interaction pair (e.g. Aspirin + Warfarin) to verify non-zero alerts.
3. Telemetry records `provider_recovery_total{provider="medication_safety"}`.
4. Normal automated evaluations resume.

================================================================================
4. BACKGROUND JOB RECOVERY & DUPLICATE-PROCESSING PROTECTION
================================================================================

When the backend container restarts or recovers from an infrastructure outage,
background job workers must safely resume processing without corrupting state.

### Idempotency Enforcement:
1. **Unique Idempotency Keys**:
   - Every background job (e.g. OCR scan extraction, document indexing, export generation) is assigned a deterministic `idempotency_key` based on `job_type:resource_id:version`.
2. **State Machine Transitions**:
   - Valid transitions: `QUEUED` -> `PROCESSING` -> `COMPLETED` | `FAILED` | `RETRYING`.
   - A job in `COMPLETED` state is NEVER re-executed.
3. **Stale Lock Recovery (Zombies)**:
   - If a worker crashes mid-task, the job remains in `PROCESSING` state.
   - On startup, the job manager identifies jobs whose heartbeat is older than 5 minutes.
   - Stale jobs are safely transitioned to `RETRYING` (if retry count < max_retries) or `FAILED`.
4. **Dead-Letter Queue (DLQ)**:
   - Jobs that exceed maximum retries (3 attempts) are moved to the Dead-Letter Queue.
   - DLQ alerts engineering without blocking the execution of healthy queued jobs.

================================================================================
5. AUTHENTICATION & SESSION CONTINUITY
================================================================================

1. **Deny-by-Default Security Invariant**:
   - If authentication stores, cryptography modules, or token verifiers encounter errors, all requests MUST fail closed with HTTP 401 Unauthorized or 403 Forbidden.
   - Authentication must NEVER be bypassed to "enable clinical continuity".
2. **Offline Local Token Verification**:
   - JWT tokens are signed using HMAC-SHA256 (`JWT_SECRET_KEY`).
   - Active tokens with valid signatures and unexpired timestamps (`exp`) can be verified by the backend container without synchronous calls to external authentication providers.
3. **Emergency Credential Invalidation**:
   - If a security incident requires invalidating all sessions, rotating `JWT_SECRET_KEY` immediately terminates all active sessions across all devices.

================================================================================
6. OPERATIONAL INCIDENT COMMUNICATION
================================================================================

During an operational outage or degraded mode event, communication must adhere
to strict healthcare compliance:

1. **Internal Status Page**: Updated within 5 minutes of incident declaration.
2. **Customer / Hospital Communications**:
   - Identify affected subsystem (e.g., "Prescription Document OCR Processing").
   - Explicitly describe clinical workaround (e.g., "Clinicians should review original PDF scans directly in the clinical workspace").
   - State estimated recovery time.
3. **STRICT PRIVACY RULE**:
   - Under NO circumstances shall operational incident notifications, public status updates, or slack alerts contain Protected Health Information (PHI), patient names, or patient identifiers.

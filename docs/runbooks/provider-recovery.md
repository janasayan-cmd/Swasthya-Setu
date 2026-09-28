# HealthSetu Runbook — External Healthcare Provider Recovery & Clinical Safety

================================================================================
OVERVIEW & CLINICAL GOVERNANCE
================================================================================
HealthSetu integrates with multiple external specialized healthcare providers:
- **Medication Safety Engine** (Drug-Drug & Drug-Allergy Interaction Detection)
- **Document OCR Extraction Provider** (Prescription & Lab PDF Parsing)
- **AI Assistive Clinical Engine** (Summarization & Extraction)
- **Healthcare Interoperability Partner** (FHIR / HL7 / ABDM Gateway)
- **Terminology Service** (RxNorm / SNOMED-CT / ICD-10)

External providers are treated as independent, untrusted external dependencies.
An outage of an external provider MUST NEVER compromise internal patient data integrity,
and MUST NEVER cause the backend to report false-negative clinical safety states.

================================================================================
1. MEDICATION SAFETY PROVIDER RECOVERY (PHASE 7 RULES)
================================================================================

### Critical Safety Invariant:
```
       Provider Unavailable / Timeout / HTTP 5xx
                        ≠
                      CLEAR
                        ≠
                       SAFE
```
When the safety engine is offline, the system MUST return evaluation status `UNKNOWN`
or `ERROR` with an explicit clinical warning banner.

### Recovery Procedure:
1. **Detect Provider Availability**:
   - Check provider health status page and verify network reachability.
2. **Execute Controlled Handshake Validation**:
   - Send an authenticated health probe to the provider's test endpoint:
     ```bash
     curl -f -H "Authorization: Bearer $MEDICATION_SAFETY_API_KEY" \
       https://api.rxnorm-engine.internal/health
     ```
3. **Execute Controlled Verification Request (Positive Alert Test)**:
   - Submit a test medication pair with a KNOWN major interaction (e.g. `Warfarin` + `Aspirin`):
     ```bash
     python -c '
     from app.services.medication_safety import MedicationSafetyService
     service = MedicationSafetyService()
     alerts = service.check_interactions(["Warfarin", "Aspirin"])
     assert len(alerts) > 0, "Safety test failed: Expected major interaction alert!"
     print("[OK] Medication safety engine correctly identified major interaction.")
     '
     ```
4. **Assert Expected Alert Generation**:
   - Confirm that the provider returns interaction alerts with severity `HIGH` or `CRITICAL`.
   - Confirm that the provider version string matches supported specifications.
5. **Resume Automated Routing & Record Telemetry**:
   ```python
   metrics.record_provider_recovery("medication_safety")
   ```
6. Clinicians are notified that automated drug interaction checks are back online.

================================================================================
2. OCR PROVIDER RECOVERY & WORKER RE-PROCESSING
================================================================================

If the OCR document parsing service experiences an outage:
1. **Preserve Raw Artifacts**:
   - All uploaded scans and PDF documents remain safely persisted in Object Storage.
   - Processing status in database remains `PENDING` or `EXTRACTION_FAILED`.
   - NEVER fabricate or guess extracted medications, dosages, or lab numbers.
2. **Resume Background Extraction Worker**:
   - When OCR service connectivity is restored, query for unprocessed documents:
     ```sql
     SELECT id, storage_key 
     FROM documents 
     WHERE processing_status IN ('PENDING', 'EXTRACTION_FAILED')
     ORDER BY created_at ASC;
     ```
3. **Idempotent Sequential Reprocessing**:
   - Background worker processes documents one-by-one.
   - Once successfully extracted, record metadata is updated to `EXTRACTED_UNVERIFIED`.
   - Extracted data remains marked as unverified until explicitly reviewed and confirmed by a licensed clinician.
4. **Record Telemetry**:
   ```python
   metrics.record_provider_recovery("ocr")
   ```

================================================================================
3. AI CLINICAL ASSISTIVE ENGINE RECOVERY
================================================================================

AI models (Gemini / Anthropic / OpenAI) serve purely as assistive tools.
During an AI provider outage:
- Deterministic fallback rules handle essential categorization.
- AI outage NEVER results in:
  - Invented clinical information or hallucinated diagnoses
  - Automated prescriptions or dosage changes
  - Unsafe triage decisions or modified acuity levels
- When AI provider recovers:
  1. Validate model endpoint latency and token quotas.
  2. Send a standard synthetic clinical test prompt.
  3. Verify output schema adheres strictly to Pydantic validation boundaries.
  4. Resume assistive suggestions in Doctor Clinical Workspace.
  5. `metrics.record_provider_recovery("ai")`.

================================================================================
4. INTEROPERABILITY RECOVERY (FHIR / HL7 / ABDM)
================================================================================

If an external hospital partner or ABDM gateway fails:
1. **Outgoing Transfers**:
   - Outbound FHIR bundles and referral messages are held in a persistent retry buffer.
   - Requests retry using exponential backoff with jitter (5s, 30s, 2m, 10m, 1h).
2. **Inbound Resources**:
   - Provenance headers (`source_system`, `external_id`, `received_at`) are preserved.
   - External records are NEVER permitted to overwrite internally verified clinical entries automatically.
3. **Recovery Verification**:
   - Send FHIR capability statement probe: `GET [partner_base_url]/metadata`.
   - Flush retry queue and verify successful delivery acknowledgments (`HTTP 200 OK` / `HTTP 201 Created`).
   - `metrics.record_provider_recovery("interoperability")`.

# HealthSetu — Known System Limitations & Capability Boundary

## 1. No False Capability Claims (Section 36)

HealthSetu maintains strict fidelity between documented features and verified production capabilities. The backend service explicitly **DOES NOT CLAIM**:

1. **NO "Autonomous Clinical Diagnosis"**: The backend does NOT diagnose diseases, interpret radiology scans as authoritative truth, or replace certified clinical judgment. Triage outputs are operational prioritization categories only.
2. **NO "Autonomous Prescribing or Medication Changes"**: The system does NOT independently prescribe medications, alter dosages, or halt active regimens without human clinician authorization.
3. **NO "Complete Universal Drug-Drug Interaction Checking"**: The system does NOT claim exhaustive, authoritative pharmacopoeia coverage unless backed by an enterprise licensed clinical safety engine. Unchecked combinations fail to `UNKNOWN`.
4. **NO "Real-Time Telemetric Hospital Bed Availability"**: Facility bed capacities reflect periodically synced departmental estimates, NOT live sensor-driven telemetry, unless an authoritative hospital IoT integration is explicitly online.
5. **NO "Automatic Transfer Execution"**: Transfer requests are referral inquiries that require two-sided clinician and administrative review; they never automatically dispatch ambulances or admit patients.

---

## 2. Documented System Limitations (Section 35)

### 2.1 Medication Safety & Terminology
- **Licensed Service Dependency**: The production backend integrates with RxNorm terminology for standard medication normalization. Authoritative clinical decision support for complex polypharmacy, pediatric weight-based adjustments, and rare contraindications requires an active commercial safety database subscription (e.g. FDB / First Databank).
- **Safe-Failure Behavior**: If the medication safety provider fails or an unknown drug formulation is submitted, the evaluation returns `UNKNOWN` with an explicit advisory. It is NEVER falsely marked `CLEAR`.

### 2.2 Medical Document Processing & OCR
- **Handwritten Clinical Notes**: Local OCR engines (Tesseract) achieve high precision (>95%) on typed, structured PDF prescriptions and printed discharge summaries. Unstructured, cursive handwritten clinical notes may produce lower extraction confidence and MUST undergo mandatory human review (`is_verified=False`).
- **File Format Constraints**: Document upload is restricted to PDF, PNG, and JPEG formats under 10MB. Complex DICOM imaging and proprietary scanner TIFF formats are currently unsupported.

### 2.3 AI Intelligence Layer
- **Non-Authoritative Advisory**: Generative AI models (Gemini / Claude / GPT) are utilized strictly for language translation, patient-friendly explanations, clinical documentation drafting, and SBAR structuring.
- **Factual Grounding**: All AI responses must cite source EHR data (`AIGroundingStatus.GROUNDED`). If hallucination or ungrounded claims are detected, the output enters `REVIEW_REQUIRED`.

### 2.4 Interoperability & FHIR Coverage
- **Supported Resources**: HealthSetu supports FHIR R4 Patient, Encounter, Condition, AllergyIntolerance, MedicationRequest, Observation, and DocumentReference.
- **Unsupported Resources**: Specialized oncology staging protocols, genomic sequencing bundles, and advanced dental charts are outside the current FHIR profile scope.
- **ABDM Integration**: Requires certified sandbox/production gateway credentials from the National Health Authority (NHA).

### 2.5 Geographic Discovery
- **Straight-Line Distance**: Facility discovery utilizes the Haversine spherical trigonometric formula for geographic distance. Actual ambulance travel times depend on local road conditions, traffic density, and terrain, which are not currently modeled via real-time GPS telemetry.
- **Radius Bounds**: Maximum discovery radius is capped at 100 kilometers.

### 2.6 Unsupported Clinical Scenarios
- Neonatal intensive care unit (NICU) dynamic incubator titrations.
- Intraoperative real-time surgical monitoring.
- Closed-loop automated insulin infusion pumps.

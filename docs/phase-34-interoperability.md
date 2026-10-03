# HealthSetu — Phase 34: Diagnostic Interoperability & FHIR Mapping

## 1. Overview
Diagnostic data in HealthSetu adheres to national and international healthcare data exchange standards, integrating with Phase 13 interoperability adapters.

## 2. Conceptual FHIR Resource Mappings

| HealthSetu Concept | FHIR R4 Resource | Key Fields Mapped |
|---|---|---|
| Diagnostic Order | `ServiceRequest` | `id`, `status`, `intent`, `code` (LOINC), `subject` (Patient), `requester` (Practitioner) |
| Diagnostic Result | `Observation` | `id`, `status`, `code`, `valueQuantity`, `valueString`, `interpretation`, `referenceRange` |
| Diagnostic Report | `DiagnosticReport` | `id`, `status`, `code`, `subject`, `result` (Observation refs), `conclusion` |
| Specimen Record | `Specimen` | `id`, `type`, `status`, `collection.collectedDateTime`, `collection.bodySite` |

## 3. Interoperability Boundaries
- **Supported Subsets Only**: Only validated subsets of FHIR R4 structures are exposed or mapped. The backend does not claim blanket FHIR compliance.
- **External Data Verification**: Inbound FHIR `Observation` or `DiagnosticReport` bundles are categorized as `IMPORTED` and require review by a clinician before being projected as verified facts in the clinical record.
- **LOINC Terminology Preservation**: Standard LOINC codes and display names are preserved without lossy local translation.

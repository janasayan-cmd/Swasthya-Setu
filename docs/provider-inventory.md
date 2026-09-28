# HealthSetu — External Provider Inventory & Lifecycle Registry

## 1. Provider Lifecycle Overview (Section 31)

HealthSetu integrates external services to support terminology normalization, optical character recognition, safety checks, interoperability, and cloud storage. Every external provider is cataloged with strict operational parameters, timeouts, retry boundaries, and safe-failure behaviors.

---

## 2. External Provider Registry

| Provider Name | Purpose | Technical Owner | Version | Timeout | Retry Policy | Failure Behavior | Replacement Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RxNorm (NIH / NLM)** | Medication Terminology Normalization | Clinical Team | API v1 | 5.0s | Max 2 retries (exponential backoff) | Fallback to local cached terminology dictionary | SNOMED-CT Clinical Terminology API |
| **Enterprise Clinical Safety Provider** (FDB / Medispan) | Authoritative Drug-Drug, Drug-Allergy Safety Evidence | Clinical Safety Officer | v2.4 | 4.0s | Max 1 retry | **Fail-Closed**: Status marked `UNKNOWN` / `ERROR`. Never marked `CLEAR`. | Alternative licensed clinical pharmacology vendor |
| **Tesseract / AWS Textract** | Optical Character Recognition (OCR) | Backend Team | v5.3 / 2024 | 15.0s | Max 2 retries | Document marked `FAILED` with review required | Google Cloud Document AI |
| **Google Gemini / OpenAI** | Non-Authoritative Clinical Summarization & SBAR Structuring | AI Engineering Team | 1.5-Pro / 4o | 8.0s | Max 1 retry | Returns `503 Unavailable` or fallback to rule templates; no fake output | Anthropic Claude API / Self-hosted LLaMA |
| **ABDM Gateway (NHA)** | National Health Interoperability & FHIR Exchange | Interoperability Team | M1/M2/M3 | 10.0s | Max 3 retries | Queue outbound bundle for retry; inbound logs failure | Direct FHIR REST Server |
| **Supabase Storage / AWS S3** | Encrypted Medical Document Object Storage | Infrastructure Team | S3 API v4 | 10.0s | Max 3 retries | Returns `502 Bad Gateway` on upload; retry via client | Cloudflare R2 / Azure Blob Storage |
| **OpenStreetMap / Haversine Engine** | Facility Geocoding & Distance Calculation | Backend Team | v1 | 3.0s | Max 1 retry | Approximate via mathematical Haversine formula | Mapbox / Google Maps Distance Matrix API |

---

## 3. Provider License & Contract Tracking (Section 32)

| Provider Name | Licensed Product / API | Account Owner | Environment | Contract / License Status | Renewal Date | Usage Restrictions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RxNorm** | UMLS Metathesaurus / RxNorm API | Chief Technology Officer | Staging & Prod | Open Public Health License (NLM/NIH) | Annual UMLS agreement | Free non-commercial and commercial healthcare use under UMLS terms. |
| **Enterprise Clinical Safety Provider** | Clinical Pharmacology Core API | Clinical Safety Lead | Production (Target) | Commercial B2B Contract (In Procurement) | 2027-03-31 | Restriced to authorized clinical users; redistribution of raw drug monograph data prohibited. |
| **Google Cloud Vertex AI** | Gemini Enterprise API | Lead AI Architect | Production | Enterprise Cloud Agreement | Monthly Invoice | Zero Data Retention (ZDR) enabled; patient PHI excluded from model training. |
| **National Health Authority (NHA)** | ABDM Health Information Provider (HIP/HIU) | Compliance Officer | Staging / Prod | Government Integration Agreement | Annual Sandbox renewal | Must comply with DISHA and Indian Digital Personal Data Protection Act (DPDPA). |
| **Supabase Cloud** | Managed PostgreSQL & Storage | Head of Infrastructure | Production | Pro / Enterprise Tier | Monthly Active | Managed automated backups, daily WAL archives, SOC2 Type II certified. |

---

## 4. Medication Safety Provider Boundary (Section 33)

HealthSetu maintains an architectural distinction between three clinical domains:

```
[ Medication Terminology Normalization ]
             ≠
[ Medication Safety Evidence Checking ]
             ≠
[ Clinical Decision Support & Action ]
```

1. **Terminology Normalization (RxNorm / SNOMED)**: Translates messy colloquial drug names (`"amox 500"`) into structured concepts (`RxCUI 8640`). Normalization alone **DOES NOT** assess clinical safety, interactions, or patient contraindications.
2. **Authoritative Safety Evidence**: Requires a licensed, curated clinical safety provider. If this provider is unreachable or times out:
   $$\text{Status} \longrightarrow \mathbf{UNKNOWN} \quad (\mathbf{NOT} \text{ CLEAR})$$
3. **Clinical Decision Support (CDS)**: The human clinician remains solely responsible for the final medical determination to prescribe, adjust, or discontinue medication.

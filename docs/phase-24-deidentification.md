# HealthSetu — De-identification & Pseudonymization Framework (Phase 24)

## 1. Overview & Conceptual Distinctions

HealthSetu strictly distinguishes between:
1. **Pseudonymization**: Replacing identifiers with cryptographically salted tokens using HMAC-SHA256. Reversible by authorized custodians. The dataset **remains sensitive**.
2. **De-identification Transformations**: Applying direct identifier removal, date shifting, demographic generalization, and narrative text redaction for research, development, and testing.
3. **Legal Anonymization**: A formal legal standard that requires institutional compliance review and mathematical re-identification risk analysis.

> [!WARNING]
> **GOVERNANCE NOTICE (TRD Sec 23, 24, 54):**
> PSEUDONYMIZATION ≠ ANONYMIZATION.
> Applying de-identification utilities does not automatically certify data as legally non-PHI. All transformed outputs carry mandatory metadata disclaimers: `{"deidentified": true, "legal_certification": false}`.

---

## 2. Transformation Capabilities

| Transformation | Implementation | Purpose |
| :--- | :--- | :--- |
| **Direct Identifier Removal** | Replaces names, emails, phones, SSNs, national IDs, and street addresses with generic tags (`[REDACTED_NAME]`, etc.). | Eliminates overt direct patient identifiers. |
| **Date Shifting** | Shifts timestamps by a bounded offset (e.g. -7 days) preserving clinical chronologies and interval intervals. | Obfuscates real admission and encounter dates while preserving longitudinal analytical validity. |
| **Location Generalization** | Truncates ZIP/Postal codes to 3 digits (e.g., `90210` -> `902**`). | Reduces geographic re-identification granularity. |
| **Narrative Redaction** | Regex matching for phone, email, SSN, and explicit dates embedded in unstructured doctor notes. | Prevents accidental clinical notes identifier leakage. |
| **HMAC Pseudonymization** | Evaluates `HMAC-SHA256(PSEUDONYMIZATION_SALT, identifier)` producing `pseudo_{hash}` tokens. | Provides deterministic join keys for multi-table research analysis without exposing true patient IDs. |

---

## 3. Cryptographic Salt Security

- The salt (`PSEUDONYMIZATION_SALT`) is loaded strictly from environment configuration.
- The salt and unmasked mapping keys are **strictly forbidden from application logs and telemetry**.
- Reversible mapping registries are held in protected memory/vault structures accessible solely through explicit, audited administrative calls.

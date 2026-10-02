# HealthSetu Phase 29: Notification, Communication & Event Delivery System

## 1. Executive Summary & Purpose

The HealthSetu Notification & Communication Delivery System provides a centralized, secure, multi-channel event notification infrastructure. It delivers already-authorized information regarding clinical milestones, document processing, security events, and operational updates through configurable delivery channels (In-App Inbox, Email, SMS, and Push).

---

## 2. Core Architectural Principles & Clinical Safety Boundaries

> [!IMPORTANT]
> **NOTIFICATION != CLINICAL DECISION**
>
> Notifications and communications exist solely to deliver already-authorized information. The notification system is never an autonomous clinical reasoning engine.

| Concept | What It Is | What It Is NOT |
| :--- | :--- | :--- |
| **Notification** | Communication of an authorized system event | Clinical decision or medical advice |
| **Delivery Confirmation** | Proof provider accepted message | Proof user read or understood content |
| **Read Status** | Recipient opened notification in inbox | Clinical verification or clinical action |
| **Medication Reminder** | Delivery of verified schedule/timing | Prescription, dose adjustment, or medication change |
| **Care Plan Notification** | Notice that a plan was created/updated | New medical advice or treatment alteration |
| **Transfer Notification** | Notice of transfer request or status | Physical patient movement or bed occupancy |
| **Notification Failure** | Channel or provider delivery error | Clinical success or clinical failure |

---

## 3. Supported Channels & Characteristics

| Channel | Encryption / Transport | PHI Allowance | Primary Use Cases |
| :--- | :--- | :--- | :--- |
| **IN_APP** | HTTPS Authenticated Portal Session | Authorized Clinical Context & Links | Primary clinical workspace & patient portal inbox |
| **EMAIL** | TLS SMTP / HTTPS Provider Gateway | Minimal Non-Sensitive Summary + Secure Link | Account security, document status, transfer alerts |
| **SMS** | Telecommunication Cellular Protocol | **ZERO RAW PHI** (Strict Privacy Filter) | Urgent alerts, verification codes, generic notices |
| **PUSH** | APNS / FCM Gateway Protocol | **ZERO RAW PHI** (Token-based) | Device alerts, real-time inbox status pings |

---

## 4. Controlled Notification Taxonomy

Notifications are strictly constrained to pre-approved event types:

1. `DOCUMENT_PROCESSING_COMPLETED`: OCR & extraction finished.
2. `DOCUMENT_PROCESSING_FAILED`: Document could not be processed.
3. `PRESCRIPTION_PROCESSING_COMPLETED`: Prescription record available.
4. `MEDICATION_NORMALIZATION_REVIEW_REQUIRED`: Clinician review required for drug normalization.
5. `MEDICATION_SAFETY_REVIEW_REQUIRED`: Drug-drug interaction or allergy contraindication flag.
6. `TRIAGE_RESULT_AVAILABLE`: Deterministic rule-based triage assessment ready.
7. `SBAR_AVAILABLE`: Structured clinical handover summary ready.
8. `DISCHARGE_DOCUMENT_AVAILABLE`: Discharge instructions available.
9. `CARE_PLAN_AVAILABLE`: Approved care plan published.
10. `CARE_PLAN_UPDATED`: Care plan milestone updated.
11. `TRANSFER_REQUEST_CREATED`: Inter-facility transfer requested.
12. `TRANSFER_STATUS_UPDATED`: Transfer status transitioned.
13. `INTEROPERABILITY_IMPORT_COMPLETED`: ABDM / FHIR record imported.
14. `INTEROPERABILITY_IMPORT_FAILED`: FHIR import error requiring review.
15. `DATA_QUALITY_REVIEW_REQUIRED`: Inconsistency detected requiring clinical reconciliation.
16. `SECURITY_ALERT`: Suspicious login, password reset, or credential modification.
17. `ACCOUNT_SECURITY_NOTIFICATION`: Security configuration update.
18. `SYSTEM_NOTIFICATION`: Scheduled platform maintenance or operational alert.
19. `ADMINISTRATIVE_NOTIFICATION`: System administrator broadcast.

---

## 5. Security & Privacy Controls

- **IDOR / BOLA Prevention**: Users cannot read, dismiss, or query notifications belonging to other patients or clinicians.
- **Mandatory Security Bypass**: Security-critical alerts (MFA changes, password resets) bypass user channel opt-outs per organizational safety policy.
- **Header & Script Injection Guards**: Titles and subjects are sanitized against CRLF (`\r`, `\n`) and script injection.
- **Target Masking**: Emails, phone numbers, and push tokens are masked in telemetry and delivery logs.
- **Sliding-Window Rate Limiting**: Recipient throughput is capped per minute to prevent notification floods.

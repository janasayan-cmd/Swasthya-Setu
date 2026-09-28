# HealthSetu — Controlled Resource Deletion & Dependency Architecture (Phase 24)

## 1. Overview & Deletion Invariant

Destructive data deletion is a strictly governed, multi-stage workflow. Immediate synchronous purging of healthcare records from standard API handlers is prohibited.

> [!IMPORTANT]
> **THE UNCERTAINTY INVARIANT (TRD Sec 15, 37, 47):**
> If a retention policy is undefined, or hold status cannot be verified, or dependency integrity is uncertain:
> **THE SYSTEM MUST FAIL CLOSED AND REFUSE DELETION.**

---

## 2. 12-Step Deletion Flow

```mermaid
flowchart TD
    Start[1. Deletion Requested] --> Auth[2. Verify Admin Authorization]
    Auth --> Policy[3. Verify Retention Policy Exists]
    Policy -- No Policy --> FailClosed[ABORT: Fail-Closed Uncertainty]
    Policy -- Policy Found --> Hold[4. Check Active Legal / Admin Holds]
    Hold -- Active Hold --> Held[ABORT: LegalHoldActiveException]
    Hold -- No Holds --> Deps[5. Evaluate Downstream Dependencies]
    Deps -- Has Unresolved Children --> DepConflict[ABORT: DeletionDependencyConflictException]
    Deps -- Dependencies Cleared --> ObjStore[6. Identify Object Storage Blobs]
    ObjStore --> Op[7. Enqueue DELETE_RESOURCE Job]
    Op --> ExecDB[8. Execute Soft/Hard DB State Update]
    ExecDB --> ExecStore[9. Remove Object Storage Files]
    ExecStore --> Verify[10. Post-Deletion Verification]
    Verify --> Audit[11. Emit RESOURCE_DELETION_COMPLETED Audit]
    Audit --> End[12. Update Retention Status to DELETED]
```

---

## 3. Dependency Verification

Before a patient or parent entity can be deleted, the backend checks downstream domain records:
- Medical documents & uploaded binary blobs
- Prescriptions & medication entries
- Encounters & consultation notes
- Triage assessments & SBAR logs
- Care plans & active tasks
- Interoperability exchange records

If active dependent records exist and the deletion request does not specify explicit cascading authorization, the operation raises `DeletionDependencyConflictException` (HTTP 409).

---

## 4. Disaster Recovery & Backup Interaction (TRD Sec 38, 39)

> [!CAUTION]
> **DATA DELETION ≠ IMMEDIATE ERASURE FROM BACKUPS**
> Deletion at the application and database layer marks records as `DELETED` and purges live object storage files. However, pre-existing database snapshot backups and storage replication mirrors retain historical states until their separate infrastructure lifecycle expires (e.g. 30-day WAL retention).
> When restoring a database from backup, the restoration verification process cross-references the immutable audit trail and deletion markers to ensure deleted patient records are not accidentally resurrected into an active clinical state.

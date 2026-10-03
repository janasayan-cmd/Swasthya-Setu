# HealthSetu — Phase 34: Diagnostic Orders Workflow

## 1. Overview
The Diagnostic Order Service manages the clinical ordering lifecycle for laboratory tests, imaging procedures, and pathology evaluations. It guarantees idempotency, validates ordering clinician authority, tracks specimen collection, and interfaces with external diagnostic networks.

## 2. Order Lifecycle State Machine
Diagnostic orders advance through controlled lifecycle states:

```
[DRAFT] ──> [REQUESTED] ──> [PLACED] ──> [ACCEPTED] ──> [SPECIMEN_PENDING] ──> [IN_PROGRESS] ──> [COMPLETED]
   │             │             │            │                  │                     │
   └───> [CANCELLED] <─────────┴────────────┴──────────────────┴─────────────────────┘
                 ▲
                 ├── [REJECTED]
                 └── [FAILED] (Allows retry back to [REQUESTED])
```

- **DRAFT**: Incomplete order draft.
- **REQUESTED**: Clinician has placed the order; validated and saved in HealthSetu.
- **PLACED**: Order dispatched to external laboratory provider.
- **ACCEPTED**: Laboratory gateway has validated and acknowledged the order.
- **SCHEDULED**: Patient appointment or collection window confirmed.
- **SPECIMEN_PENDING**: Biological specimen collection awaited.
- **IN_PROGRESS**: Laboratory analysis or procedure actively executing.
- **COMPLETED**: Authoritative results delivered and ingested.
- **CANCELLED**: Order cancelled before completion (completed orders cannot be cancelled).
- **REJECTED**: Lab provider declined order due to specimen or scheduling constraints.
- **FAILED**: Network or gateway failure during submission; retry allowed.

## 3. Specimen Lifecycle
Biological specimens follow a dedicated state machine distinct from test status:
- `ORDERED` -> `COLLECTION_PENDING` -> `COLLECTED` -> `RECEIVED` -> `PROCESSING` -> `COMPLETED`.
- Rejection state: `REJECTED`. Specimen rejection (e.g. hemolyzed blood) remains distinguishable from test failure.
- Missing collection details default to `UNKNOWN` / `NOT_RECORDED`, never assumed.

## 4. Idempotency & Duplicate Protection
- Every order creation request accepts an optional `idempotency_key`.
- If an order with the same idempotency key already exists, the existing record is returned without re-executing placement.
- Prevents double-submission from network timeouts or UI retries.

## 5. Security & Authorization
- Ordering requires an authenticated user with `DOCTOR`, `CLINICIAN`, or `ADMIN` role.
- Clinicians can only place orders within their organizational or facility scope.
- IDOR protection prevents clinicians from impersonating other ordering physicians.
- Patients can only view orders linked directly to their `patient_id`.

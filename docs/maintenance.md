# HealthSetu — Continuous Maintenance & Operational Support Model

## 1. Production Support Model & Operational Ownership (Section 37)

To prevent single-person operational dependencies and guarantee rapid incident resolution, operational domains have assigned primary and secondary owners:

| Operational Domain | Primary Team Owner | Secondary Standby | Escalation Lead |
| :--- | :--- | :--- | :--- |
| **Backend Application & APIs** | Backend Engineering Team | SRE / DevOps Team | Lead Software Architect |
| **Database & Migrations** | Database Team (DBA) | Backend Team | Lead Data Architect |
| **Cloud Infrastructure (Railway)**| Infrastructure / SRE Team| Backend Team | Head of Infrastructure |
| **Application Security & PHI** | Information Security Team | Backend Team | Chief Information Security Officer |
| **External Providers & Terminology**| Integrations Team | Clinical Operations | Chief Technology Officer |
| **AI Layer & LLM Prompts** | AI Engineering Team | Backend Team | Lead AI Architect |
| **Medication Safety Evidence** | Clinical Safety Team | Clinical Pharmacist | Chief Medical Officer |
| **Object Storage & Backups** | SRE / Infrastructure | Database Team | Head of Infrastructure |
| **Domain, DNS & Ingress TLS** | DevOps Team | Railway Platform Ops | Lead Systems Engineer |

---

## 2. Maintenance Windows & Procedures (Section 38)

### Scheduled Maintenance Policy
- **Standard Maintenance Window**: Tuesdays and Thursdays between **02:00 AM – 04:00 AM IST** (low-utilization clinical window).
- **Notification**: Scheduled maintenance affecting external provider connectivity or database maintenance requires 48-hour prior notification to clinical administrators.
- **Zero-Downtime Objective**: All routine application releases and backward-compatible database schema expansions MUST execute with zero service downtime.

### Maintenance Change Checklist (Section 27)
Every production maintenance change must record:
1. **Change Description**: Technical summary of code or configuration changes.
2. **Business Reason**: Defect fix, security patch, or performance optimization.
3. **Affected Components**: Modules impacted (e.g. `/api/v1/auth`, `PrescriptionService`).
4. **Database Impact**: Schema changes, lock risks, or query plan shifts.
5. **External Provider Impact**: Updated endpoints, payload changes, or credentials.
6. **Security Impact**: Access control, authentication, or PHI boundary changes.
7. **Clinical Safety Impact**: Verification state transitions, interaction checks, triage rules.
8. **Rollback Plan**: Specific, tested procedure to revert the change within 5 minutes.
9. **Validation Plan**: Post-change smoke tests to confirm health and stability.

---

## 3. Incident $\longrightarrow$ Release Feedback Loop (Section 39)

Every production incident triggers a closed-loop remediation process:

```
[ Production Incident ]
          │
          ▼
[ Rapid Operational Mitigation ] ──> (Rollback / Failover / Safe Disablement)
          │
          ▼
[ Blameless Root Cause Analysis (RCA) ]
          │
          ▼
[ Corrective Action Items ]
          │
          ▼
[ Automated Regression Test Created ]
          │
          ▼
[ Code / Config Hardening Release ]
          │
          ▼
[ Verified Deployment & Metric Audit ]
```

---

## 4. Production Database Safety & Destruction Prohibition (Section 45)

The backend application is fundamentally restricted from executing uncontrolled destructive operations:

- **Prohibited SQL Commands**: The backend service account NEVER executes `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, or unconstrained `DELETE` statements.
- **Migration Safety**: Any migration that drops columns or alters foreign keys MUST be handled exclusively by the Database Team through a multi-step expand-contract schedule.
- **Audit Immutability**: The `audit_events` and clinical provenance tables are append-only. Updates and deletions are blocked by database trigger rules.

---

## 5. Feature Flags & Safe Disablement (Sections 46, 47)

High-impact external dependencies are controlled via environment feature flags:

| Feature Flag | Default | Safe Disablement Behavior |
| :--- | :--- | :--- |
| `AI_ENABLED` | `true` | Raises `AIDisabledException`; endpoints return `503 Unavailable` with clear explanation. Never returns fake output. |
| `MEDICATION_SAFETY_ENABLED` | `true` | Returns `SafetyEvaluationStatus.UNKNOWN` with advisory for human pharmacist review. Never returns `CLEAR`. |
| `DOCUMENT_PROCESSING_ENABLED`| `true` | Retains raw uploaded file in `PENDING_REVIEW` state without automated OCR extraction. |
| `INTEROPERABILITY_ENABLED` | `true` | FHIR/ABDM endpoints return `503 Service Disabled`; queues pending outbound bundles. |

> **SAFE DISABLEMENT INVARIANT:** When a feature is disabled, the system MUST return an explicit disabled state or failure. It MUST NEVER return a fake success response.

---

## 6. Continuous Improvement Framework (Section 53)

Post-go-live engineering focuses on continuous non-clinical operational hardening:
1. **Reliability**: Proactively eliminating latency outliers (P99 $< 1000\text{ms}$).
2. **Security**: Weekly automated dependency scanning and rapid patch application ($< 48\text{h}$ for Critical CVEs).
3. **Observability**: Enriching metric cardinality and refining alerting thresholds to eliminate alert fatigue.
4. **Test Coverage**: Expanding automated end-to-end edge-case testing with each sprint.
5. **No Scope Creep**: New clinical capabilities MUST go through formal architectural and clinical safety review phases, never ad-hoc production patching.

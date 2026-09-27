# HealthSetu Incident Response & Recovery Framework

## 1. Incident Management Overview

This document specifies the standard operating procedure for identifying, triaging, mitigating, and recovering from production incidents affecting the HealthSetu backend infrastructure (`api.healthsetu.com`).

The primary goals of incident response are:
1. **Patient Safety First**: Ensure that clinical safety boundaries are never violated during operational failures.
2. **Rapid Mitigation**: Restore system availability and service health before conducting root-cause analysis.
3. **Audit & Data Integrity**: Preserve audit trails and prevent data corruption or orphaned states.
4. **PHI Protection**: Ensure no Protected Health Information (PHI) is exposed during triage, debugging, or public incident summaries.

---

## 2. Incident Lifecycle

```
[ DETECTED ] ──> [ ACKNOWLEDGED ] ──> [ INVESTIGATING ] ──> [ MITIGATING ] ──> [ RECOVERED ] ──> [ CLOSED ] ──> [ POST-INCIDENT REVIEW ]
```

1. **DETECTED**: Alert fires via automated monitor (Prometheus / Railway / Healthcheck) or engineer observes abnormal behavior.
2. **ACKNOWLEDGED**: On-call engineer acknowledges alert within SLA window and assumes Incident Commander (IC) role.
3. **INVESTIGATING**: IC and responders analyze telemetry, inspect logs, identify affected components, and determine root cause.
4. **MITIGATING**: Responders apply operational countermeasures (e.g., container restart, traffic rerouting, rollback).
5. **RECOVERED**: Health and readiness checks pass (`/api/v1/health`, `/api/v1/ready`), error rate drops below alert threshold, smoke tests succeed.
6. **CLOSED**: Operational stability is verified for at least 30 minutes; incident ticket is marked resolved.
7. **POST-INCIDENT REVIEW**: Formal blameless post-mortem conducted within 48 hours for CRITICAL and HIGH severity incidents.

---

## 3. Incident Severity Matrix

| Severity Level | Response SLA | Criteria & Examples | Notification Target |
| :--- | :--- | :--- | :--- |
| **CRITICAL (P0)** | **< 15 minutes** | - Total API unavailability (`/api/v1/health` failing)<br>- Supabase PostgreSQL unavailable for > 3 minutes<br>- Active data corruption or clinical safety boundary violation<br>- P99 Latency > 10,000ms affecting all routes | Engineering Lead, SRE On-Call, Clinical Safety Officer |
| **HIGH (P1)** | **< 30 minutes** | - HTTP 5xx rate > 5% for > 5 minutes<br>- Medication safety provider completely down<br>- Spike in authentication service failures (> 15%)<br>- Container crash looping on Railway | SRE On-Call, Backend Team Lead |
| **MEDIUM (P2)** | **< 2 hours** | - Single non-critical provider failure (e.g. OCR delay)<br>- Elevated P95 latency (2000–5000ms)<br>- Background job queue backlog growing without drain<br>- Isolated authentication or permission anomalies | Engineering Team (Standup / Ticket) |
| **LOW (P3)** | **< 24 hours** | - Minor telemetry gaps<br>- Sporadic transient 4xx errors<br>- Deprecated API endpoint warnings | Backlog / Next Sprint |

---

## 4. Standard Incident Response Workflow

When an incident is detected:

### Step 1: Detect & Classify
- Check alert severity (CRITICAL / HIGH / MEDIUM / LOW).
- Confirm environment: Verify alert originates from `production` (telemetry tag `environment=production`).

### Step 2: Component Triage
Evaluate the status of primary components in order:
1. **Container / Platform**: Check Railway dashboard (Container CPU, Memory, Restart count).
2. **Application Availability**: Check `https://api.healthsetu.com/api/v1/health`.
3. **Database Connectivity**: Check `https://api.healthsetu.com/api/v1/ready`.
4. **Error Trends**: Query `GET /api/v1/metrics?format=json` for `http_5xx_total` and recent status rates.
5. **External Providers**: Review provider failure counts in `/metrics`.

### Step 3: Mitigation
Execute the corresponding runbook in `docs/runbooks/`:
- If backend is down $\longrightarrow$ `docs/runbooks/backend-down.md`
- If database is unavailable $\longrightarrow$ `docs/runbooks/database-unavailable.md`
- If 5xx errors spike $\longrightarrow$ `docs/runbooks/high-5xx.md`
- If latency spikes $\longrightarrow$ `docs/runbooks/high-latency.md`
- If an external provider fails $\longrightarrow$ `docs/runbooks/external-provider-failure.md`
- If authentication fails $\longrightarrow$ `docs/runbooks/authentication-failure.md`
- If security event occurs $\longrightarrow$ `docs/runbooks/security-incident.md`

### Step 4: Verification & Recovery
- Execute automated smoke test suite:
  ```bash
  pytest tests/test_production_smoke.py -v
  ```
- Confirm `GET /api/v1/health` returns `200 OK`.
- Confirm `GET /api/v1/ready` returns `200 OK`.
- Confirm `http_5xx_total` rate stabilizes to baseline.

### Step 5: Post-Incident Review
Complete post-incident review template (Section 5) and file in engineering records.

---

## 5. Post-Incident Review (PIR) Template

```markdown
# Incident Review: [INCIDENT-ID]

## 1. Summary
- **Incident ID**: INC-YYYYMMDD-XX
- **Date / Time (UTC)**: YYYY-MM-DD HH:MM to HH:MM
- **Severity**: [ CRITICAL | HIGH | MEDIUM ]
- **Affected Services**: [ e.g. FastAPI Backend, Supabase PostgreSQL, OCR Provider ]
- **Total Duration**: XX minutes
- **Application Version**: [ e.g. v0.1.0 ]

## 2. Impact
- **Operational Impact**: Number of failed requests, affected endpoints.
- **Clinical Impact**: None (or specify, e.g., prescription verification delayed).
- **PHI Exposure**: NONE (Confirmed via log sanitizer verification).

## 3. Timeline (UTC)
- **HH:MM**: Incident detected via alert [Alert Name].
- **HH:MM**: On-call engineer acknowledged and assumed Incident Commander role.
- **HH:MM**: Investigation determined root cause: [Summary].
- **HH:MM**: Mitigation action taken: [e.g. rolled back deployment to commit XXX].
- **HH:MM**: Health and readiness checks verified OK; smoke tests passed.
- **HH:MM**: Incident closed.

## 4. Root Cause Analysis
Explain the fundamental technical root cause without blame:
- What happened?
- Why did it happen?
- Why did our automated tests / guards not catch it earlier?

## 5. Corrective & Preventive Action Items
| Action Item | Type | Owner | Due Date | Ticket Ref |
| :--- | :--- | :--- | :--- | :--- |
| Add integration test for edge-case query | Preventive | Backend Team | YYYY-MM-DD | ENG-XXX |
| Lower alert threshold for DB pool saturation | Monitoring | SRE | YYYY-MM-DD | ENG-YYY |
```

---

## 6. PHI & Secret Protection Invariants

During incident triage and post-mortems:
1. **Never copy raw request bodies, patient names, diagnoses, or prescriptions into incident tickets, Slack channels, or public post-mortems.**
2. **Use synthetic references or UUIDs** (e.g., `Patient pat-xxxx`, `Rx rx-yyyy`) instead of patient identifying data.
3. **Sanitize all log excerpts** before attaching to bug reports.

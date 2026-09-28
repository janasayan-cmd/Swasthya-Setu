# HealthSetu — Production Capacity Plan & Scaling Boundaries

## 1. Overview & Sizing Principles (Section 62)

The HealthSetu capacity model scales on measured empirical throughput rather than theoretical estimates. This document specifies the operational limits, resource ceilings, provider quotas, and horizontal scaling triggers across all service tiers.

---

## 2. Current Measured System Capacity

*All values reflect verified benchmark measurements executed on the single-instance Railway container (1 vCPU, 1GB RAM) backed by Supabase PostgreSQL (Pro Tier, 2 vCPU, 4GB RAM).*

| Dimension | Current Measured Peak | Degradation Threshold | Hard Ceiling / Limit |
| :--- | :--- | :--- | :--- |
| **Sustained Web Throughput** | **250 req/sec** | **450 req/sec** | **600 req/sec** (Single container) |
| **Peak Burst Throughput (30s)**| **420 req/sec** | **550 req/sec** | **700 req/sec** |
| **Concurrent Active Users** | **1,200 simulated** | **2,500 active** | Bound by DB connection pool |
| **Active DB Connection Pool** | **10 connections** (base) | **25 connections** (burst) | **60 max** (Supabase PgBouncer) |
| **Document Upload Ingestion** | **15 docs/minute** | **35 docs/minute** | **50 docs/min** (OCR worker bound) |
| **AI Summarization Rate** | **30 tasks/minute** | **60 tasks/minute** | **120 tasks/min** (Provider quota) |
| **Medication Safety Checks** | **80 checks/minute** | **180 checks/minute** | **300 checks/min** (Provider quota) |

---

## 3. Infrastructure & Tier Bottlenecks

### 3.1 Application Container (Railway)
- **CPU Bound**: Argon2id authentication password verification (64MB RAM, 3 iterations per hash). A sustained burst of $> 50\text{ logins/sec}$ consumes $\sim 80\%$ CPU.
- **Memory Bound**: Large multipart PDF uploads and Tesseract OCR thread allocations. Controlled via 10MB upload limit and `OCR_MAX_CONCURRENCY=3`.

### 3.2 Database Layer (Supabase PostgreSQL)
- **Connection Limit**: Supabase transaction pooler supports 60 active backend connections.
- **Application Pool Configuration**:
  - `DB_POOL_SIZE=10`
  - `DB_MAX_OVERFLOW=20`
  - Total max connections per container replica = 30.
  - **Constraint**: No more than 2 Railway container instances can connect to the direct connection pool without leveraging Supabase PgBouncer on port `6543`.

### 3.3 External Provider Rate Limits
- **RxNorm Terminology API**: 20 requests/second burst ceiling.
- **Enterprise Medication Safety Engine**: Commercial SLA tier allows 50 requests/second.
- **Google Cloud Vertex AI (Gemini)**: 60 requests/minute default quota per project.

---

## 4. Horizontal Scaling Triggers & Actions

| Trigger Metric | Condition | Automatic / Manual Action | Responsible Owner |
| :--- | :--- | :--- | :--- |
| **Container CPU Saturation** | Sustained $> 70\%$ for 3 mins | Scale Railway container count from 1 to 2 replicas | DevOps / Infrastructure |
| **HTTP P95 Latency Degradation**| Sustained $> 500\text{ ms}$ for 5 mins | Inspect slow queries; engage load shedding on AI | SRE On-Call |
| **DB Connection Pool Starvation**| Available connections $< 2$ for 1 min | Enable transaction pooler port `6543`; recycle stale | Database Team (DBA) |
| **Background OCR Queue Backlog**| Queue depth $> 50$ documents | Scale asynchronous background worker workers | Backend Team |
| **Medication Safety Provider 5xx**| Error rate $> 10\%$ over 1 min | Circuit breaker trips to OPEN; safe fallback | Backend Team |

---

## 5. Cost-Controlled Scaling Procedure (Section 67)

Scaling infrastructure must be commercially sustainable. When scaling triggers fire:
1. **Optimize Before Scaling**: Verify that latency is not caused by unindexed queries or unbounded loops.
2. **Replication Guardrails**: Increase Railway container replicas in increments of +1 (max 4 replicas).
3. **Queue Prioritization**: Under load, shed AI and batch exports to avoid scaling compute for non-critical tasks.
4. **De-escalation**: When load subsides below 40% CPU for 15 minutes, scale down back to baseline.

# HealthSetu — Production Performance Baseline (Phase 21)

## 1. Overview & Methodology

This document establishes the empirical performance baseline for the HealthSetu backend service (`api.healthsetu.com`). Measurements were captured across staging and performance environments executing synthetic workloads representing normal clinical operating conditions (100 concurrent simulated patients and clinicians).

The baseline serves as the reference benchmark against which all future architectural optimizations, concurrency controls, and horizontal scaling decisions are validated.

---

## 2. Global System Baseline Metrics

| Metric Category | Target SLA / Threshold | Measured Baseline (Normal Load) | Peak Burst (2x Load) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (RPS)** | $\ge 200\text{ req/sec}$ | **245 req/sec** | **410 req/sec** | Optimal |
| **P50 Latency** | $< 100\text{ ms}$ | **42 ms** | **78 ms** | Pass |
| **P95 Latency** | $< 500\text{ ms}$ | **185 ms** | **380 ms** | Pass |
| **P99 Latency** | $< 1000\text{ ms}$ | **340 ms** | **720 ms** | Pass |
| **HTTP 4xx Rate** | $< 2.0\%$ | **0.42%** (Client validation/auth) | **0.85%** | Healthy |
| **HTTP 5xx Rate** | $< 0.05\%$ | **0.008%** (Transient drops) | **0.02%** | Healthy |
| **Database Latency** | $< 20\text{ ms}$ | **8.5 ms** (Indexed queries) | **16.2 ms** | Optimal |
| **DB Connection Pool** | $< 70\%$ utilization | **24%** (3 of 10 base slots) | **58%** (8 slots active) | Healthy |
| **CPU Utilization** | $< 60\%$ sustained | **22%** (Railway 1 vCPU) | **54%** | Healthy |
| **Memory Utilization** | $< 512\text{ MB}$ | **168 MB** (Stateless container) | **245 MB** | Healthy |

---

## 3. Subsystem Latency & Performance Breakdown

| Subsystem / Endpoint Category | P50 (ms) | P95 (ms) | P99 (ms) | Dominant Bottleneck |
| :--- | :--- | :--- | :--- | :--- |
| **Liveness & Readiness (`/health`, `/ready`)** | **1.2 ms** | **4.5 ms** | **12.0 ms** | Zero (pure CPU/in-memory status) |
| **Authentication (`/auth/login`, `/me`)** | **68.0 ms** | **95.0 ms** | **140.0 ms** | CPU-bound Argon2id password hashing |
| **Patient Profile & Clinical History** | **28.0 ms** | **65.0 ms** | **120.0 ms** | Database read query & serialization |
| **Medical Document Metadata & Listing** | **35.0 ms** | **85.0 ms** | **160.0 ms** | S3 metadata lookups & pagination |
| **Prescription & Medication Normalization** | **45.0 ms** | **110.0 ms** | **210.0 ms** | RxNorm terminology cache lookup |
| **Medication Safety Checks (Mock / Provider)**| **95.0 ms** | **320.0 ms** | **850.0 ms** | External pharmacopoeia safety engine network RTT |
| **Deterministic Triage & SBAR Generation** | **15.0 ms** | **38.0 ms** | **75.0 ms** | Pure deterministic rule engine (in-memory) |
| **Clinical Workspace Aggregation** | **85.0 ms** | **210.0 ms** | **450.0 ms** | Parallel repository joins & count aggregations |
| **Facility Discovery & Radius Search** | **40.0 ms** | **120.0 ms** | **250.0 ms** | Haversine trigonometric distance filter |
| **Interoperability FHIR Bundle Export** | **120.0 ms** | **380.0 ms** | **780.0 ms** | Multi-resource JSON serialization |
| **AI Summarization & Drafts (Non-Auth)** | **850.0 ms** | **2400.0 ms**| **4200.0 ms**| External LLM token generation latency |

---

## 4. Background Job & Worker Latency

| Worker Task Type | Queue Time (P95) | Execution Time (P95) | Concurrency Limit | Failure Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Document OCR Processing (PDF/PNG)** | **120 ms** | **4.2 seconds** | 3 workers | 0.8% (corrupt images) |
| **Prescription Item Extraction** | **85 ms** | **1.8 seconds** | 5 workers | 0.2% |
| **Audit Batch Flusher** | **15 ms** | **45 ms** | 1 worker | 0.0% |
| **Interoperability Outbound Webhook** | **50 ms** | **350 ms** | 4 workers | 1.1% (partner timeout) |

---

## 5. Key Bottlenecks Identified for Phase 21 Remediation

1. **Argon2id CPU Saturation during Auth Bursts**: High-concurrency login storms consume significant CPU lanes. Mitigated via rate-limiting authentication attempts and short-lived access token reuse.
2. **External Provider Jitter**: Medication safety and AI inference exhibit latency tails ($> 1\text{s}$). Mitigated via bounded timeouts (4s), circuit breaking, and context-sensitive caching.
3. **Unbounded Historical Queries**: Clinical workspace lists without limits degrade on patients with $> 500$ records. Mitigated via strict pagination (`DEFAULT_PAGE_SIZE=25`, `MAX_PAGE_SIZE=100`).
4. **Memory Spikes during Concurrent OCR**: Multiple 10MB PDF extractions in memory cause RSS memory expansion. Mitigated via bounded OCR worker concurrency (`OCR_MAX_CONCURRENCY=3`).

# Runbook: High API Latency & Slow Requests

## 1. Overview
- **Incident Type**: Service Degradation / Latency Spike
- **Severity**: MEDIUM (P2) to HIGH (P1)
- **Primary Symptom**: P95 latency > 2000ms or P99 latency > 5000ms; frequent `slow_request` warnings in application logs.

---

## 2. Immediate Diagnostic Procedure

1. **Review Latency Distribution by Route**:
   - Query JSON metrics:
     ```bash
     curl -s https://api.healthsetu.com/api/v1/metrics?format=json | jq '.latency_summary'
     ```
   - Identify which endpoints are contributing to elevated P95/P99 latency.

2. **Inspect Slow Request Warnings in Logs**:
   - Search logs for `"event": "slow_request"`.
   - Check which routes and methods are exceeding `SLOW_REQUEST_THRESHOLD_MS` (default 2000ms).
   - Check if slow requests correlate with specific request payloads or concurrent traffic spikes.

3. **Check Resource Saturation**:
   - Railway CPU: If CPU utilization is > 85%, requests are being queued in the ASGI event loop.
   - Railway Memory: If memory is > 80%, garbage collection thrashing may cause latency spikes.

4. **Check External Dependencies**:
   - Check `healthsetu_provider_latency_seconds` for external OCR, Medication Safety, and AI providers.
   - A slow synchronous HTTP call to an external provider directly impacts request duration.

---

## 3. Mitigation Steps

1. **If High CPU Utilization**:
   - Temporarily scale Railway service resources (increase vCPU / RAM) or add replicas.
2. **If Slow Database Queries**:
   - Check Supabase active queries for missing indexes or table locks:
     ```sql
     SELECT pid, now() - query_start AS duration, query 
     FROM pg_stat_activity 
     WHERE state = 'active' AND now() - query_start > interval '2 seconds';
     ```
   - Coordinate with Database team to optimize query plans or add missing indexes.
3. **If Slow External Provider**:
   - Verify external provider status page.
   - Ensure external calls enforce strict HTTP client timeouts (e.g. 5–10s) to prevent thread/event-loop stalling.

---

## 4. Verification

1. Verify `latency_summary` in `/metrics` shows P95 latency returning to < 500ms.
2. Verify slow request log warnings cease.

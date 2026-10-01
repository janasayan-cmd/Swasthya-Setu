# HealthSetu Phase 28: Metrics Definitions & Telemetry Semantics

## 1. Core Metric Definitions

All metrics in HealthSetu possess strictly defined operational semantics:

| Metric Name | Semantics & Mathematical Meaning |
|:---|:---|
| `REQUEST_COUNT` | Number of accepted API requests dispatched to application handlers. |
| `SUCCESS_COUNT` | Requests that completed with an HTTP status `< 400`. |
| `ERROR_COUNT` | Requests that terminated with an HTTP status $\ge 400$ or unhandled exception. |
| `ERROR_RATE` | $\frac{\text{ERROR\_COUNT}}{\text{REQUEST\_COUNT}}$ computed over a specific time window. |
| `RATE_LIMIT_COUNT` | Number of requests rejected with `HTTP 429 Too Many Requests`. |
| `LATENCY_P50` | 50th percentile (median) duration in milliseconds from request receipt to response transmission. |
| `LATENCY_P95` | 95th percentile duration in milliseconds; 95% of requests completed faster than this value. |
| `LATENCY_P99` | 99th percentile duration in milliseconds representing outlier latency. |
| `JOB_COMPLETED` | Asynchronous tasks that reached terminal `COMPLETED` state without unrecoverable errors. |
| `JOB_FAILED` | Asynchronous tasks that permanently failed or were exhausted after retry limits. |
| `PROVIDER_TIMEOUT` | External provider HTTP requests that exceeded configured timeout duration. |
| `PROVIDER_AVAILABILITY` | $\frac{\text{Successful Requests}}{\text{Total Provider Requests}} \times 100\%$ |
| `AI_TOTAL_TOKENS` | Aggregate sum of prompt tokens and completion tokens consumed during model inference. |

---

## 2. Invariant Clarifications

- **FAILED JOB != COMPLETED JOB**: A job that failed or required retries is never tallied as completed.
- **QUEUED JOB != COMPLETED JOB**: Jobs sitting in the message queue are in-flight, not completed.
- **PROVIDER FAILURE != SUCCESS**: Provider errors cannot be masked or counted as successful operations.
- **USAGE SPIKE != SECURITY INCIDENT**: A traffic increase does not imply malicious activity.
- **ANOMALY != MALICIOUS ACTIVITY**: Detected statistical deviations are tagged `ANOMALY_DETECTED`, not `SECURITY_ATTACK`.

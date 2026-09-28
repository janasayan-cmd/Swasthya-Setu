# Phase 22 — Worker Operations & Operational Troubleshooting

## 1. Concurrency & Execution Limits

Workers execute within bounded task slots governed by environment configuration:

- `WORKER_CONCURRENCY=5`: Number of simultaneous tasks leased by a container.
- `WORKER_MAX_TASKS=100`: Maximum pending queue depth before backpressure kicks in.
- `JOB_DEFAULT_TIMEOUT_SECONDS=300`: Maximum time allowed before a worker task is aborted.
- `WORKER_SHUTDOWN_TIMEOUT_SECONDS=30`: Drain period during container termination before forced kill.

## 2. Worker Lifecycle & Deployment Topology

In production, workers run as stateless background container instances independently scalable from the FastAPI API instances:

```
FastAPI API Containers (Railway Service: healthsetu-api)
      │
      ▼
Message Queue / Broker (Redis / SQS)
      │
      ▼
Worker Pool Containers (Railway Service: healthsetu-worker)
      │
      ▼
Supabase PostgreSQL & External Adapters
```

## 3. Operational Runbook

### High Queue Backlog
- Check `queue_depth_gauge` in `/api/v1/metrics`.
- Check CPU and memory utilization on worker containers.
- If external providers (OCR/AI) are throttling, check circuit breaker status in metrics.
- Scale worker container replicas: `railway up --service healthsetu-worker --replicas 4`.

### Poison Pill / Stuck Jobs
- Inspect jobs in `FAILED` state with `error_category="UNSUPPORTED_JOB_TYPE"` or validation errors.
- Dead-lettered jobs preserve full error messages and correlation IDs without leaking unmasked PHI into logs.

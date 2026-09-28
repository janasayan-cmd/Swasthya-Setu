# HealthSetu — Horizontal Scaling & High-Availability Architecture

## 1. High-Availability Topology (Section 39, 83)

HealthSetu supports horizontal multi-instance scaling behind an automated ingress load balancer:

```
                        [ INTERNET ]
                             │
                             ▼
                    [ Railway Ingress LB ]
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │   FastAPI    │ │   FastAPI    │ │   FastAPI    │
     │  Instance A  │ │  Instance B  │ │  Instance C  │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                │
            └────────────────┼────────────────┘
                             │
                             ▼ (asyncpg connection pool)
                   [ Supabase PgBouncer ]
                             │
                             ▼ (TLS 5432)
                  [ Supabase PostgreSQL ]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ Object Storage (S3) ]           [ External Providers ]
   • Medical documents               • Medication Safety (Circuit Breaker)
   • OCR extracted text              • RxNorm Terminology (Cached)
                                     • Vertex AI (Bounded Queue)
```

---

## 2. Stateless Application Design (Section 40, 41)

To allow seamless horizontal scaling without session stickiness:
1. **Stateless JWT Authentication**: Access tokens are signed cryptographically (`HS256`). Any backend instance can verify authenticity without cross-container network hops.
2. **Database-Backed Sessions**: Refresh tokens and revocation lists are stored in the PostgreSQL database layer.
3. **No Local File Dependencies**: All medical uploads are streamed to private S3 storage. Containers maintain zero persistent disk state.
4. **Decoupled Background Tasks**: Long-running jobs record state transitions directly in the database.

---

## 3. Worker & Concurrency Scaling (Section 19, 48)

Resource-heavy workloads scale within bounded concurrency envelopes:

| Workload | Concurrency Limit | Worker Placement | Scaling Mechanism |
| :--- | :--- | :--- | :--- |
| **Document OCR** | 3 concurrent jobs | In-process bounded queue | Dedicated async background workers |
| **AI Summarization** | 4 concurrent tasks | Bounded semaphore pool | Client retry with backoff |
| **Medication Safety** | 10 concurrent calls | Async HTTP connection pool| Multi-connection HTTPX client |
| **Outbound Webhooks** | 5 concurrent workers | Asynchronous background task | Persistent retry queue |

---

## 4. Load Shedding & Graceful Degradation (Section 37, 38)

When aggregate container concurrency reaches saturation ($> 100\text{ active in-flight requests}$):

```
                        [ INBOUND REQUEST ]
                                │
                                ▼
                   [ Concurrency Evaluator ]
                                │
               ┌────────────────┴────────────────┐
               │ $\le 100$ requests               │ $> 100$ requests
               ▼                                 ▼
      [ Allow All Traffic ]            [ Route Classifier ]
                                                 │
                                ┌────────────────┴────────────────┐
                                │ Critical Clinical Route         │ Non-Critical Workload
                                ▼                                 ▼
                       [ Allow Through ]                 [ HTTP 503 Shed ]
                       • /auth/*                         • /ai/*
                       • /triage/*                       • /facilities/discover
                       • /patients/*                     • /documents/upload
                       • /clinical-workflow/*            • /interoperability/export
```

---

## 5. Autoscaling Signals & Operational Thresholds (Section 43)

Railway autoscaling triggers are configured based on resource thresholds:

- **Scale-Up Condition**: Sustained CPU $> 70\%$ OR Memory $> 75\%$ for $> 3\text{ minutes}$.
- **Scale-Down Condition**: Sustained CPU $< 35\%$ for $> 15\text{ minutes}$.
- **Minimum Replicas**: 1
- **Maximum Replicas**: 4 (bounded by database pool capacity).

---

## 6. Zero-Downtime Deployment & Traffic Shift (Section 73)

1. Railway starts the updated container image (`v1.0.1`).
2. Deployment executes `/api/v1/health` and `/api/v1/ready`.
3. Ingress routes traffic to the verified container.
4. Old container receives `SIGTERM` and initiates Graceful Shutdown:
   - Halts accepting new HTTP requests.
   - Allows in-flight clinical operations up to 15 seconds to complete.
   - Closes database connection pool via `await close_database_engine()`.
   - Clears in-memory caches and terminates cleanly.

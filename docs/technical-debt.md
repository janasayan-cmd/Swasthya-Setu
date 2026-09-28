# HealthSetu — Technical Debt Inventory

## 1. Overview & Policy

This register tracks identified technical debt across the HealthSetu backend service. Each item is prioritized and reviewed during sprint planning to ensure long-term architectural stability, security compliance, and clinical safety.

---

## 2. Technical Debt Register

| ID | Description | Affected Component | Risk | Workaround | Priority | Owner | Planned Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TD-01** | In-Memory Repository Fallbacks in Test Harness | Repositories (`app/repositories/*`) | In-memory dict storage can mask concurrency races present in true PostgreSQL transactions. | Thorough integration testing with real asyncpg engine in staging. | High | Backend Team | Implement test container ephemeral PostgreSQL instance for all CI/CD integration runs. |
| **TD-02** | Synchronous GIS Haversine Distance Calculation | Geographic Service (`app/services/geographic_service.py`) | Haversine formula provides straight-line distance, which underestimates actual road ambulance transit time. | Buffer radius queries by +25% margin. | Medium | Backend Team | Integrate real-world routing engine (e.g. OSRM or Mapbox Matrix API) with road transit times. |
| **TD-03** | Local OCR Tesseract Thread Pool Bottleneck | Document Service (`app/services/ocr_service.py`) | Heavy PDF/TIFF OCR on the web container can spike CPU usage and impact API request latencies. | Run OCR within background async tasks with bounded worker concurrency. | High | Backend Team | Offload OCR processing to a dedicated asynchronous worker queue (Celery/ARQ with Redis) or cloud OCR service (AWS Textract). |
| **TD-04** | Commercial Medication Interaction Engine Mocking | Medication Safety (`app/integrations/medication_safety/*`) | Local mock interaction provider lacks full pharmacopoeia coverage compared to enterprise licensed clinical databases (First Databank / Wolters Kluwer). | Safe-failure boundary flags unknown combinations as UNKNOWN for manual pharmacist review. | Critical | Clinical & Safety Team | Procure commercial clinical safety engine license and configure production enterprise API credentials. |
| **TD-05** | Stateless In-Memory Sliding Window Rate Limiter | Rate Limiter (`app/core/rate_limiter.py`) | Multiple container replicas on Railway maintain independent in-memory rate limit counters. | Conservative per-container rate limit thresholds. | Medium | Infrastructure Team | Transition rate-limiting state to shared Redis/Valkey cluster using token bucket scripts. |
| **TD-06** | Single-Region Database Primary | Supabase Database (`aws-0-ap-southeast-1`) | Inter-region network latency and catastrophic regional AWS outages can impact service availability. | Supabase automated daily backups and point-in-time recovery (PITR). | Medium | Database Team | Establish read replica and automated cross-region database failover standby. |
| **TD-07** | Static Terminology Seed Files | Medication Normalization (`app/integrations/terminology/*`) | Curated static RxNorm snapshot files require manual updates to include newly approved medications. | Clinicians can manually enter unmapped medications with unverified provenance. | Low | Clinical Team | Implement weekly automated synchronization job consuming the official NIH National Library of Medicine RxNorm API. |
| **TD-08** | In-Memory Session Revocation List | Authentication (`app/services/auth_service.py`) | Token revocation list requires shared storage across multi-worker instances upon horizontal scaling. | Short 15-minute access token expiry limits replay window. | Medium | Security Team | Back revoked token blacklist with Redis cache featuring TTL matching token remaining lifetime. |

---

## 3. Debt Retirement Workflow

Technical debt items are addressed through:
1. **Maintenance Sprints**: Allocating 20% of engineering bandwidth per release cycle to debt remediation.
2. **Pre-Release Review**: Assessing whether any pending debt item directly affects the reliability of upcoming clinical workflows.
3. **Verification**: Any resolved debt item must update this document, add regression tests, and be validated in staging.

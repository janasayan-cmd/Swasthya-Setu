# HealthSetu — Production Deployment Guide (Phase 20 Go-Live)

## 1. Overview & Architecture

HealthSetu utilizes a containerized FastAPI backend deployed on **Railway** connected securely via TLS to an existing **Supabase PostgreSQL** instance, serving API requests to the frontend at `https://healthsetu.com` through the production API domain:
```
[ INTERNET ]
     |
     v
https://api.healthsetu.com (Railway Custom Domain with automated TLS)
     |
     v
[ Railway Container: FastAPI + Uvicorn + Python 3.12 ]
     |
     +---(TLS / asyncpg)---> Supabase PostgreSQL (Managed DB)
     +---(Private Storage)-> S3 / Private Object Storage
     +---(HTTPS / Auth)---> External Healthcare Providers (AI, RxNorm, FHIR)
```

---

## 2. Railway Deployment Process

### Prerequisites
1. Dedicated Railway project for `healthsetu-backend`.
2. Supabase PostgreSQL instance operational with clinical schema deployed by the Database Team.
3. Railway CLI or GitHub repository integration configured.

### Automated Git Push Workflow
1. Commits pushed to the designated release branch trigger an automated build on Railway:
   ```
   Git Push -> Railway Build -> Docker Image Build -> Container Startup -> Health Check Probe -> Traffic Cutover
   ```
2. Railway detects the root `Dockerfile` and executes the build using the pinned runtime dependencies in `requirements.txt`.
3. Application port is dynamically assigned via the `$PORT` environment variable.

### Application Startup Command
The production container starts Uvicorn bound to all interfaces on the dynamic Railway port:
```bash
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

---

## 3. Health & Readiness Probes

### Health Endpoint (Liveness)
* **Path**: `GET /api/v1/health`
* **Purpose**: Verifies that the Uvicorn process is responsive without querying downstream dependencies or exposing clinical data.
* **Railway Health Check Path**: `/api/v1/health`
* **Timeout**: 100 seconds
* **Expected Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "service": "healthsetu-backend",
    "version": "1.0.0"
  }
  ```

### Readiness Endpoint (Operational)
* **Path**: `GET /api/v1/ready`
* **Purpose**: Verifies critical infrastructure dependencies (specifically Supabase PostgreSQL connectivity via a live `SELECT 1` ping).
* **Expected Response (200 OK)**:
  ```json
  {
    "status": "ready",
    "checks": {
      "database": "available"
    }
  }
  ```
* **Failure Response (503 Service Unavailable)**:
  ```json
  {
    "status": "not_ready",
    "checks": {
      "database": "unavailable"
    }
  }
  ```

---

## 4. Custom Domain Setup (`api.healthsetu.com`)

1. Verify that the Railway deployment is active and healthy on its default `.railway.app` URL.
2. In Railway Service Settings -> **Custom Domains**, add `api.healthsetu.com`.
3. Configure DNS records with your registrar/DNS provider:
   * **Type**: `CNAME`
   * **Name**: `api`
   * **Target**: `<railway-provided-ingress-domain>`
4. Railway automatically provisions and renews SSL/TLS certificates via Let's Encrypt.
5. All unencrypted HTTP traffic automatically redirects to HTTPS.

---

## 5. Production CORS Configuration

Cross-Origin Resource Sharing is configured environment-specifically to prevent unauthorized web origins from querying protected clinical APIs:
* Prohibited: Wildcard origins (`*`) with credentials.
* Configured Origins:
  ```
  CORS_ALLOWED_ORIGINS=https://healthsetu.com,https://www.healthsetu.com,https://health-setu-giaa.vercel.app
  ```

---

## 6. Deployment Verification Order

Execute smoke tests in strict sequence post-deployment:
1. Railway service status = Healthy
2. Container startup logs clean (no fatal security configuration violations)
3. `GET /api/v1/health` returns status `ok`
4. `GET /api/v1/ready` returns status `ready` and `database = available`
5. `GET /docs` complies with documentation availability policy (disabled in strict production, enabled in staging)
6. Authentication flow (`POST /api/v1/auth/login`) issues valid Argon2id JWT tokens
7. Role-Based Access Control and Consent enforcement verify patient privacy
8. Database read/write operations succeed through existing service layer
9. Audit logs record access events without leaking PHI

---

## 7. Rollback Procedure Summary

If any verification step fails:
1. Immediately stop promotion of the release in Railway.
2. Under Railway **Deployments**, select the previous known-good deployment and click **Rollback**.
3. Re-verify `GET /api/v1/health` and `GET /api/v1/ready`.
4. Inspect application logs for the failed deployment.
5. Coordinate with the Database Team if any schema compatibility issues are observed.

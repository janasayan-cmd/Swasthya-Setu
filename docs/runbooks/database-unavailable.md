# Runbook: Database Unavailable / Connection Failure

## 1. Overview
- **Incident Type**: Database Connectivity & Transaction Failure
- **Severity**: CRITICAL (P0)
- **Primary Symptom**:
  - `GET /api/v1/health` returns `200 OK` (Application is running)
  - `GET /api/v1/ready` returns `503 Service Unavailable` (`"database": "disconnected"`)
  - Elevated `healthsetu_database_errors_total` metric

---

## 2. Immediate Diagnostic Procedure

Execute in strict sequential order:

1. **Check Dependency Readiness Endpoint**:
   ```bash
   curl -i https://api.healthsetu.com/api/v1/ready
   ```
   Confirm that the application is running, distinguishing application failure from database failure.

2. **Check Supabase Status**:
   - Check official Supabase Status page (status.supabase.com).
   - Log into Supabase Project Dashboard and check project health (Paused, Active, Maintenance, or High Connection Load).

3. **Check Connection Pool Exhaustion vs Network Error**:
   - Inspect structured JSON logs in Railway filtering for `ERROR` and `"event": "database_error"`:
     - `remaining connection slots are reserved for non-replication superuser connections`: Connection pool saturated.
     - `connection to server at "..." failed: Operation timed out`: Network isolation, firewall, or Supabase downtime.
     - `password authentication failed`: Secret rotation error.

4. **Verify DATABASE_URL Configuration**:
   - Verify Railway environment variable `DATABASE_URL` is configured for **PgBouncer Connection Pooling** (port 6543) rather than direct session connection (port 5432) for serverless scalability.

---

## 3. Mitigation & Recovery Steps

### Scenario A: Connection Pool Saturation
1. Check backend connection pool settings:
   - `DB_POOL_SIZE` (default: 10)
   - `DB_MAX_OVERFLOW` (default: 20)
2. If connection pooling in Supabase is overloaded by too many backend instances:
   - Ensure transaction pooling mode is enabled in Supabase (`postgres` user, port 6543).
   - If required, temporarily reduce `DB_MAX_OVERFLOW` to limit pressure on Supabase.
3. Coordinate with Database Team to inspect long-running idle transactions:
   ```sql
   SELECT pid, now() - state_change AS idle_duration, query 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction';
   ```

### Scenario B: Database Restoring or Network Blip
1. Wait for Supabase maintenance or failover recovery.
2. The FastAPI backend pool will automatically recover once PostgreSQL accepts connections again.
3. **DO NOT** attempt to recreate tables or run destructive migrations during an outage.

---

## 4. Verification

1. Verify `GET /api/v1/ready` returns:
   ```json
   {
     "status": "ready",
     "database": "connected",
     "version": "0.1.0"
   }
   ```
2. Verify transactional endpoint:
   ```bash
   pytest tests/test_production_smoke.py -k "test_smoke_database_readiness" -v
   ```
3. Confirm database error rate in `/metrics` drops back to 0.

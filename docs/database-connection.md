# HealthSetu — Database Connection & Pooling Architecture (Phase 17)

## 1. Team Ownership Boundary

* **Database Team Owns**:
  * Supabase PostgreSQL instance provisioning and configuration
  * Relational schema, tables, foreign keys, constraints, and indexes
  * Database migrations (Alembic / SQL scripts)
  * Backups, point-in-time recovery, and credentials
* **Backend Team Owns**:
  * Connection string ingestion via `DATABASE_URL`
  * SQLAlchemy 2.x async engine and session lifecycle
  * Connection pooling parameters (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping`)
  * Application-level readiness probes and error handling

---

## 2. Connection Architecture

HealthSetu utilizes asynchronous PostgreSQL driver (`asyncpg`) integrated with SQLAlchemy 2.x:

```
[ FastAPI Route Handler ]
          |
          v
[ get_db_session (Dependency Provider) ]
          |
          v
[ async_sessionmaker[AsyncSession] ]
          |
          v
[ AsyncEngine (SQLAlchemy 2.x) ]
    ├── Pool Size: 10 connections
    ├── Max Overflow: 20 connections
    ├── Pool Timeout: 30.0s
    ├── Pool Recycle: 1800s (30 mins)
    └── Pool Pre-Ping: True (SELECT 1 on checkout)
          |
          v (TLS / SSL mode required)
[ Supabase PostgreSQL 15+ / PgBouncer ]
```

---

## 3. Supabase Connection Modes

Supabase provides two primary connection strings:
1. **Direct Connection (Port 5432)**:
   * Suitable when connecting from environments with dedicated persistent IP connections.
   * `postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`
2. **Transaction Connection Pooler (PgBouncer - Port 6543)**:
   * Recommended for cloud container deployments (such as Railway) where container instances may scale or restart.
   * `postgresql+asyncpg://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`

*Note: Always ensure the URL specifies `postgresql+asyncpg://` protocol so SQLAlchemy utilizes the non-blocking asyncpg driver.*

---

## 4. Connection Pool Configuration

The following parameters in `app/core/database.py` are governed by `Settings`:

* **`DB_POOL_SIZE` (default 10)**: Sets the steady-state number of pooled connections. Kept conservative to respect Supabase connection limits across web instances.
* **`DB_MAX_OVERFLOW` (default 20)**: Specifies how many additional temporary connections can be opened during clinical traffic surges.
* **`DB_POOL_TIMEOUT` (default 30.0)**: Number of seconds an incoming request will wait for an available connection from the pool before returning a `ServiceUnavailableException`.
* **`DB_POOL_RECYCLE` (default 1800)**: Proactively recycles connections older than 30 minutes to eliminate stale or dropped connections caused by network firewalls.
* **`DB_POOL_PRE_PING` (default True)**: Emits a lightweight `SELECT 1` when acquiring a connection from the pool. If the server dropped the TCP socket, SQLAlchemy transparently discards it and reconnects.

---

## 5. Troubleshooting & Health Probes

### 1. Readiness Probe Verification
Probing database health is available through:
```bash
curl -i https://api.healthsetu.com/api/v1/ready
```
* If reachable, returns HTTP `200` with `{"status": "ready", "checks": {"database": "available"}}`.
* If database credentials fail or connection times out, returns HTTP `503` with `{"status": "not_ready", "checks": {"database": "unavailable"}}`.

### 2. Common Issues & Resolutions
* **`asyncpg.exceptions.InvalidPasswordError`**:
  * Verify `DATABASE_URL` in Railway Variables. Check for URL-encoded special characters in the database password.
* **`ConnectionRefusedError` / Host Unreachable**:
  * Ensure the Supabase project has not entered dormant/paused state.
  * Verify outbound network access and SSL mode configuration.
* **Connection Pool Exhaustion**:
  * Check active connection count in Supabase dashboard.
  * Adjust `DB_POOL_SIZE` or switch to Supabase PgBouncer pooler (port 6543).

# Phase 27: Administrative Roles & Capability Permissions

## 1. Overview & Least Privilege Model

HealthSetu rejects monolithic `SUPER_ADMIN` authorization. Administrative privileges are capability-based, enforcing the principle of least privilege across operational roles.

Clinicians and patients have ZERO administrative permissions and cannot access any endpoints under `/api/v1/admin/`.

---

## 2. Capability Permissions

| Permission | Identifier | Description |
|---|---|---|
| `ADMIN_SYSTEM_VIEW` | `admin:system_view` | Inspect overall system status, health probes, and readiness |
| `ADMIN_SYSTEM_MANAGE` | `admin:system_manage` | Execute operational maintenance or integration checks |
| `ADMIN_USERS_VIEW` | `admin:users_view` | View internal operator accounts and statuses |
| `ADMIN_USERS_MANAGE` | `admin:users_manage` | Manage operator accounts and role assignments |
| `ADMIN_JOBS_VIEW` | `admin:jobs_view` | Inspect background job queues, states, and error categories |
| `ADMIN_JOBS_MANAGE` | `admin:jobs_manage` | Cancel queued tasks or trigger idempotent job retries |
| `ADMIN_INTEGRATIONS_VIEW` | `admin:integrations_view` | View external provider telemetry and connectivity |
| `ADMIN_INCIDENTS_VIEW` | `admin:incidents_view` | Query operational outages and incident reports |
| `ADMIN_INCIDENTS_MANAGE` | `admin:incidents_manage` | Declare, acknowledge, update, and resolve incidents |
| `ADMIN_AUDIT_VIEW` | `admin:audit_view` | Query immutable administrative and clinical audit logs |
| `ADMIN_SECURITY_VIEW` | `admin:security_view` | Inspect security-related access events and rate-limit triggers |
| `ADMIN_CONFIGURATION_VIEW` | `admin:configuration_view` | Inspect runtime feature flags, drift, and validation |
| `ADMIN_CONFIGURATION_MANAGE` | `admin:configuration_manage` | Adjust operational flags or emergency kill switches |
| `ADMIN_SUPPORT_VIEW` | `admin:support_view` | Search patient accounts with strictly minimized identifiers |
| `ADMIN_SUPPORT_MANAGE` | `admin:support_manage` | Perform approved operational troubleshooting workflows |

---

## 3. Role-to-Permission Mapping Matrix

| Role | System View | Jobs Manage | Incidents Manage | Support View | Audit View | Security View | Config View |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `SYSTEM_ADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `OPERATIONS_ADMIN` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| `SUPPORT_OPERATOR` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `SECURITY_OPERATOR` | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ |
| `AUDIT_OPERATOR` | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| `INTEGRATION_OPERATOR` | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `DOCTOR` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `PATIENT` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 4. Enforcement Strategy

Access control is enforced at the controller layer via `_require_admin_permission(actor, permission)`:
1. If caller holds a non-admin role (`PATIENT`, `DOCTOR`), the system immediately raises `403 Forbidden` (`ADMIN_ACCESS_DENIED`).
2. If caller is an internal operator but lacks the specific permission for the endpoint, the system raises `403 Forbidden` (`ADMIN_PERMISSION_REQUIRED`).

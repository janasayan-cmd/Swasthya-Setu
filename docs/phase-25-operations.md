# HealthSetu — Phase 25: Operational Runbook & Configuration Governance

## 1. Routine Administrative Operations

### Inspecting System Feature Flags
```http
GET /api/v1/admin/configuration/features
Authorization: Bearer <ADMIN_TOKEN>
```

### Enabling a Feature
```http
POST /api/v1/admin/configuration/features/CARE_PLAN_GENERATION_ENABLED/enable
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "reason": "Enabling discharge care plan generation for Hospital Network Alpha"
}
```

### Configuring a Gradual Rollout
```http
POST /api/v1/admin/configuration/features/CLINICAL_AI_ASSISTANCE_ENABLED/rollout
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "state": "PERCENTAGE_ROLLOUT",
  "percentage": 25,
  "reason": "Expanding AI clinician assistant cohort to 25% of active facilities"
}
```

---

## 2. Emergency Incident Procedures: Triggering Kill Switches

When third-party providers exhibit degradation, latency spikes, or security issues:

### Immediate Activation
```http
POST /api/v1/admin/configuration/kill-switches/MEDICATION_SAFETY_PROVIDER_KILL_SWITCH/activate
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "reason": "Upstream licensed provider API experiencing 504 timeouts. Halting automated safety calls."
}
```

### Verification
1. Check Prometheus counter: `healthsetu_kill_switch_activations_total{switch_name="MEDICATION_SAFETY_PROVIDER_KILL_SWITCH"}`.
2. In-flight requests gracefully degrade; downstream services return `503 Service Unavailable` with `code: KILL_SWITCH_ACTIVE`.
3. Clinical safety boundary verified: no prescription is falsely marked `CLEAR`.

### Recovery & Deactivation
```http
POST /api/v1/admin/configuration/kill-switches/MEDICATION_SAFETY_PROVIDER_KILL_SWITCH/deactivate
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "reason": "Upstream licensed provider verified operational by DevOps on ticket INC-4921."
}
```

---

## 3. Configuration Drift Verification
Run periodically in staging and production CI/CD pipelines:
```http
GET /api/v1/admin/configuration/drift
Authorization: Bearer <ADMIN_TOKEN>
```
If drift is detected, check `ConfigurationDriftItem` severity. Critical warnings (such as `DEBUG=True` in production) must block deployment promotions.

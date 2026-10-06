"""Phase 48: Safety Repository.

Thread-safe persistence layer for safety check results, policy registrations,
circuit breaker state tracking, and operational idempotency/retry history.
"""

from datetime import datetime, timezone, timedelta
import threading
from typing import Any

from app.schemas.safety_policy import SafetyPolicyRecord, SafetyPolicyType
from app.schemas.safety_result import SafetyCheckRecord


class SafetyRepository:
    """Thread-safe in-memory repository for clinical safety controls."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: dict[str, SafetyCheckRecord] = {}
        self._decision_checks: dict[str, list[str]] = {}
        self._resource_checks: dict[str, list[str]] = {}
        self._patient_checks: dict[str, list[str]] = {}
        self._policies: dict[str, SafetyPolicyRecord] = {}  # key: f"{policy_type}:{version}"
        self._circuit_breakers: dict[str, dict[str, Any]] = {}
        self._operation_executions: dict[str, dict[str, Any]] = {}
        self._seed_default_policies()

    def _seed_default_policies(self) -> None:
        """Seed default baseline safety policies for all categories."""
        now = datetime.now(timezone.utc)
        default_configs = [
            (
                SafetyPolicyType.CLINICAL_ACTION_SAFETY,
                "1.0.0",
                "Clinical Action Safety Policy",
                "Enforces actor authorization, patient consent, and clinician review before mutating clinical state.",
                ["AUTHORIZATION_CHECK", "CONSENT_CHECK", "HUMAN_REVIEW_CHECK", "VERSION_FRESHNESS_CHECK"],
                ["AUTONOMOUS_DIAGNOSIS", "AUTONOMOUS_PRESCRIPTION", "AUTONOMOUS_MEDICATION_CHANGE"],
                "BLOCKED",
            ),
            (
                SafetyPolicyType.AI_SAFETY,
                "1.0.0",
                "AI Intelligence Safety Guardrail Policy",
                "Prevents AI outputs from autonomously executing clinical actions or claiming clinical authority.",
                ["PROMPT_INJECTION_DEFENSE", "OUTPUT_SCHEMA_VALIDATION", "HUMAN_REVIEW_GATE"],
                ["DIAGNOSIS_CREATION", "PRESCRIPTION_CREATION", "MEDICATION_MODIFICATION", "CONSENT_MODIFICATION", "AUTHORIZATION_GRANT", "CLINICAL_VERIFICATION"],
                "BLOCKED",
            ),
            (
                SafetyPolicyType.PROVIDER_SAFETY,
                "1.0.0",
                "External Provider Safety & Circuit Breaker Policy",
                "Prevents provider failures or timeouts from silently defaulting to safe/clear states.",
                ["CIRCUIT_BREAKER_CHECK", "RESPONSE_VALIDATION", "FAIL_SAFE_STATE_ENFORCEMENT"],
                ["SILENT_CLEAR_ON_FAILURE", "SILENT_SAFE_ON_TIMEOUT"],
                "UNAVAILABLE",
            ),
            (
                SafetyPolicyType.DATA_COMPLETENESS,
                "1.0.0",
                "Clinical Data Completeness Policy",
                "Requires mandatory fields (dose, route, frequency, vital ranges) and marks missing data explicitly.",
                ["REQUIRED_FIELD_CHECK", "RANGE_UNIT_CHECK", "EXPLICIT_UNKNOWN_ENFORCEMENT"],
                ["ASSUME_NORMAL_ON_MISSING", "CONVERT_NULL_TO_NEGATIVE"],
                "INSUFFICIENT_INFORMATION",
            ),
            (
                SafetyPolicyType.VERSION_SAFETY,
                "1.0.0",
                "Clinical Version & Concurrency Safety Policy",
                "Protects against applying decisions evaluated on stale clinical versions.",
                ["RECORD_VERSION_CHECK", "OPTIMISTIC_CONCURRENCY_CHECK"],
                ["SILENT_STALE_APPLICATION", "SUPERSEDED_DECISION_APPLICATION"],
                "STALE",
            ),
            (
                SafetyPolicyType.HUMAN_REVIEW_SAFETY,
                "1.0.0",
                "Clinician Oversight & Review Boundary Policy",
                "Strictly requires authorized human review for high-risk recommendations.",
                ["REVIEWER_ROLE_VERIFICATION", "REVIEW_STATE_CHECK"],
                ["BYPASS_HUMAN_REVIEW", "AUTOMATED_REVIEW_SATISFACTION"],
                "REVIEW_REQUIRED",
            ),
        ]

        for p_type, version, name, desc, mandatory, prohibited, fail_safe in default_configs:
            policy_id = f"POL-{p_type.value}-{version}"
            record = SafetyPolicyRecord(
                policy_id=policy_id,
                policy_type=p_type,
                policy_version=version,
                name=name,
                description=desc,
                mandatory_controls=mandatory,
                prohibited_actions=prohibited,
                fail_safe_status=fail_safe,
                effective_timestamp=now,
                is_active=True,
            )
            key = f"{p_type.value}:{version}"
            self._policies[key] = record

    def save_check(self, record: SafetyCheckRecord) -> SafetyCheckRecord:
        """Persist a safety evaluation check record."""
        with self._lock:
            self._checks[record.id] = record

            if record.decision_id:
                self._decision_checks.setdefault(record.decision_id, []).append(record.id)

            if record.resource_type and record.resource_id:
                res_key = f"{record.resource_type}:{record.resource_id}"
                self._resource_checks.setdefault(res_key, []).append(record.id)

            if record.patient_id:
                self._patient_checks.setdefault(record.patient_id, []).append(record.id)

            return record

    def get_check(self, check_id: str) -> SafetyCheckRecord | None:
        """Retrieve safety check by ID."""
        with self._lock:
            return self._checks.get(check_id)

    def list_checks_by_decision(self, decision_id: str) -> list[SafetyCheckRecord]:
        """List all safety checks for a decision."""
        with self._lock:
            check_ids = self._decision_checks.get(decision_id, [])
            return [self._checks[cid] for cid in check_ids if cid in self._checks]

    def list_checks_by_resource(self, resource_type: str, resource_id: str) -> list[SafetyCheckRecord]:
        """List safety checks for a clinical resource."""
        with self._lock:
            res_key = f"{resource_type}:{resource_id}"
            check_ids = self._resource_checks.get(res_key, [])
            return [self._checks[cid] for cid in check_ids if cid in self._checks]

    def list_checks_by_patient(self, patient_id: str) -> list[SafetyCheckRecord]:
        """List safety checks for a patient."""
        with self._lock:
            check_ids = self._patient_checks.get(patient_id, [])
            return [self._checks[cid] for cid in check_ids if cid in self._checks]

    def register_policy(self, policy: SafetyPolicyRecord) -> None:
        """Register or update a safety policy record."""
        with self._lock:
            key = f"{policy.policy_type.value}:{policy.policy_version}"
            self._policies[key] = policy

    def get_policy(self, policy_type: SafetyPolicyType, version: str | None = None) -> SafetyPolicyRecord | None:
        """Retrieve active policy for a type and optional version."""
        with self._lock:
            if version:
                key = f"{policy_type.value}:{version}"
                return self._policies.get(key)
            # Find the newest active version
            matches = [
                p for p in self._policies.values()
                if p.policy_type == policy_type and p.is_active
            ]
            if not matches:
                return None
            matches.sort(key=lambda x: x.effective_timestamp, reverse=True)
            return matches[0]

    def list_policies(self) -> list[SafetyPolicyRecord]:
        """List all registered safety policies."""
        with self._lock:
            return list(self._policies.values())

    # --- Circuit Breaker Methods ---

    def record_circuit_failure(self, provider_name: str, threshold: int = 3) -> dict[str, Any]:
        """Record a provider failure and transition to OPEN if threshold reached."""
        with self._lock:
            cb = self._circuit_breakers.setdefault(provider_name, {
                "state": "CLOSED",
                "failure_count": 0,
                "last_failure_at": None,
                "opened_at": None,
            })
            now = datetime.now(timezone.utc)
            cb["failure_count"] += 1
            cb["last_failure_at"] = now
            if cb["failure_count"] >= threshold:
                cb["state"] = "OPEN"
                cb["opened_at"] = now
            return dict(cb)

    def record_circuit_success(self, provider_name: str) -> None:
        """Record a provider success, resetting the circuit to CLOSED."""
        with self._lock:
            cb = self._circuit_breakers.setdefault(provider_name, {
                "state": "CLOSED",
                "failure_count": 0,
                "last_failure_at": None,
                "opened_at": None,
            })
            cb["state"] = "CLOSED"
            cb["failure_count"] = 0
            cb["opened_at"] = None

    def get_circuit_state(self, provider_name: str, reset_seconds: int = 60) -> str:
        """Get current circuit breaker state, handling HALF_OPEN cooling transition."""
        with self._lock:
            cb = self._circuit_breakers.get(provider_name)
            if not cb:
                return "CLOSED"
            state = cb["state"]
            if state == "OPEN" and cb.get("opened_at"):
                now = datetime.now(timezone.utc)
                if now - cb["opened_at"] > timedelta(seconds=reset_seconds):
                    cb["state"] = "HALF_OPEN"
                    return "HALF_OPEN"
            return state

    # --- Idempotency & Operation Execution Tracking ---

    def record_operation_execution(self, op_key: str, status: str, check_id: str) -> None:
        """Record operational execution status to guard against unsafe retries."""
        with self._lock:
            self._operation_executions[op_key] = {
                "status": status,
                "check_id": check_id,
                "executed_at": datetime.now(timezone.utc),
            }

    def get_operation_execution(self, op_key: str) -> dict[str, Any] | None:
        """Retrieve operation execution status for idempotency check."""
        with self._lock:
            return self._operation_executions.get(op_key)

    def reset(self) -> None:
        """Reset repository state for clean test isolation."""
        with self._lock:
            self._checks.clear()
            self._decision_checks.clear()
            self._resource_checks.clear()
            self._patient_checks.clear()
            self._policies.clear()
            self._circuit_breakers.clear()
            self._operation_executions.clear()
            self._seed_default_policies()


# Global repository singleton
safety_repository = SafetyRepository()

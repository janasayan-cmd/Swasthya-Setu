"""Phase 51: Safety Governance Repository.

Thread-safe repository for clinical safety risks, assessments, acceptances,
mitigations, change requests, approvals, implementations, validations, and rollbacks.
Follows the database team boundary: does not create unmanaged tables or competing migrations.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.risk import RiskHistoryEntry, RiskRecord
from app.schemas.risk_assessment import RiskAssessmentRecord
from app.schemas.risk_mitigation import MitigationRecord
from app.schemas.safety_approval import (
    RiskAcceptanceRecord,
    SafetyChangeApprovalRecord,
)
from app.schemas.safety_change import SafetyChangeRecord
from app.schemas.safety_governance import (
    ChangeRequestState,
    RiskCategory,
    RiskState,
)
from app.schemas.safety_rollback import (
    SafetyChangeImplementationRecord,
    SafetyChangeRollbackRecord,
)
from app.schemas.safety_validation import SafetyChangeValidationRecord


class SafetyGovernanceRepository:
    """Thread-safe in-memory repository for Phase 51 safety governance entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._risks: Dict[str, RiskRecord] = {}
        self._risk_history: Dict[str, List[RiskHistoryEntry]] = {}  # risk_id -> entries
        self._assessments: Dict[str, RiskAssessmentRecord] = {}
        self._risk_assessments: Dict[str, List[str]] = {}  # risk_id -> assessment_ids
        self._acceptances: Dict[str, RiskAcceptanceRecord] = {}
        self._risk_acceptances: Dict[str, List[str]] = {}  # risk_id -> acceptance_ids
        self._mitigations: Dict[str, MitigationRecord] = {}
        self._risk_mitigations: Dict[str, List[str]] = {}  # risk_id -> mitigation_ids

        self._changes: Dict[str, SafetyChangeRecord] = {}
        self._risk_changes: Dict[str, List[str]] = {}  # risk_id -> change_ids
        self._approvals: Dict[str, SafetyChangeApprovalRecord] = {}
        self._change_approvals: Dict[str, List[str]] = {}  # change_id -> approval_ids
        self._implementations: Dict[str, SafetyChangeImplementationRecord] = {}
        self._change_implementations: Dict[str, List[str]] = {}  # change_id -> impl_ids
        self._validations: Dict[str, SafetyChangeValidationRecord] = {}
        self._change_validations: Dict[str, List[str]] = {}  # change_id -> val_ids
        self._rollbacks: Dict[str, SafetyChangeRollbackRecord] = {}
        self._change_rollbacks: Dict[str, List[str]] = {}  # change_id -> rollback_ids

        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> entity_id

    # --- Risk Methods ---
    def save_risk(self, risk: RiskRecord) -> RiskRecord:
        """Persist or update a clinical safety risk."""
        with self._lock:
            self._risks[risk.id] = risk
            return risk

    def get_risk(self, risk_id: str) -> Optional[RiskRecord]:
        """Retrieve a clinical safety risk by ID."""
        with self._lock:
            return self._risks.get(risk_id)

    def list_risks(
        self,
        organization_id: Optional[str] = None,
        category: Optional[RiskCategory] = None,
        state: Optional[RiskState] = None,
    ) -> List[RiskRecord]:
        """Filter and list clinical safety risks."""
        with self._lock:
            risks = list(self._risks.values())
            if organization_id:
                risks = [r for r in risks if r.organization_id == organization_id or r.organization_id is None]
            if category:
                risks = [r for r in risks if r.category == category]
            if state:
                risks = [r for r in risks if r.state == state]
            return risks

    def add_risk_history(self, entry: RiskHistoryEntry) -> RiskHistoryEntry:
        """Append an audit trail entry for risk state transition."""
        with self._lock:
            h_list = self._risk_history.setdefault(entry.risk_id, [])
            h_list.append(entry)
            return entry

    def list_risk_history(self, risk_id: str) -> List[RiskHistoryEntry]:
        """List all chronological history entries for a risk."""
        with self._lock:
            return list(self._risk_history.get(risk_id, []))

    # --- Assessment Methods ---
    def save_assessment(self, assessment: RiskAssessmentRecord) -> RiskAssessmentRecord:
        """Persist a structured risk assessment."""
        with self._lock:
            self._assessments[assessment.id] = assessment
            a_list = self._risk_assessments.setdefault(assessment.risk_id, [])
            if assessment.id not in a_list:
                a_list.append(assessment.id)
            return assessment

    def get_assessment(self, assessment_id: str) -> Optional[RiskAssessmentRecord]:
        """Retrieve assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def list_assessments(self, risk_id: str) -> List[RiskAssessmentRecord]:
        """List all assessments for a specific risk."""
        with self._lock:
            a_ids = self._risk_assessments.get(risk_id, [])
            return [self._assessments[aid] for aid in a_ids if aid in self._assessments]

    # --- Acceptance Methods ---
    def save_acceptance(self, acceptance: RiskAcceptanceRecord) -> RiskAcceptanceRecord:
        """Persist an explicit risk acceptance record."""
        with self._lock:
            self._acceptances[acceptance.id] = acceptance
            acc_list = self._risk_acceptances.setdefault(acceptance.risk_id, [])
            if acceptance.id not in acc_list:
                acc_list.append(acceptance.id)
            return acceptance

    def get_acceptance(self, acceptance_id: str) -> Optional[RiskAcceptanceRecord]:
        """Retrieve risk acceptance record by ID."""
        with self._lock:
            return self._acceptances.get(acceptance_id)

    def list_acceptances(self, risk_id: str) -> List[RiskAcceptanceRecord]:
        """List all risk acceptance records for a specific risk."""
        with self._lock:
            acc_ids = self._risk_acceptances.get(risk_id, [])
            return [self._acceptances[aid] for aid in acc_ids if aid in self._acceptances]

    # --- Mitigation Methods ---
    def save_mitigation(self, mitigation: MitigationRecord) -> MitigationRecord:
        """Persist a risk mitigation plan."""
        with self._lock:
            self._mitigations[mitigation.id] = mitigation
            m_list = self._risk_mitigations.setdefault(mitigation.risk_id, [])
            if mitigation.id not in m_list:
                m_list.append(mitigation.id)
            return mitigation

    def get_mitigation(self, mitigation_id: str) -> Optional[MitigationRecord]:
        """Retrieve mitigation plan by ID."""
        with self._lock:
            return self._mitigations.get(mitigation_id)

    def list_mitigations(self, risk_id: str) -> List[MitigationRecord]:
        """List all mitigations linked to a risk."""
        with self._lock:
            m_ids = self._risk_mitigations.get(risk_id, [])
            return [self._mitigations[mid] for mid in m_ids if mid in self._mitigations]

    # --- Safety Change Methods ---
    def save_change(self, change: SafetyChangeRecord) -> SafetyChangeRecord:
        """Persist or update a controlled safety change request."""
        with self._lock:
            self._changes[change.id] = change
            c_list = self._risk_changes.setdefault(change.risk_id, [])
            if change.id not in c_list:
                c_list.append(change.id)
            return change

    def get_change(self, change_id: str) -> Optional[SafetyChangeRecord]:
        """Retrieve safety change request by ID."""
        with self._lock:
            return self._changes.get(change_id)

    def list_changes(
        self,
        risk_id: Optional[str] = None,
        state: Optional[ChangeRequestState] = None,
        organization_id: Optional[str] = None,
    ) -> List[SafetyChangeRecord]:
        """Filter and list safety change requests."""
        with self._lock:
            changes = list(self._changes.values())
            if risk_id:
                changes = [c for c in changes if c.risk_id == risk_id]
            if state:
                changes = [c for c in changes if c.state == state]
            if organization_id:
                changes = [c for c in changes if c.organization_id == organization_id or c.organization_id is None]
            return changes

    # --- Approval Methods ---
    def save_approval(self, approval: SafetyChangeApprovalRecord) -> SafetyChangeApprovalRecord:
        """Persist an explicit safety change approval."""
        with self._lock:
            self._approvals[approval.id] = approval
            appr_list = self._change_approvals.setdefault(approval.change_id, [])
            if approval.id not in appr_list:
                appr_list.append(approval.id)
            return approval

    def get_approval(self, approval_id: str) -> Optional[SafetyChangeApprovalRecord]:
        """Retrieve approval record by ID."""
        with self._lock:
            return self._approvals.get(approval_id)

    def list_approvals(self, change_id: str) -> List[SafetyChangeApprovalRecord]:
        """List all approvals recorded for a safety change."""
        with self._lock:
            appr_ids = self._change_approvals.get(change_id, [])
            return [self._approvals[aid] for aid in appr_ids if aid in self._approvals]

    # --- Implementation Methods ---
    def save_implementation(self, impl: SafetyChangeImplementationRecord) -> SafetyChangeImplementationRecord:
        """Persist a safety change implementation execution record."""
        with self._lock:
            self._implementations[impl.id] = impl
            impl_list = self._change_implementations.setdefault(impl.change_id, [])
            if impl.id not in impl_list:
                impl_list.append(impl.id)
            return impl

    def get_implementation(self, impl_id: str) -> Optional[SafetyChangeImplementationRecord]:
        """Retrieve implementation record by ID."""
        with self._lock:
            return self._implementations.get(impl_id)

    def list_implementations(self, change_id: str) -> List[SafetyChangeImplementationRecord]:
        """List all implementations for a safety change."""
        with self._lock:
            i_ids = self._change_implementations.get(change_id, [])
            return [self._implementations[iid] for iid in i_ids if iid in self._implementations]

    # --- Validation Methods ---
    def save_validation(self, val: SafetyChangeValidationRecord) -> SafetyChangeValidationRecord:
        """Persist a safety change validation record."""
        with self._lock:
            self._validations[val.id] = val
            v_list = self._change_validations.setdefault(val.change_id, [])
            if val.id not in v_list:
                v_list.append(val.id)
            return val

    def get_validation(self, val_id: str) -> Optional[SafetyChangeValidationRecord]:
        """Retrieve validation record by ID."""
        with self._lock:
            return self._validations.get(val_id)

    def list_validations(self, change_id: str) -> List[SafetyChangeValidationRecord]:
        """List all validation records for a safety change."""
        with self._lock:
            v_ids = self._change_validations.get(change_id, [])
            return [self._validations[vid] for vid in v_ids if vid in self._validations]

    # --- Rollback Methods ---
    def save_rollback(self, rbk: SafetyChangeRollbackRecord) -> SafetyChangeRollbackRecord:
        """Persist a safety change rollback record."""
        with self._lock:
            self._rollbacks[rbk.id] = rbk
            r_list = self._change_rollbacks.setdefault(rbk.change_id, [])
            if rbk.id not in r_list:
                r_list.append(rbk.id)
            return rbk

    def get_rollback(self, rbk_id: str) -> Optional[SafetyChangeRollbackRecord]:
        """Retrieve rollback record by ID."""
        with self._lock:
            return self._rollbacks.get(rbk_id)

    def list_rollbacks(self, change_id: str) -> List[SafetyChangeRollbackRecord]:
        """List all rollback records for a safety change."""
        with self._lock:
            r_ids = self._change_rollbacks.get(change_id, [])
            return [self._rollbacks[rid] for rid in r_ids if rid in self._rollbacks]

    # --- Idempotency Methods ---
    def get_idempotent_result(self, key: str) -> Optional[str]:
        """Check if an idempotency key has already resolved to an entity ID."""
        with self._lock:
            return self._idempotency_map.get(key)

    def save_idempotent_result(self, key: str, entity_id: str) -> None:
        """Map idempotency key to entity ID."""
        with self._lock:
            self._idempotency_map[key] = entity_id

    # --- Reset Method for Clean Tests ---
    def reset(self) -> None:
        """Clear all in-memory entities for test isolation."""
        with self._lock:
            self._risks.clear()
            self._risk_history.clear()
            self._assessments.clear()
            self._risk_assessments.clear()
            self._acceptances.clear()
            self._risk_acceptances.clear()
            self._mitigations.clear()
            self._risk_mitigations.clear()
            self._changes.clear()
            self._risk_changes.clear()
            self._approvals.clear()
            self._change_approvals.clear()
            self._implementations.clear()
            self._change_implementations.clear()
            self._validations.clear()
            self._change_validations.clear()
            self._rollbacks.clear()
            self._change_rollbacks.clear()
            self._idempotency_map.clear()


# Global singleton repository
safety_governance_repository = SafetyGovernanceRepository()

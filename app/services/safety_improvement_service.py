"""Phase 56: Primary Safety Improvement Orchestration Service.

Orchestrates continuous improvement lifecycle:
- Feedback intake from Phase 55 effectiveness outcomes
- Signal classification & policy-driven response selection
- Controlled change proposal composition
- Multidimensional impact assessment
- Strict readiness gating
- Closed-loop routing into Phase 51 governance, Phase 52 assurance, and Phase 50 learning
- Recurrence & regression handling
- History and idempotency management
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.action_effectiveness_repository import (
    ActionEffectivenessRepository,
    get_action_effectiveness_repository,
)
from app.repositories.safety_action_repository import (
    SafetyActionRepository,
    get_safety_action_repository,
)
from app.repositories.safety_improvement_repository import (
    SafetyImprovementRepository,
    get_safety_improvement_repository,
)
from app.schemas.safety_improvement import (
    ClassifyImprovementRequest,
    CreateChangeProposalRequest,
    CreateImprovementRequest,
    EscalationTarget,
    ImpactAssessmentRecord,
    ImprovementEvidenceReference,
    ImprovementHistoryEntry,
    ImprovementLifecycleState,
    ImprovementPriority,
    ImprovementResponseType,
    ImprovementScope,
    ImprovementSignalType,
    ReadinessResponse,
    RequestImpactAssessmentRequest,
    SafetyImprovementRecord,
)
from app.services.safety_improvement_change_service import SafetyImprovementChangeService
from app.services.safety_improvement_classification_service import SafetyImprovementClassificationService
from app.services.safety_improvement_routing_service import SafetyImprovementRoutingService


class SafetyImprovementService:
    """Primary orchestration service for Phase 56 clinical safety improvements."""

    def __init__(
        self,
        repository: Optional[SafetyImprovementRepository] = None,
        eff_repository: Optional[ActionEffectivenessRepository] = None,
        act_repository: Optional[SafetyActionRepository] = None,
    ) -> None:
        self._repo = repository or get_safety_improvement_repository()
        self._eff_repo = eff_repository or get_action_effectiveness_repository()
        self._act_repo = act_repository or get_safety_action_repository()
        self._classification_service = SafetyImprovementClassificationService()
        self._change_service = SafetyImprovementChangeService()
        self._routing_service = SafetyImprovementRoutingService()

    def create_improvement(
        self,
        request: CreateImprovementRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Create continuous improvement record from a Phase 55 effectiveness evaluation."""
        # 1. Idempotency check
        if request.idempotency_key:
            payload_str = f"{request.source_evaluation_id}:{request.signal_type}:{request.response_type}"
            p_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            is_dup, existing_id = self._repo.check_idempotency(request.idempotency_key, p_hash)
            if is_dup:
                if existing_id:
                    rec = self._repo.get(existing_id)
                    if rec:
                        return rec
                raise AppException(
                    code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message="Conflicting idempotency key provided for safety improvement.",
                    status_code=409,
                )

        # 2. Resolve source effectiveness evaluation
        evaluation = self._eff_repo.get(request.source_evaluation_id)
        if not evaluation:
            raise AppException(
                code=ErrorCode.SOURCE_EVALUATION_INVALID,
                message=f"Referenced effectiveness evaluation '{request.source_evaluation_id}' not found.",
                status_code=404,
            )

        # 3. Scope resolution
        scope = request.scope or ImprovementScope(
            organization_id=evaluation.scope.organization_id,
            facility_id=evaluation.scope.facility_id,
            department_id=evaluation.scope.department_id,
            environment=evaluation.scope.environment,
        )

        # 4. Check recurrence across prior improvements for this action
        source_action_id = request.source_action_id or evaluation.action_id
        prior_improvements = [
            r for r in self._repo.list_improvements(organization_id=scope.organization_id)
            if r.source_action_id == source_action_id
        ]
        recurrence_count = len(prior_improvements)

        # 5. Classify signal & response
        if request.signal_type and request.response_type:
            signal_type = request.signal_type
            response_type = request.response_type
            priority = request.priority or ImprovementPriority.MEDIUM
            is_regression = (signal_type == ImprovementSignalType.CONTROL_REGRESSION)
            is_recurring = recurrence_count > 0 or (signal_type == ImprovementSignalType.RECURRING_FAILURE)
            self._classification_service.validate_classification_policy(signal_type, response_type)
        else:
            (
                signal_type,
                response_type,
                priority,
                is_regression,
                is_recurring,
            ) = self._classification_service.classify_from_evaluation(
                evaluation=evaluation,
                prior_recurrence_count=recurrence_count,
            )

        # 6. Build evidence references
        evidence_refs: List[ImprovementEvidenceReference] = [
            ImprovementEvidenceReference(
                evidence_id=e.evidence_id,
                source_phase=e.source_system,
                source_id=e.source_id,
                summary=f"Evidence type: {e.evidence_type}",
                timestamp=e.timestamp,
            )
            for e in evaluation.evidence_items
        ]

        improvement = SafetyImprovementRecord(
            improvement_id=f"imp-{uuid.uuid4().hex[:12]}",
            source_evaluation_id=request.source_evaluation_id,
            source_action_id=source_action_id,
            scope=scope,
            signal_type=signal_type,
            response_type=response_type,
            lifecycle_state=ImprovementLifecycleState.SIGNAL_IDENTIFIED,
            priority=priority,
            is_recurring=is_recurring,
            recurrence_count=recurrence_count,
            is_regression=is_regression,
            evidence_references=evidence_refs,
            created_by=actor_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Record history
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state="NONE",
                to_state=ImprovementLifecycleState.SIGNAL_IDENTIFIED.value,
                action="CREATE_IMPROVEMENT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Derived from evaluation {evaluation.evaluation_id} with state {evaluation.effectiveness_state.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        # General feedback routing
        self._routing_service.route_general_feedback(improvement)

        saved = self._repo.save(improvement)

        # Record idempotency
        if request.idempotency_key:
            payload_str = f"{request.source_evaluation_id}:{request.signal_type}:{request.response_type}"
            p_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            self._repo.record_idempotency(request.idempotency_key, p_hash, saved.improvement_id)

        return saved

    def get_improvement(self, improvement_id: str) -> SafetyImprovementRecord:
        """Fetch improvement record or raise 404."""
        record = self._repo.get(improvement_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_IMPROVEMENT_NOT_FOUND,
                message=f"Safety improvement '{improvement_id}' not found.",
                status_code=404,
            )
        return record

    def classify_improvement(
        self,
        improvement_id: str,
        request: ClassifyImprovementRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Reclassify improvement signal and response type with policy validation."""
        improvement = self.get_improvement(improvement_id)

        self._classification_service.validate_classification_policy(
            signal_type=request.signal_type,
            response_type=request.response_type,
        )

        old_signal = improvement.signal_type.value
        improvement.signal_type = request.signal_type
        improvement.response_type = request.response_type
        if request.priority:
            improvement.priority = request.priority

        improvement.lifecycle_state = ImprovementLifecycleState.CLASSIFIED
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_signal,
                to_state=request.signal_type.value,
                action="CLASSIFY",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.rationale,
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def create_change_proposal(
        self,
        improvement_id: str,
        request: CreateChangeProposalRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Attach a structured safety change proposal to an improvement opportunity."""
        improvement = self.get_improvement(improvement_id)

        proposal = self._change_service.create_change_proposal(
            improvement=improvement,
            change_category=request.change_category,
            problem_statement=request.problem_statement,
            proposed_solution=request.proposed_solution,
            expected_outcome=request.expected_outcome,
            rollback_plan=request.rollback_plan,
            validation_plan=request.validation_plan,
            observation_plan=request.observation_plan,
            success_criteria=request.success_criteria,
            dependencies=request.dependencies,
        )

        improvement.change_proposal = proposal
        improvement.lifecycle_state = ImprovementLifecycleState.CHANGE_PROPOSED
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=ImprovementLifecycleState.SIGNAL_IDENTIFIED.value,
                to_state=ImprovementLifecycleState.CHANGE_PROPOSED.value,
                action="PROPOSE_CHANGE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Formulated change proposal under category {request.change_category.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def request_impact_assessment(
        self,
        improvement_id: str,
        request: RequestImpactAssessmentRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Attach multidimensional impact assessment to the change proposal."""
        improvement = self.get_improvement(improvement_id)
        if not improvement.change_proposal:
            raise AppException(
                code=ErrorCode.CHANGE_NOT_READY,
                message="Cannot assess impact without an existing change proposal.",
                status_code=400,
            )

        self._change_service.record_impact_assessment(
            proposal=improvement.change_proposal,
            safety_impact=request.safety_impact,
            clinical_workflow_impact=request.clinical_workflow_impact,
            privacy_impact=request.privacy_impact,
            security_impact=request.security_impact,
            operational_impact=request.operational_impact,
            rollback_complexity=request.rollback_complexity,
            assessed_by=actor_id,
            affected_controls=request.affected_controls,
        )

        improvement.lifecycle_state = ImprovementLifecycleState.IMPACT_ASSESSED
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=ImprovementLifecycleState.CHANGE_PROPOSED.value,
                to_state=ImprovementLifecycleState.IMPACT_ASSESSED.value,
                action="ASSESS_IMPACT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Completed multidimensional impact assessment.",
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def check_readiness(self, improvement_id: str) -> ReadinessResponse:
        """Evaluate readiness gates for change proposal."""
        improvement = self.get_improvement(improvement_id)
        readiness = self._change_service.evaluate_readiness(improvement)
        if readiness.is_ready and improvement.lifecycle_state != ImprovementLifecycleState.CHANGE_READY:
            improvement.lifecycle_state = ImprovementLifecycleState.CHANGE_READY
            self._repo.save(improvement)
        return readiness

    def route_to_governance(
        self,
        improvement_id: str,
        rationale: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Verify readiness and dispatch change proposal to Phase 51 governance."""
        improvement = self.get_improvement(improvement_id)
        readiness = self.check_readiness(improvement_id)

        if not readiness.is_ready:
            raise AppException(
                code=ErrorCode.CHANGE_NOT_READY,
                message=f"Change proposal is not ready for governance submission: {', '.join(readiness.blockers)}",
                status_code=400,
            )

        # Dispatch
        self._routing_service.route_to_phase51_governance(improvement)
        if improvement.change_proposal:
            improvement.change_proposal.phase51_change_request_id = f"chg-{uuid.uuid4().hex[:8]}"

        old_state = improvement.lifecycle_state.value
        improvement.lifecycle_state = ImprovementLifecycleState.GOVERNANCE_ROUTED
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_state,
                to_state=ImprovementLifecycleState.GOVERNANCE_ROUTED.value,
                action="ROUTE_TO_GOVERNANCE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=rationale,
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def reassess_improvement(
        self,
        improvement_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Trigger formal reassessment of improvement opportunity."""
        improvement = self.get_improvement(improvement_id)
        old_state = improvement.lifecycle_state.value
        improvement.lifecycle_state = ImprovementLifecycleState.ANALYZING
        improvement.response_type = ImprovementResponseType.REASSESS
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_state,
                to_state=ImprovementLifecycleState.ANALYZING.value,
                action="REASSESS",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def escalate_improvement(
        self,
        improvement_id: str,
        target: EscalationTarget,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Escalate improvement opportunity to a specialized governance body."""
        improvement = self.get_improvement(improvement_id)
        old_state = improvement.lifecycle_state.value
        improvement.lifecycle_state = ImprovementLifecycleState.ESCALATED
        improvement.priority = ImprovementPriority.CRITICAL if improvement.priority == ImprovementPriority.HIGH else ImprovementPriority.HIGH
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_state,
                to_state=ImprovementLifecycleState.ESCALATED.value,
                action="ESCALATE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Escalated to {target.value}: {reason}",
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def reopen_improvement(
        self,
        improvement_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Reopen a closed or deferred improvement opportunity."""
        improvement = self.get_improvement(improvement_id)
        old_state = improvement.lifecycle_state.value
        improvement.lifecycle_state = ImprovementLifecycleState.REOPENED
        improvement.reopened_count += 1
        improvement.closed_at = None
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_state,
                to_state=ImprovementLifecycleState.REOPENED.value,
                action="REOPEN",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def close_improvement(
        self,
        improvement_id: str,
        rationale: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyImprovementRecord:
        """Formally close an improvement opportunity."""
        improvement = self.get_improvement(improvement_id)
        if improvement.lifecycle_state == ImprovementLifecycleState.CLOSED:
            raise AppException(
                code=ErrorCode.ALREADY_CLOSED,
                message="Improvement record is already closed.",
                status_code=400,
            )

        old_state = improvement.lifecycle_state.value
        improvement.lifecycle_state = ImprovementLifecycleState.CLOSED
        improvement.closed_at = datetime.now(timezone.utc)
        improvement.history.append(
            ImprovementHistoryEntry(
                entry_id=f"his-{uuid.uuid4().hex[:8]}",
                from_state=old_state,
                to_state=ImprovementLifecycleState.CLOSED.value,
                action="CLOSE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=rationale,
                timestamp=datetime.now(timezone.utc),
            )
        )
        improvement.version += 1
        return self._repo.save(improvement)

    def list_improvements(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[ImprovementLifecycleState] = None,
        priority: Optional[ImprovementPriority] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyImprovementRecord]:
        return self._repo.list_improvements(
            organization_id=organization_id,
            facility_id=facility_id,
            lifecycle_state=lifecycle_state,
            priority=priority,
            limit=limit,
            offset=offset,
        )

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        return self._repo.list_pending(organization_id)

    def list_high_priority(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        return self._repo.list_high_priority(organization_id)

    def list_regressions(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        return self._repo.list_regressions(organization_id)

    def list_recurring(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        return self._repo.list_recurring(organization_id)

    def list_change_candidates(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        return self._repo.list_change_candidates(organization_id)

    def reanalysis(self, improvement_ids: Optional[List[str]], reason: str) -> Dict[str, Any]:
        """Batch reanalysis of improvement opportunities."""
        if not reason or len(reason.strip()) < 10:
            raise AppException(
                code=ErrorCode.CRITERIA_MISSING,
                message="Reanalysis reason must be at least 10 characters.",
                status_code=400,
            )

        items_to_reanalyze = []
        if improvement_ids:
            for iid in improvement_ids:
                try:
                    items_to_reanalyze.append(self.get_improvement(iid))
                except AppException:
                    pass
        else:
            items_to_reanalyze = self._repo.list_improvements(limit=50)

        processed = 0
        for item in items_to_reanalyze:
            self.check_readiness(item.improvement_id)
            processed += 1

        return {
            "processed_count": processed,
            "reason": reason,
            "status": "COMPLETED",
        }


# Global singleton instance
_service_instance: Optional[SafetyImprovementService] = None


def get_safety_improvement_service() -> SafetyImprovementService:
    """Retrieve global singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SafetyImprovementService()
    return _service_instance

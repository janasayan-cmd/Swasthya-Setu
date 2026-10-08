"""Phase 62: Safety Risk Assessment Service Orchestrator.

Main orchestrator coordinating finding consolidation, cross-domain correlation,
evidence reconciliation, risk characterization, readiness evaluation, human review,
and authoritative routing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_risk_assessment_repository import (
    SafetyRiskAssessmentRepository,
    get_safety_risk_assessment_repository,
)
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    AssessmentReadinessState,
    ConsolidatedRiskContext,
    CreateRiskAssessmentRequest,
    EvidenceReconciliationState,
    HumanRiskReviewDecision,
    RiskAssessmentHistoryEntry,
    RiskAssessmentScope,
    RiskPriority,
    RiskRoutingDestination,
    RiskUncertaintyState,
    SafetyRiskAssessmentRecord,
)
from app.services.safety_cross_domain_correlation_service import (
    SafetyCrossDomainCorrelationService,
    get_safety_cross_domain_correlation_service,
)
from app.services.safety_evidence_reconciliation_service import (
    SafetyEvidenceReconciliationService,
    get_safety_evidence_reconciliation_service,
)
from app.services.safety_finding_consolidation_service import (
    SafetyFindingConsolidationService,
    get_safety_finding_consolidation_service,
)
from app.services.safety_risk_characterization_service import (
    SafetyRiskCharacterizationService,
    get_safety_risk_characterization_service,
)
from app.services.safety_risk_input_service import (
    SafetyRiskInputService,
    get_safety_risk_input_service,
)
from app.services.safety_risk_review_service import (
    SafetyRiskReviewService,
    get_safety_risk_review_service,
)
from app.services.safety_risk_routing_service import (
    SafetyRiskRoutingService,
    get_safety_risk_routing_service,
)


class SafetyRiskAssessmentService:
    """End-to-end coordinator for Phase 62 cross-domain safety risk assessment."""

    def __init__(
        self,
        repository: Optional[SafetyRiskAssessmentRepository] = None,
        input_service: Optional[SafetyRiskInputService] = None,
        consolidation_service: Optional[SafetyFindingConsolidationService] = None,
        correlation_service: Optional[SafetyCrossDomainCorrelationService] = None,
        reconciliation_service: Optional[SafetyEvidenceReconciliationService] = None,
        characterization_service: Optional[SafetyRiskCharacterizationService] = None,
        review_service: Optional[SafetyRiskReviewService] = None,
        routing_service: Optional[SafetyRiskRoutingService] = None,
    ) -> None:
        self.repo = repository or get_safety_risk_assessment_repository()
        self.input_svc = input_service or get_safety_risk_input_service()
        self.consolidation_svc = consolidation_service or get_safety_finding_consolidation_service()
        self.correlation_svc = correlation_service or get_safety_cross_domain_correlation_service()
        self.reconciliation_svc = reconciliation_service or get_safety_evidence_reconciliation_service()
        self.characterization_svc = characterization_service or get_safety_risk_characterization_service()
        self.review_svc = review_service or get_safety_risk_review_service()
        self.routing_svc = routing_service or get_safety_risk_routing_service()

    def create_assessment(
        self,
        request: CreateRiskAssessmentRequest,
        organization_id: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyRiskAssessmentRecord:
        """Create and initialize a new risk assessment context."""
        # 1. Idempotency Check
        if request.idempotency_key:
            existing = self.repo.check_idempotency(request.idempotency_key, organization_id)
            if existing:
                return existing

        scope = request.scope or RiskAssessmentScope(organization_id=organization_id)
        if scope.organization_id != organization_id:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Cannot create risk assessment for another organization scope",
                status_code=403,
            )

        asmt_id = request.assessment_id or f"sra-{uuid.uuid4().hex[:10]}"

        # Validate input findings
        raw_findings = request.findings or []
        eligible, excluded = self.input_svc.filter_and_validate_findings(
            raw_findings=raw_findings, scope=scope
        )

        record = SafetyRiskAssessmentRecord(
            assessment_id=asmt_id,
            organization_id=organization_id,
            scope=scope,
            lifecycle_state=AssessmentLifecycleState.RECEIVED,
            readiness_state=AssessmentReadinessState.ASSESSMENT_NOT_READY,
            source_findings=eligible,
            excluded_findings=excluded,
            idempotency_key=request.idempotency_key,
            version=request.version,
        )

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="ASSESSMENT_CREATED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AssessmentLifecycleState.RECEIVED.value,
                details={"purpose": request.purpose, "initial_findings": len(raw_findings)},
            )
        )

        return self.repo.save(record)

    def consolidate(
        self,
        assessment_id: str,
        actor_id: str,
        actor_role: str,
        concern_summary: Optional[str] = None,
    ) -> SafetyRiskAssessmentRecord:
        """Consolidate eligible findings into unified risk context and cross-domain correlations."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        findings = record.source_findings
        if not findings:
            record.readiness_state = AssessmentReadinessState.ASSESSMENT_BLOCKED
            self.repo.save(record)
            raise AppException(
                code=ErrorCode.CONSOLIDATION_FAILED,
                message="No eligible source findings available for consolidation",
                status_code=400,
            )

        # 1. Consolidate Context
        record.risk_context = self.consolidation_svc.consolidate_findings(
            findings=findings, scope=record.scope, concern_summary=concern_summary
        )

        # 2. Correlate across operational domains
        record.correlations = self.correlation_svc.evaluate_correlations(findings=findings)

        # 3. Baseline reconciliation
        evidence_items, rec_state, has_conflicts = self.reconciliation_svc.reconcile_evidence(
            findings=findings
        )
        record.evidence_items = evidence_items
        record.has_unresolved_conflicts = has_conflicts
        record.risk_context.reconciliation_state = rec_state

        record.lifecycle_state = AssessmentLifecycleState.CONSOLIDATED
        record.readiness_state = (
            AssessmentReadinessState.CONFLICT_REQUIRES_REVIEW
            if has_conflicts
            else AssessmentReadinessState.ASSESSMENT_READY
        )

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="FINDINGS_CONSOLIDATED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AssessmentLifecycleState.CONSOLIDATED.value,
                details={
                    "consolidated_count": len(findings),
                    "correlations_count": len(record.correlations),
                },
            )
        )

        return self.repo.save(record)

    def reconcile_evidence(
        self,
        assessment_id: str,
        actor_id: str,
        actor_role: str,
        external_evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> SafetyRiskAssessmentRecord:
        """Reconcile internal surveillance findings with external evidence sources."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        evidence_items, rec_state, has_conflicts = self.reconciliation_svc.reconcile_evidence(
            findings=record.source_findings, external_evidence=external_evidence
        )
        record.evidence_items = evidence_items
        record.has_unresolved_conflicts = has_conflicts

        if record.risk_context:
            record.risk_context.reconciliation_state = rec_state

        if has_conflicts:
            record.lifecycle_state = AssessmentLifecycleState.CONFLICTED
            record.readiness_state = AssessmentReadinessState.CONFLICT_REQUIRES_REVIEW
            record.overall_uncertainty = RiskUncertaintyState.CONFLICTED_EVIDENCE
            record.requires_human_review = True
        else:
            record.readiness_state = AssessmentReadinessState.ASSESSMENT_READY

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="EVIDENCE_RECONCILED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=record.lifecycle_state.value,
                details={
                    "evidence_items_count": len(evidence_items),
                    "has_conflicts": has_conflicts,
                },
            )
        )

        return self.repo.save(record)

    def assess_risk(
        self,
        assessment_id: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyRiskAssessmentRecord:
        """Execute governed risk characterization and uncertainty quantification."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        if not record.risk_context:
            # Auto-consolidate if not yet explicitly called
            self.consolidate(assessment_id=assessment_id, actor_id=actor_id, actor_role=actor_role)
            record = self.repo.get(assessment_id)
            if not record or not record.risk_context:
                raise AppException(
                    code=ErrorCode.ASSESSMENT_NOT_READY,
                    message="Cannot assess risk without consolidated risk context",
                    status_code=400,
                )

        # 1. Risk Characterization
        char = self.characterization_svc.characterize_risk(
            context=record.risk_context,
            findings=record.source_findings,
            correlations=record.correlations,
            has_conflicts=record.has_unresolved_conflicts,
        )
        record.characterization = char

        # 2. Uncertainty Evaluation
        if len(record.source_findings) == 0:
            record.overall_uncertainty = RiskUncertaintyState.INSUFFICIENT_DATA
        elif record.has_unresolved_conflicts:
            record.overall_uncertainty = RiskUncertaintyState.CONFLICTED_EVIDENCE
        elif len(record.source_findings) < 3:
            record.overall_uncertainty = RiskUncertaintyState.MODERATE_UNCERTAINTY
        else:
            record.overall_uncertainty = RiskUncertaintyState.LOW_UNCERTAINTY

        # 3. Governance Review & Escalation Flags
        is_critical = char.priority == RiskPriority.CRITICAL_ESCALATION
        is_urgent = char.priority in (
            RiskPriority.URGENT_GOVERNANCE_REVIEW,
            RiskPriority.HIGH_PRIORITY_REVIEW,
        )

        record.requires_escalation = is_critical
        record.requires_human_review = is_critical or is_urgent or record.has_unresolved_conflicts

        if is_critical:
            record.lifecycle_state = AssessmentLifecycleState.ESCALATION_REQUIRED
        elif record.requires_human_review:
            record.lifecycle_state = AssessmentLifecycleState.REVIEW_REQUIRED
        else:
            record.lifecycle_state = AssessmentLifecycleState.ASSESSMENT_READY

        record.completed_at = datetime.now(timezone.utc)

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="RISK_CHARACTERIZED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=record.lifecycle_state.value,
                details={
                    "priority": char.priority.value,
                    "severity": char.system_severity,
                    "uncertainty": record.overall_uncertainty.value,
                },
            )
        )

        return self.repo.save(record)

    def submit_review(
        self,
        assessment_id: str,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanRiskReviewDecision,
        reason: str,
        resulting_routes: Optional[List[RiskRoutingDestination]] = None,
        is_ai: bool = False,
    ) -> SafetyRiskAssessmentRecord:
        """Submit human review decision on a risk assessment."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        review_rec = self.review_svc.submit_review(
            assessment=record,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            reason=reason,
            resulting_routes=resulting_routes,
            is_ai=is_ai,
        )

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="REVIEW_SUBMITTED",
                actor_id=reviewer_id,
                actor_role=reviewer_role,
                new_state=record.lifecycle_state.value,
                details={"decision": decision.value, "review_id": review_rec.review_id},
            )
        )

        return self.repo.save(record)

    def route_assessment(
        self,
        assessment_id: str,
        destinations: List[RiskRoutingDestination],
        actor_id: str,
        actor_role: str,
        reason: str,
        target_reference: Optional[str] = None,
    ) -> SafetyRiskAssessmentRecord:
        """Route consolidated assessment findings to downstream authoritative phases."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        routing_recs = self.routing_svc.execute_routing(
            assessment=record,
            destinations=destinations,
            actor_id=actor_id,
            reason=reason,
            target_reference=target_reference,
        )

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="ASSESSMENT_ROUTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=record.lifecycle_state.value,
                details={
                    "destinations": [d.value for d in destinations],
                    "count": len(routing_recs),
                },
            )
        )

        return self.repo.save(record)

    def request_reassessment(
        self,
        assessment_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        signal_ids: Optional[List[str]] = None,
    ) -> SafetyRiskAssessmentRecord:
        """Request Phase 60 signal reassessment for contributing findings."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        record.lifecycle_state = AssessmentLifecycleState.REASSESSMENT_REQUIRED
        record.requires_reassessment = True

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="REASSESSMENT_REQUESTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AssessmentLifecycleState.REASSESSMENT_REQUIRED.value,
                details={"reason": reason, "signal_ids": signal_ids or []},
            )
        )

        return self.repo.save(record)

    def request_reanalysis(
        self,
        assessment_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        finding_ids: Optional[List[str]] = None,
    ) -> SafetyRiskAssessmentRecord:
        """Request Phase 61 longitudinal reanalysis for contributing findings."""
        record = self.repo.get(assessment_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
                message=f"Risk assessment {assessment_id} not found",
                status_code=404,
            )

        record.lifecycle_state = AssessmentLifecycleState.STALE

        record.history.append(
            RiskAssessmentHistoryEntry(
                action="REANALYSIS_REQUESTED",
                actor_id=actor_id,
                actor_role=actor_role,
                new_state=AssessmentLifecycleState.STALE.value,
                details={"reason": reason, "finding_ids": finding_ids or []},
            )
        )

        return self.repo.save(record)


_safety_risk_assessment_service: Optional[SafetyRiskAssessmentService] = None


def get_safety_risk_assessment_service() -> SafetyRiskAssessmentService:
    global _safety_risk_assessment_service
    if _safety_risk_assessment_service is None:
        _safety_risk_assessment_service = SafetyRiskAssessmentService()
    return _safety_risk_assessment_service

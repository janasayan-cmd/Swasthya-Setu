"""Phase 51: Structured Clinical Risk Assessment Service.

Enforces structured risk assessment, evaluates existing barriers and control effectiveness,
distinguishes initial vs residual risk (INITIAL RISK -> CONTROL -> RESIDUAL RISK),
and guarantees that risk severity is never derived solely from AI scores or HTTP codes.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import time

from app.core.exceptions import (
    RiskAlreadyClosedException,
    RiskAssessmentInvalidException,
    RiskNotFoundException,
    RiskVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import RiskHistoryEntry, RiskRecord
from app.schemas.risk_assessment import (
    RiskAssessmentCreateRequest,
    RiskAssessmentRecord,
)
from app.schemas.safety_governance import (
    RiskSeverity,
    RiskState,
)
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.risk_assessment_service")


class RiskAssessmentService:
    """Service governing explicit clinical risk assessments and residual risk reductions."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        audit_svc: Optional[AuditService] = None,
        metrics_svc: Optional[SafetyGovernanceMetricsService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.audit_service = audit_svc or audit_service
        self.metrics_service = metrics_svc or safety_governance_metrics_service

    async def assess_risk(
        self,
        risk_id: str,
        request: RiskAssessmentCreateRequest,
        assessor_id: str,
        assessor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskAssessmentRecord:
        """Conduct an authorized risk assessment and compute residual risk."""
        start_time = time.time()

        # 1. Human Authority validation (AI cannot autonomously complete risk assessments)
        self.policy_service.assert_human_safety_authority(assessor_id, assessor_role, "assess_risk")

        # 2. Retrieve risk & validate org boundaries
        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        if risk.is_closed:
            raise RiskAlreadyClosedException(
                f"Cannot assess closed risk '{risk_id}'. Reopening required before assessment."
            )

        if request.expected_version is not None and risk.version != request.expected_version:
            raise RiskVersionConflictException(
                f"Version conflict on risk assessment: expected {request.expected_version}, current {risk.version}."
            )

        # 3. Validation: Enforce that residual severity and initial severity are explicit
        if not request.severity or not request.residual_severity:
            raise RiskAssessmentInvalidException("Both initial severity and residual severity are required.")

        # 4. Check existing assessments count to establish assessment version
        existing_assessments = self.repository.list_assessments(risk_id)
        assessment_version = len(existing_assessments) + 1

        now = datetime.now(timezone.utc)
        assessment = RiskAssessmentRecord(
            risk_id=risk_id,
            assessment_version=assessment_version,
            category=request.category,
            severity=request.severity,
            likelihood=request.likelihood,
            impact=request.impact,
            residual_severity=request.residual_severity,
            residual_likelihood=request.residual_likelihood,
            residual_impact=request.residual_impact,
            affected_system=request.affected_system,
            affected_workflow=request.affected_workflow,
            affected_provider=request.affected_provider,
            affected_configuration=request.affected_configuration,
            affected_scope=request.affected_scope,
            evidence=request.evidence,
            existing_controls=request.existing_controls,
            mitigation_recommendation=request.mitigation_recommendation,
            limitations=request.limitations or [
                "Residual risk reflects reduction by controls, not absolute elimination.",
                "Subject to periodic reassessment upon new incident findings.",
            ],
            assessor_id=assessor_id,
            assessor_role=assessor_role,
            assessed_at=now,
            assessment_notes=request.assessment_notes,
            ai_metadata=request.ai_metadata,
        )

        persisted_assessment = self.repository.save_assessment(assessment)

        # 5. Update Risk Record with residual risk and transition state
        previous_state = risk.state
        risk.latest_assessment_id = persisted_assessment.id
        risk.residual_severity = request.residual_severity
        risk.residual_likelihood = request.residual_likelihood
        risk.residual_impact = request.residual_impact

        # Determine next lifecycle state based on policy
        if request.residual_severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL):
            next_state = RiskState.MITIGATION_REQUIRED
        else:
            next_state = RiskState.ASSESSED

        risk.state = next_state
        risk.version += 1
        risk.updated_at = now
        self.repository.save_risk(risk)

        # 6. Append History Entry
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=next_state,
                action="RISK_ASSESSED",
                actor_id=assessor_id,
                actor_role=assessor_role,
                reason="Structured clinical risk assessment completed",
                details={
                    "assessment_id": persisted_assessment.id,
                    "initial_severity": request.severity.value,
                    "residual_severity": request.residual_severity.value,
                    "controls_evaluated_count": len(request.existing_controls),
                },
            )
        )

        # 7. Metrics & Audit
        duration = time.time() - start_time
        self.metrics_service.increment("risk_assessed_count")
        self.metrics_service.record_latency("assessment_duration_seconds", duration)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_ASSESSED,
                    outcome="ALLOW",
                    actor_id=assessor_id,
                    action="safety_governance:risk:assess",
                    resource_type="risk_assessment",
                    resource_id=persisted_assessment.id,
                    metadata={
                        "risk_id": risk_id,
                        "residual_severity": request.residual_severity.value,
                        "residual_likelihood": request.residual_likelihood.value,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk assessment: %s", ex)

        return persisted_assessment

    def get_assessment(self, assessment_id: str) -> Optional[RiskAssessmentRecord]:
        """Retrieve assessment by ID."""
        return self.repository.get_assessment(assessment_id)

    def list_assessments(self, risk_id: str) -> List[RiskAssessmentRecord]:
        """List all assessments recorded for a specific risk."""
        return self.repository.list_assessments(risk_id)


# Global singleton risk assessment service
risk_assessment_service = RiskAssessmentService()

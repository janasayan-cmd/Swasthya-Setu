"""Phase 56: Safety Improvement Change Proposal & Readiness Service.

Governs change proposal composition, dependency tracking, impact assessment, and readiness checks.
Enforces:
- CHANGE PROPOSAL != CHANGE APPROVAL
- Readiness requires: Opportunity Valid + Evidence Sufficient + Scope Valid + Impact Assessed +
  Dependencies Satisfied + Rollback Defined + Validation Defined + Observation Defined.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_improvement import (
    ChangeDependency,
    ChangeProposalRecord,
    ImpactAssessmentRecord,
    ReadinessResponse,
    SafetyChangeCategory,
    SafetyImprovementRecord,
)


class SafetyImprovementChangeService:
    """Service for formulating and validating governed safety change proposals."""

    def create_change_proposal(
        self,
        improvement: SafetyImprovementRecord,
        change_category: SafetyChangeCategory,
        problem_statement: str,
        proposed_solution: str,
        expected_outcome: str,
        rollback_plan: str,
        validation_plan: str,
        observation_plan: str,
        success_criteria: Optional[List[str]] = None,
        dependencies: Optional[List[ChangeDependency]] = None,
    ) -> ChangeProposalRecord:
        """Formulate a structured change proposal."""
        if not problem_statement or len(problem_statement.strip()) < 10:
            raise AppException(
                code=ErrorCode.CHANGE_NOT_READY,
                message="Problem statement must be at least 10 characters.",
                status_code=400,
            )

        if not rollback_plan or len(rollback_plan.strip()) < 10:
            raise AppException(
                code=ErrorCode.CHANGE_NOT_READY,
                message="Rollback plan must be at least 10 characters.",
                status_code=400,
            )

        proposal = ChangeProposalRecord(
            proposal_id=f"prp-{uuid.uuid4().hex[:8]}",
            improvement_id=improvement.improvement_id,
            change_category=change_category,
            problem_statement=problem_statement.strip(),
            proposed_solution=proposed_solution.strip(),
            expected_outcome=expected_outcome.strip(),
            success_criteria=success_criteria or ["Verified zero regression on target control."],
            rollback_plan=rollback_plan.strip(),
            validation_plan=validation_plan.strip(),
            observation_plan=observation_plan.strip(),
            dependencies=dependencies or [],
            is_ready=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return proposal

    def record_impact_assessment(
        self,
        proposal: ChangeProposalRecord,
        safety_impact: str,
        clinical_workflow_impact: str,
        privacy_impact: str,
        security_impact: str,
        operational_impact: str,
        rollback_complexity: str,
        assessed_by: str,
        affected_controls: Optional[List[str]] = None,
    ) -> ImpactAssessmentRecord:
        """Attach multidimensional impact assessment to proposal."""
        assessment = ImpactAssessmentRecord(
            assessment_id=f"imp-{uuid.uuid4().hex[:8]}",
            safety_impact=safety_impact.strip(),
            clinical_workflow_impact=clinical_workflow_impact.strip(),
            privacy_impact=privacy_impact.strip(),
            security_impact=security_impact.strip(),
            operational_impact=operational_impact.strip(),
            rollback_complexity=rollback_complexity.strip(),
            affected_controls=affected_controls or [],
            assessed_by=assessed_by,
            assessed_at=datetime.now(timezone.utc),
            status="COMPLETED",
        )
        proposal.impact_assessment = assessment
        proposal.updated_at = datetime.now(timezone.utc)
        return assessment

    def evaluate_readiness(
        self,
        improvement: SafetyImprovementRecord,
    ) -> ReadinessResponse:
        """Evaluate full readiness gate for governance dispatch."""
        blockers: List[str] = []
        proposal = improvement.change_proposal

        opp_valid = bool(improvement.improvement_id and improvement.scope.organization_id)
        if not opp_valid:
            blockers.append("Improvement record is invalid or unassociated with an organization.")

        evi_suff = bool(improvement.evidence_references)
        if not evi_suff:
            blockers.append("No evidence references linked to substantiate improvement opportunity.")

        scope_valid = bool(improvement.scope.environment)
        if not scope_valid:
            blockers.append("Scope environment is unspecified.")

        impact_assessed = bool(proposal and proposal.impact_assessment is not None)
        if not impact_assessed:
            blockers.append("Multidimensional impact assessment has not been conducted.")

        deps_valid = True
        if proposal and proposal.dependencies:
            for d in proposal.dependencies:
                if not d.is_satisfied:
                    deps_valid = False
                    blockers.append(f"Unsatisfied dependency: {d.dependency_type} '{d.target_name}' (requires {d.required_version})")

        rollback_def = bool(proposal and proposal.rollback_plan and len(proposal.rollback_plan) >= 10)
        if not rollback_def:
            blockers.append("Rollback plan is missing or insufficient.")

        val_def = bool(proposal and proposal.validation_plan and len(proposal.validation_plan) >= 10)
        if not val_def:
            blockers.append("Post-implementation validation plan is missing.")

        obs_def = bool(proposal and proposal.observation_plan and len(proposal.observation_plan) >= 10)
        if not obs_def:
            blockers.append("Post-implementation observation plan is missing.")

        is_ready = (
            opp_valid
            and evi_suff
            and scope_valid
            and impact_assessed
            and deps_valid
            and rollback_def
            and val_def
            and obs_def
        )

        if proposal:
            proposal.is_ready = is_ready

        return ReadinessResponse(
            improvement_id=improvement.improvement_id,
            is_ready=is_ready,
            opportunity_valid=opp_valid,
            evidence_sufficient=evi_suff,
            scope_valid=scope_valid,
            impact_assessed=impact_assessed,
            dependencies_valid=deps_valid,
            rollback_defined=rollback_def,
            validation_defined=val_def,
            observation_defined=obs_def,
            blockers=blockers,
        )

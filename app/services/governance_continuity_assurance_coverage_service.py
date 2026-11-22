"""Phase 81: Continuity Capability Coverage Assurance Service.

Evaluates coverage of critical governance capabilities against approved
continuity arrangements, identifying uncovered, expired, unapproved, or untested areas.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    governance_continuity_repository,
)
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_plan import ContinuityPlanStatus
from app.schemas.governance_continuity_assurance_coverage import (
    CapabilityCoverageSummary,
    ContinuityCoverageAssessmentRecord,
    CoverageGapType,
    RunCoverageAssessmentRequest,
)


class GovernanceContinuityAssuranceCoverageService:
    """Domain service for assessing continuity coverage of critical governance capabilities."""

    def __init__(self, repo=None, phase80_repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository
        self.phase80_repo = phase80_repo or governance_continuity_repository

    def run_coverage_assessment(
        self,
        req: RunCoverageAssessmentRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityCoverageAssessmentRecord:
        assessment_id = f"CCA-{uuid.uuid4().hex[:8].upper()}"

        all_caps = self.phase80_repo.list_capabilities(tenant_id=tenant_id)
        all_plans = self.phase80_repo.list_plans(tenant_id=tenant_id)
        all_requirements = self.phase80_repo.list_requirements(tenant_id=tenant_id)

        # Map capabilities to plans (supporting both covered_capability_ids and primary_capability_id)
        plan_map = {}
        for p in all_plans:
            covered_ids = getattr(p, "covered_capability_ids", []) or []
            prim_id = getattr(p, "primary_capability_id", None)
            if prim_id:
                plan_map[prim_id] = p
            for cid in covered_ids:
                plan_map[cid] = p

        req_map = {r.capability_id: r for r in all_requirements}

        summaries: List[CapabilityCoverageSummary] = []
        detected_gaps: List[dict] = []
        covered_count = 0

        for cap in all_caps:
            gaps: List[CoverageGapType] = []
            matched_plan = plan_map.get(cap.capability_id)
            has_active_plan = False

            if not matched_plan:
                gaps.append(CoverageGapType.UNCOVERED_CAPABILITY)
                detected_gaps.append({
                    "capability_id": cap.capability_id,
                    "gap_type": CoverageGapType.UNCOVERED_CAPABILITY.value,
                    "reason": "No continuity plan mapped to capability",
                })
            else:
                if matched_plan.status != ContinuityPlanStatus.APPROVED:
                    gaps.append(CoverageGapType.UNAPPROVED_PLAN)
                    detected_gaps.append({
                        "capability_id": cap.capability_id,
                        "plan_id": matched_plan.plan_id,
                        "gap_type": CoverageGapType.UNAPPROVED_PLAN.value,
                        "reason": f"Plan status is {matched_plan.status}",
                    })
                else:
                    has_active_plan = True
                    covered_count += 1

            matched_req = req_map.get(cap.capability_id)
            has_recovery_targets = bool(matched_req and (getattr(matched_req, "rto_minutes", None) is not None))
            if not has_recovery_targets:
                gaps.append(CoverageGapType.INCOMPLETE_RECOVERY_REQUIREMENTS)

            cap_name = getattr(cap, "name", None) or getattr(cap, "capability_name", cap.capability_id)
            crit_tier = getattr(cap, "criticality", None) or getattr(cap, "criticality_tier", "TIER_1_CRITICAL")
            crit_val = crit_tier.value if hasattr(crit_tier, "value") else str(crit_tier)

            summaries.append(
                CapabilityCoverageSummary(
                    capability_id=cap.capability_id,
                    capability_name=cap_name,
                    criticality_tier=crit_val,
                    has_active_plan=has_active_plan,
                    plan_id=matched_plan.plan_id if matched_plan else None,
                    plan_version=getattr(matched_plan, "version", 1) if matched_plan else None,
                    identified_gaps=gaps,
                    recovery_targets_defined=has_recovery_targets,
                )
            )

        total_caps = len(all_caps)
        coverage_pct = (covered_count / total_caps * 100.0) if total_caps > 0 else 0.0

        record = ContinuityCoverageAssessmentRecord(
            assessment_id=assessment_id,
            scope_level=req.scope_level,
            scope_id=req.scope_id,
            assessed_at=datetime.utcnow(),
            assessed_by=actor_id,
            total_critical_capabilities=total_caps,
            covered_capabilities_count=covered_count,
            uncovered_capabilities_count=total_caps - covered_count,
            coverage_percentage=round(coverage_pct, 2),
            summaries=summaries,
            detected_gaps=detected_gaps,
            limitations="Coverage evaluation depends on freshness of Phase 80 capability inventory records.",
            tenant_id=tenant_id,
        )
        return self.repo.save_coverage_assessment(record)

    def get_coverage_assessment(self, assessment_id: str, tenant_id: str = "default") -> ContinuityCoverageAssessmentRecord:
        rec = self.repo.get_coverage_assessment(assessment_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.COVERAGE_ASSESSMENT_NOT_FOUND,
                message=f"Coverage assessment {assessment_id} not found",
                status_code=404,
            )
        return rec

    def list_coverage_assessments(self, tenant_id: str = "default") -> List[ContinuityCoverageAssessmentRecord]:
        return self.repo.list_coverage_assessments(tenant_id)


# Module-level instance
governance_continuity_assurance_coverage_service = GovernanceContinuityAssuranceCoverageService()

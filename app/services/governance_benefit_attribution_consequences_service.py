"""Phase 76: Benefit Attribution & Unintended Consequences Service.

Coordinates:
- Attribution analysis distinguishing causation from correlation
- Unintended operational consequence and trade-off logging
- Routing safety, risk, and adoption concerns to authoritative modules
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_attribution_consequences import (
    BenefitAttributionRecord,
    ConsequenceClassification,
    CreateAttributionAssessmentRequest,
    CreateConsequenceRequest,
    ReviewConsequenceRequest,
    RouteConsequenceRequest,
    UnintendedConsequenceRecord,
)


class GovernanceBenefitAttributionConsequencesService:
    """Service governing attribution analysis and unintended consequences handling."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()

    # -------------------------------------------------------------------------
    # Attribution Analysis
    # -------------------------------------------------------------------------

    def create_attribution_assessment(
        self,
        benefit_id: str,
        request: CreateAttributionAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitAttributionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        attribution_id = f"attr_{uuid.uuid4().hex[:12]}"

        record = BenefitAttributionRecord(
            attribution_id=attribution_id,
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            attribution_type=request.attribution_type,
            related_initiative_ids=request.related_initiative_ids,
            relevant_implementation_periods=request.relevant_implementation_periods,
            external_influencing_factors=request.external_influencing_factors,
            measurement_limitations=request.measurement_limitations,
            attribution_methodology=request.attribution_methodology,
            supporting_evidence=request.supporting_evidence,
            reviewer_id=current_user.user_id,
            created_at=now,
        )
        return self.repo.save_attribution(record)

    def list_attributions(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitAttributionRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_attributions_for_benefit(benefit_id, user_tenant)

    def get_attribution(
        self,
        assessment_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitAttributionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        attr = self.repo.get_attribution(assessment_id)
        if not attr or attr.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_ATTRIBUTION_NOT_FOUND,
                message=f"Attribution assessment '{assessment_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return attr

    # -------------------------------------------------------------------------
    # Unintended Consequences
    # -------------------------------------------------------------------------

    def create_consequence(
        self,
        benefit_id: str,
        request: CreateConsequenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> UnintendedConsequenceRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        consequence_id = f"csq_{uuid.uuid4().hex[:12]}"

        record = UnintendedConsequenceRecord(
            consequence_id=consequence_id,
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            related_initiative_ids=request.related_initiative_ids,
            description=request.description,
            affected_organizational_scope=request.affected_organizational_scope,
            evidence_references=request.evidence_references,
            source_measurements=request.source_measurements,
            detection_date=now,
            potential_impact=request.potential_impact,
            status=ConsequenceClassification.POTENTIAL_CONSEQUENCE,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_consequence(record)

    def list_consequences(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[UnintendedConsequenceRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_consequences_for_benefit(benefit_id, user_tenant)

    def review_consequence(
        self,
        consequence_id: str,
        request: ReviewConsequenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> UnintendedConsequenceRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        csq = self.repo.get_consequence(consequence_id)
        if not csq or csq.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_CONSEQUENCE_NOT_FOUND,
                message=f"Consequence '{consequence_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        csq.status = request.status
        csq.reviewer_id = current_user.user_id
        csq.review_notes = request.review_notes
        csq.updated_at = now
        return self.repo.save_consequence(csq)

    def route_consequence(
        self,
        consequence_id: str,
        request: RouteConsequenceRequest,
        current_user: AuthenticatedUserContext,
    ) -> UnintendedConsequenceRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        csq = self.repo.get_consequence(consequence_id)
        if not csq or csq.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_CONSEQUENCE_NOT_FOUND,
                message=f"Consequence '{consequence_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        csq.routed_destination = request.routed_destination
        csq.destination_reference = request.destination_reference
        csq.routing_notes = request.routing_notes
        csq.updated_at = now
        return self.repo.save_consequence(csq)

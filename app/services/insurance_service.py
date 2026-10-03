"""Patient Insurance Coverage Service (Phase 33).

Orchestrates patient insurance policy registration, validation, retrieval, and status updates.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    InsuranceDisabledException,
    InsuranceNotFoundException,
)
from app.repositories.insurance_repository import InsuranceRepository
from app.schemas.insurance import (
    CoverageStatus,
    InsuranceCoverageCreate,
    InsuranceCoverageRecord,
    InsuranceCoverageResponse,
    InsuranceCoverageUpdate,
    RelationshipType,
    mask_identifier,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.insurance_validation_service import InsuranceValidationService
from app.services.payer_authorization_service import PayerAuthorizationService

logger = logging.getLogger(__name__)


class InsuranceService:
    """Business service managing patient insurance coverage."""

    def __init__(self, repository: Optional[InsuranceRepository] = None) -> None:
        self.repo = repository or InsuranceRepository()

    def _ensure_enabled(self) -> None:
        if not settings.INSURANCE_ENABLED:
            raise InsuranceDisabledException("Insurance subsystem is currently disabled.")

    def create_coverage(
        self,
        caller: AuthenticatedUserContext,
        payload: InsuranceCoverageCreate,
    ) -> InsuranceCoverageResponse:
        """Register a new patient insurance policy."""
        self._ensure_enabled()
        InsuranceValidationService.validate_coverage_create(payload)

        # Build internal record
        coverage_id = f"cov_{uuid.uuid4().hex[:12]}"
        record = InsuranceCoverageRecord(
            id=coverage_id,
            patient_id=payload.patient_id,
            payer_id=payload.payer_id,
            payer_name=payload.payer_name,
            policy_number=payload.policy_number,
            member_id=payload.member_id,
            group_number=payload.group_number,
            plan_name=payload.plan_name,
            plan_type=payload.plan_type,
            subscriber_id=payload.subscriber.subscriber_id,
            subscriber_name=payload.subscriber.full_name,
            subscriber_dob=payload.subscriber.date_of_birth,
            relationship=payload.subscriber.relationship,
            status=CoverageStatus.UNVERIFIED,
            is_primary=payload.is_primary,
            start_date=payload.start_date,
            end_date=payload.end_date,
            document_reference_id=payload.document_reference_id,
        )

        PayerAuthorizationService.authorize_coverage_access(caller, record, action="create")
        created = self.repo.create(record)

        logger.info(
            f"Registered insurance coverage: id={created.id}, patient={created.patient_id}, "
            f"payer={created.payer_name}, policy={mask_identifier(created.policy_number)}"
        )
        return created.to_response()

    def get_coverage(
        self,
        caller: AuthenticatedUserContext,
        coverage_id: str,
    ) -> InsuranceCoverageResponse:
        """Retrieve patient insurance coverage by ID."""
        self._ensure_enabled()
        record = self.repo.get(coverage_id)
        if not record:
            raise InsuranceNotFoundException(f"Insurance coverage {coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, record, action="read")
        return record.to_response()

    def update_coverage(
        self,
        caller: AuthenticatedUserContext,
        coverage_id: str,
        payload: InsuranceCoverageUpdate,
    ) -> InsuranceCoverageResponse:
        """Update existing insurance coverage record."""
        self._ensure_enabled()
        record = self.repo.get(coverage_id)
        if not record:
            raise InsuranceNotFoundException(f"Insurance coverage {coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, record, action="update")

        if payload.status is not None:
            InsuranceValidationService.validate_coverage_transition(record.status, payload.status)
            record.status = payload.status

        if payload.plan_name is not None:
            record.plan_name = payload.plan_name
        if payload.group_number is not None:
            record.group_number = payload.group_number
        if payload.is_primary is not None:
            record.is_primary = payload.is_primary
        if payload.start_date is not None:
            record.start_date = payload.start_date
        if payload.end_date is not None:
            record.end_date = payload.end_date

        updated = self.repo.update(record)
        return updated.to_response()

    def delete_coverage(
        self,
        caller: AuthenticatedUserContext,
        coverage_id: str,
    ) -> bool:
        """Delete insurance coverage record."""
        self._ensure_enabled()
        record = self.repo.get(coverage_id)
        if not record:
            raise InsuranceNotFoundException(f"Insurance coverage {coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, record, action="delete")
        return self.repo.delete(coverage_id)

    def list_patient_coverages(
        self,
        caller: AuthenticatedUserContext,
        patient_id: str,
        status: Optional[CoverageStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InsuranceCoverageResponse], int]:
        """List coverage records for a given patient."""
        self._ensure_enabled()
        # Verify access for target patient
        dummy_record = InsuranceCoverageRecord(
            id="probe",
            patient_id=patient_id,
            payer_id="probe",
            payer_name="probe",
            policy_number="probe",
            member_id="probe",
            subscriber_id="probe",
            subscriber_name="probe",
        )
        PayerAuthorizationService.authorize_coverage_access(caller, dummy_record, action="read")

        records, total = self.repo.list_by_patient(patient_id, status=status, limit=limit, offset=offset)
        return [r.to_response() for r in records], total

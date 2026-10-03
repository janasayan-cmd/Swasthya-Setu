"""Diagnostic Result Verification Service (Phase 34 & Phase 10).

Integrates clinical verification workflow for laboratory and diagnostic results.
Enforces that results remain in REVIEW_REQUIRED until explicitly reviewed and certified
by an authorized clinician.

CRITICAL CLINICAL INVARIANTS:
- RESULT RECEIVED != CLINICALLY VERIFIED
- RESULT EXTRACTION != RESULT VERIFICATION
- RESULT VERIFICATION != CLINICAL DIAGNOSIS
- ONLY LICENSED CLINICIANS CAN VERIFY RESULTS
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    DiagnosticResultNotFoundException,
    ResultVerificationRequiredException,
)
from app.repositories.diagnostic_result_repository import DiagnosticResultRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_result import (
    DiagnosticResultRecord,
    ResultVerificationRequest,
    VerificationStatus,
)
from app.services.audit_service import AuditService
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService

logger = logging.getLogger(__name__)


class DiagnosticVerificationService:
    """Service handling clinician review and formal verification of diagnostic findings."""

    def __init__(
        self,
        result_repository: Optional[DiagnosticResultRepository] = None,
        authorization_service: Optional[DiagnosticAuthorizationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.result_repository = result_repository or DiagnosticResultRepository()
        self.authorization_service = authorization_service or DiagnosticAuthorizationService()
        self.audit_service = audit_service

    async def verify_result(
        self,
        result_id: str,
        verification_request: ResultVerificationRequest,
        clinician: AuthenticatedUserContext,
    ) -> DiagnosticResultRecord:
        """Execute clinician review and verification decision."""
        # 1. Authorize clinician role
        self.authorization_service.authorize_result_verification(clinician)

        # 2. Fetch result
        result = self.result_repository.get_by_id(result_id)
        if not result:
            raise DiagnosticResultNotFoundException(f"Diagnostic result '{result_id}' not found")

        # 3. Determine target verification status
        clinician_id = str(
            getattr(clinician, "clinician_id", None)
            or getattr(clinician, "doctor_id", None)
            or getattr(clinician, "id", None)
            or getattr(clinician, "user_id", None)
        )

        new_status = (
            VerificationStatus.VERIFIED
            if verification_request.action.upper() == "VERIFY"
            else VerificationStatus.REJECTED
        )

        updated = self.result_repository.verify_result(
            result_id=result.result_id,
            verified_by=clinician_id,
            verification_status=new_status,
            notes=verification_request.notes,
        )

        # 4. Audit
        if self.audit_service:
            event_type = (
                AuditEventType.DIAGNOSTIC_RESULT_VERIFIED
                if new_status == VerificationStatus.VERIFIED
                else AuditEventType.DIAGNOSTIC_RESULT_REJECTED
            )
            await self._audit(
                event_type=event_type,
                actor=clinician,
                resource_id=result.result_id,
                patient_id=result.patient_id,
                outcome="ALLOW",
                notes=verification_request.notes,
            )

        return updated or result

    async def _audit(
        self,
        event_type: AuditEventType,
        actor: AuthenticatedUserContext,
        resource_id: str,
        patient_id: Optional[str],
        outcome: str,
        notes: Optional[str] = None,
    ) -> None:
        if not self.audit_service:
            return
        actor_id = str(getattr(actor, "id", None) or getattr(actor, "user_id", None) or "unknown")
        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            action=event_type.value,
            resource_type="diagnostic_result",
            resource_id=resource_id,
            outcome=outcome,
            metadata={"notes": notes} if notes else None,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed for result verification: %s", e)

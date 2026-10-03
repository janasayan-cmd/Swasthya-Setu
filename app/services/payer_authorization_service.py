"""Payer & Insurance Multi-Tenant Authorization Service (Phase 33).

Enforces:
- Object-level security (BOLA / IDOR protection)
- Patient self-service scoping (Patient A cannot view or file claims for Patient B)
- Clinician and facility organizational boundaries
- Administrative permission validation
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.exceptions import (
    AuthorizationAccessDeniedException,
    ClaimAccessDeniedException,
    InsuranceAccessDeniedException,
    InsuranceNotAuthorizedException,
)
from app.core.policies import Permission, role_has_permission
from app.schemas.authorization import PreAuthorizationRecord
from app.schemas.claim import ClaimRecord
from app.schemas.insurance import InsuranceCoverageRecord
from app.schemas.user import AuthenticatedUserContext

logger = logging.getLogger(__name__)


class PayerAuthorizationService:
    """Security guard evaluating multi-tenant boundaries for insurance and claims."""

    @classmethod
    def _resolve_patient_id(cls, caller: AuthenticatedUserContext) -> Optional[str]:
        """Resolve patient record ID from caller context or patient repository."""
        if getattr(caller, "patient_id", None):
            return caller.patient_id
        try:
            from app.api.deps import get_patient_repository
            repo = get_patient_repository()
            if hasattr(repo, "_user_to_patient"):
                pid = repo._user_to_patient.get(caller.user_id)
                if pid:
                    return pid
        except Exception:
            pass
        return caller.user_id

    @classmethod
    def authorize_coverage_access(
        cls,
        caller: AuthenticatedUserContext,
        coverage: InsuranceCoverageRecord,
        action: str = "read",
    ) -> None:
        """Verify caller is authorized to view or mutate patient coverage."""
        role_str = caller.role.value if hasattr(caller.role, "value") else str(caller.role)

        # 1. Platform Admin roles have full visibility
        if role_str in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
            return

        # 2. Patient role — must strictly match patient_id (BOLA/IDOR barrier)
        if role_str == "PATIENT":
            caller_patient_id = cls._resolve_patient_id(caller)
            if caller_patient_id != coverage.patient_id and caller.user_id != coverage.patient_id:
                logger.warning(
                    f"BOLA/IDOR attempt: Patient {caller_patient_id} tried to {action} coverage for {coverage.patient_id}"
                )
                raise InsuranceAccessDeniedException("Patients can only access their own insurance records.")
            return

        # 3. Clinician roles (DOCTOR, NURSE, CLINICIAN)
        if role_str in ("DOCTOR", "NURSE", "CLINICIAN"):
            if not role_has_permission(role_str, Permission.INSURANCE_READ):
                raise InsuranceAccessDeniedException("Clinician role lacks insurance view permission.")
            return

        # 4. Facility / Organization staff
        if role_str in ("FACILITY_ADMIN", "ORG_ADMIN", "STAFF"):
            return

        raise InsuranceAccessDeniedException(f"Role {role_str} is not authorized to {action} insurance coverage.")

    @classmethod
    def authorize_preauth_access(
        cls,
        caller: AuthenticatedUserContext,
        auth_record: PreAuthorizationRecord,
        action: str = "read",
    ) -> None:
        """Verify caller is authorized to view or modify pre-authorization."""
        role_str = caller.role.value if hasattr(caller.role, "value") else str(caller.role)

        if role_str in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
            return

        if role_str == "PATIENT":
            caller_patient_id = cls._resolve_patient_id(caller)
            if caller_patient_id != auth_record.patient_id and caller.user_id != auth_record.patient_id:
                logger.warning(
                    f"BOLA/IDOR attempt: Patient {caller_patient_id} tried to {action} pre-authorization for {auth_record.patient_id}"
                )
                raise AuthorizationAccessDeniedException("Patients can only access their own pre-authorizations.")
            return

        if role_str in ("DOCTOR", "NURSE", "CLINICIAN", "FACILITY_ADMIN", "ORG_ADMIN"):
            # Check facility alignment if set
            if caller.facility_id and auth_record.facility_id and caller.facility_id != auth_record.facility_id:
                raise AuthorizationAccessDeniedException("Cross-facility pre-authorization access denied.")
            return

        raise AuthorizationAccessDeniedException(f"Role {role_str} is not authorized to {action} pre-authorizations.")

    @classmethod
    def authorize_claim_access(
        cls,
        caller: AuthenticatedUserContext,
        claim_record: ClaimRecord,
        action: str = "read",
    ) -> None:
        """Verify caller is authorized to view or submit claim."""
        role_str = caller.role.value if hasattr(caller.role, "value") else str(caller.role)

        if role_str in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"):
            return

        if role_str == "PATIENT":
            caller_patient_id = cls._resolve_patient_id(caller)
            if caller_patient_id != claim_record.patient_id and caller.user_id != claim_record.patient_id:
                logger.warning(
                    f"BOLA/IDOR attempt: Patient {caller_patient_id} tried to {action} claim for {claim_record.patient_id}"
                )
                raise ClaimAccessDeniedException("Patients can only access their own insurance claims.")
            return

        if role_str in ("FACILITY_ADMIN", "ORG_ADMIN", "STAFF"):
            if caller.facility_id and claim_record.facility_id and caller.facility_id != claim_record.facility_id:
                raise ClaimAccessDeniedException("Cross-facility claim access denied.")
            return

        if role_str in ("DOCTOR", "NURSE", "CLINICIAN"):
            return

        raise ClaimAccessDeniedException(f"Role {role_str} is not authorized to {action} claims.")


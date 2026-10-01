"""Support Operations Service (Phase 27).

Provides controlled troubleshooting capabilities for support operators:
- Minimum necessary patient account discovery (zero clinical data leakage)
- Audited identifier lookup
- Support operational overview

INVARIANTS:
- SUPPORT ACCESS != UNLIMITED DATA ACCESS
- PATIENT LOOKUP != CLINICAL RECORD ACCESS
- NO DIAGNOSES, NO MEDICATIONS, NO ALLERGIES, NO CLINICAL NOTES LEAKED
"""

from __future__ import annotations

from typing import Any, List, Optional
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.repositories.consent_repository import ConsentRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import SupportPatientItem, SupportPatientSearchResponse
from app.schemas.audit import AuditActor, AuditEventRecord, AuditEventType
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService

logger = get_logger("app.services.support_service")


class SupportService:
    """Service governing privacy-safe support operations and patient account lookup."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        user_repo: UserRepository,
        consent_repo: ConsentRepository,
        audit_service: AuditService,
    ) -> None:
        self._patient_repo = patient_repo
        self._user_repo = user_repo
        self._consent_repo = consent_repo
        self._audit = audit_service

    async def search_patient_account(
        self,
        query: str,
        actor: AuthenticatedUserContext,
        request_id: Optional[str] = None,
    ) -> SupportPatientSearchResponse:
        """Search patient accounts returning only strictly minimized operational data.
        
        INVARIANT: Contains ZERO clinical observations, notes, diagnoses, or prescriptions.
        """
        trimmed = query.strip()
        results: List[SupportPatientItem] = []

        if not trimmed:
            return SupportPatientSearchResponse(items=[], total=0)

        # 1. Lookup in patient repository (in-memory / DB)
        # Check by patient ID or search in known patient records
        patient_record = await self._patient_repo.get_by_id(trimmed)
        if patient_record:
            item = await self._build_support_item(patient_record)
            results.append(item)
        else:
            # Query by demographics/name/phone if repo supports or iterate
            all_patients = getattr(self._patient_repo, "_patients", {})
            for pid, prec in all_patients.items():
                sovereign_id = getattr(prec, "sovereign_id", "") or ""
                pname = getattr(prec, "name", "") or f"{getattr(prec, 'first_name', '')} {getattr(prec, 'last_name', '')}".strip()
                pphone = getattr(prec, "phone", "") or ""
                if (
                    trimmed.lower() in pid.lower()
                    or (sovereign_id and trimmed.lower() in sovereign_id.lower())
                    or (pname and trimmed.lower() in pname.lower())
                    or (pphone and trimmed in pphone)
                ):
                    item = await self._build_support_item(prec)
                    results.append(item)
                    if len(results) >= 20:
                        break

        # Log audit trail for support search
        await self._log_audit(
            event_type=AuditEventType.ADMIN_SUPPORT_LOOKUP,
            actor=actor,
            query=trimmed,
            match_count=len(results),
            request_id=request_id,
        )

        return SupportPatientSearchResponse(items=results, total=len(results))

    async def _build_support_item(self, patient: Any) -> SupportPatientItem:
        """Transform patient entity into minimized, non-clinical SupportPatientItem."""
        pid = str(patient.id)
        name = getattr(patient, "name", "") or f"{getattr(patient, 'first_name', '')} {getattr(patient, 'last_name', '')}".strip() or "Patient"

        # Mask name: e.g. "Subrata Ghosh" -> "S*** G***" or "Sub***"
        parts = name.split()
        masked_parts = [f"{p[0]}***" if len(p) > 1 else p for p in parts]
        masked_name = " ".join(masked_parts) if masked_parts else "P***"

        # Determine sovereign ID
        sovereign_id = getattr(patient, "sovereign_id", None)
        if not sovereign_id:
            cleaned_digits = "".join(c for c in pid if c.isdigit())
            suffix = cleaned_digits[-4:] if len(cleaned_digits) >= 4 else cleaned_digits.zfill(4)
            sovereign_id = f"HS-PAT-{suffix}"

        # Fetch active consent count
        consents = await self._consent_repo.list_by_patient(pid)
        active_consents = sum(1 for c in consents if getattr(c, "status", None) == "ACTIVE" or str(getattr(c, "status", "")).upper() == "ACTIVE")

        registered_at = getattr(patient, "registered_at", None) or getattr(patient, "created_at", None) or datetime.now(timezone.utc)
        if not isinstance(registered_at, datetime):
            registered_at = datetime.now(timezone.utc)

        return SupportPatientItem(
            patient_id=pid,
            sovereign_id=sovereign_id,
            masked_name=masked_name,
            account_status="ACTIVE",
            city=getattr(patient, "city", None),
            registered_at=registered_at,
            active_consent_count=active_consents,
        )

    async def _log_audit(
        self,
        event_type: AuditEventType,
        actor: AuthenticatedUserContext,
        query: str,
        match_count: int,
        request_id: Optional[str],
    ) -> None:
        try:
            event = AuditEventRecord(
                event_type=event_type,
                actor_id=actor.user_id,
                resource_type="patient_support_search",
                resource_id=f"query-{hash(query) & 0xffffffff:x}",
                outcome="ALLOW",
                request_id=request_id,
                metadata={"query_len": len(query), "match_count": match_count},
            )
            await self._audit.record_event(event)
        except Exception as e:
            logger.error(f"Failed to record support search audit event: {e}")


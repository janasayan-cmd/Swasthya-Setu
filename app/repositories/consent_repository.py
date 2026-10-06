"""Consent data access repository and database team contract definition.

DATABASE TEAM DEPENDENCY — PHASE 3
====================================
This repository defines the data access contract expected from the Database
Team's consent-related entities.

Required Consent entity fields:
  id              : Primary Key (UUID / string)
  patient_id      : FOREIGN KEY → users.id (consent subject)
  grantee_id      : FOREIGN KEY → users.id (consent recipient — e.g., doctor)
  purpose         : VARCHAR / ENUM — matches ConsentPurpose values
  scope           : VARCHAR / ENUM — matches ConsentScope values
  status          : ENUM ('ACTIVE', 'REVOKED', 'EXPIRED', 'PENDING', 'DENIED')
  granted_at      : TIMESTAMP WITH TIME ZONE
  effective_from  : TIMESTAMP WITH TIME ZONE
  expires_at      : NULLABLE TIMESTAMP WITH TIME ZONE
  revoked_at      : NULLABLE TIMESTAMP WITH TIME ZONE
  revoked_by      : NULLABLE FOREIGN KEY → users.id
  version         : INTEGER DEFAULT 1
  notes           : NULLABLE VARCHAR (patient notes, non-clinical)
  created_at      : TIMESTAMP WITH TIME ZONE

Required indexes:
  - (patient_id, status) for active consent lookup
  - (patient_id, grantee_id, purpose, scope, status) for targeted checks
  - (grantee_id, status) for doctor's granted-consents view

Until the database team delivers these, this repository operates on an
in-memory store for development and testing.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.schemas.authorization import ConsentStatus


@dataclass
class ConsentRecord:
    """Contract representing a consent record from the database."""

    id: str
    patient_id: str
    grantee_id: str
    purpose: str
    scope: str
    status: ConsentStatus = ConsentStatus.ACTIVE
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    withdrawal_reason: str | None = None
    version: int = 1
    notes: str | None = None
    recipient_type: str = "CLINICIAN"
    resource_scopes: list[str] = field(default_factory=list)
    action_scopes: list[str] = field(default_factory=lambda: ["READ"])
    evidence: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """True only when status is ACTIVE and within effective validity period."""
        if self.status != ConsentStatus.ACTIVE:
            return False
        now = datetime.now(timezone.utc)
        if self.effective_from > now:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True


class ConsentRepository(BaseRepository[Any]):
    """Repository managing consent lifecycle data access.

    In-memory implementation serves as a functional placeholder until
    the Database Team delivers the production consent schema and models.
    Integration point comments are provided throughout.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session=session)  # type: ignore[arg-type]
        # In-memory stores (testing/dev fallback)
        self._consents: dict[str, ConsentRecord] = {}   # id → record

    # -----------------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------------

    async def create_consent(self, record: ConsentRecord) -> ConsentRecord:
        """Persist a new consent record."""
        # Ensure default scopes populated if empty
        if not record.resource_scopes and record.scope:
            record.resource_scopes = [record.scope.upper()]
        if not record.action_scopes:
            record.action_scopes = ["READ"]
        # Add initial history entry if none exists
        if not record.history:
            record.history = [
                {
                    "version": record.version,
                    "status": record.status.value,
                    "changed_at": record.granted_at.isoformat() if hasattr(record.granted_at, "isoformat") else str(record.granted_at),
                    "actor_id": record.patient_id,
                    "reason": "Initial consent grant",
                    "purpose": record.purpose,
                    "resource_scopes": list(record.resource_scopes),
                    "action_scopes": list(record.action_scopes),
                }
            ]
        self._consents[record.id] = record
        return record

    create = create_consent

    def add(self, record: ConsentRecord) -> ConsentRecord:
        """Synchronously persist a record into in-memory store (convenient for testing)."""
        if not record.resource_scopes and record.scope:
            record.resource_scopes = [record.scope.upper()]
        if not record.action_scopes:
            record.action_scopes = ["READ"]
        if not record.history:
            record.history = [
                {
                    "version": record.version,
                    "status": record.status.value,
                    "changed_at": record.granted_at.isoformat() if hasattr(record.granted_at, "isoformat") else str(record.granted_at),
                    "actor_id": record.patient_id,
                    "reason": "Initial consent grant",
                    "purpose": record.purpose,
                    "resource_scopes": list(record.resource_scopes),
                    "action_scopes": list(record.action_scopes),
                }
            ]
        self._consents[record.id] = record
        return record

    async def update_consent(self, record: ConsentRecord) -> ConsentRecord:
        """Persist updates to an existing consent record."""
        self._consents[record.id] = record
        return record

    update = update_consent

    async def update_consent_status(
        self,
        consent_id: str,
        new_status: ConsentStatus,
        revoked_at: datetime | None = None,
        revoked_by: str | None = None,
        reason: str | None = None,
    ) -> ConsentRecord | None:
        """Update consent status (for revocation, withdrawal, expiration, etc.)."""
        record = self._consents.get(consent_id)
        if record is None:
            return None

        from dataclasses import replace
        now = datetime.now(timezone.utc)
        new_history = list(record.history)
        new_history.append({
            "version": record.version,
            "status": new_status.value,
            "changed_at": (revoked_at or now).isoformat(),
            "actor_id": revoked_by or record.patient_id,
            "reason": reason or f"Status changed to {new_status.value}",
            "purpose": record.purpose,
            "resource_scopes": list(record.resource_scopes),
            "action_scopes": list(record.action_scopes),
        })

        updated = replace(
            record,
            status=new_status,
            revoked_at=revoked_at or (now if new_status in (ConsentStatus.REVOKED, ConsentStatus.WITHDRAWN) else record.revoked_at),
            revoked_by=revoked_by or record.revoked_by,
            withdrawal_reason=reason if new_status == ConsentStatus.WITHDRAWN else record.withdrawal_reason,
            history=new_history,
        )
        self._consents[consent_id] = updated
        return updated

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    async def get_by_id(self, consent_id: str) -> ConsentRecord | None:
        """Retrieve a consent record by its primary key."""
        return self._consents.get(consent_id)

    async def get_active_consent(
        self,
        patient_id: str,
        grantee_id: str,
        purpose: str,
        scope: str,
        action: str | None = None,
    ) -> ConsentRecord | None:
        """Look up an ACTIVE consent matching patient, grantee, purpose, scope, and action."""
        now = datetime.now(timezone.utc)
        norm_purpose = purpose.strip().upper()
        norm_scope = scope.strip().upper()
        norm_action = action.strip().upper() if action else None

        for record in self._consents.values():
            if record.patient_id != patient_id or record.grantee_id != grantee_id:
                continue

            if record.status != ConsentStatus.ACTIVE:
                continue

            if record.effective_from > now:
                continue

            if record.expires_at is not None and record.expires_at <= now:
                continue

            # Purpose match (support exact string match or normalized enum)
            rec_purpose = record.purpose.strip().upper()
            purpose_matches = (
                rec_purpose == norm_purpose
                or (norm_purpose == "CARE" and rec_purpose in ("CARE", "CARE_DELIVERY"))
                or (norm_purpose == "CARE_DELIVERY" and rec_purpose in ("CARE", "CARE_DELIVERY"))
            )
            if not purpose_matches:
                continue

            # Scope match (check legacy scope string or resource_scopes list)
            rec_scope = record.scope.strip().upper()
            scopes_set = {s.strip().upper() for s in record.resource_scopes}
            scopes_set.add(rec_scope)

            scope_matches = (
                "ALL_RECORDS" in scopes_set
                or norm_scope in scopes_set
                or (norm_scope == "CLINICAL_RECORDS" and "CLINICAL_RECORD" in scopes_set)
                or (norm_scope == "CLINICAL_RECORD" and "CLINICAL_RECORDS" in scopes_set)
                or (norm_scope == "DOCUMENTS" and "DOCUMENT" in scopes_set)
                or (norm_scope == "DOCUMENT" and "DOCUMENTS" in scopes_set)
            )
            if not scope_matches:
                continue

            # Action match if requested
            if norm_action:
                actions_set = {a.strip().upper() for a in record.action_scopes}
                if actions_set and norm_action not in actions_set:
                    continue

            return record

        return None

    async def list_by_patient(
        self,
        patient_id: str,
        status_filter: ConsentStatus | None = None,
    ) -> list[ConsentRecord]:
        """List consents where the patient is the subject."""
        results = [r for r in self._consents.values() if r.patient_id == patient_id]
        if status_filter is not None:
            results = [r for r in results if r.status == status_filter]
        return results

    async def list_by_grantee(
        self,
        grantee_id: str,
        status_filter: ConsentStatus | None = None,
    ) -> list[ConsentRecord]:
        """List consents where the grantee is the recipient."""
        results = [r for r in self._consents.values() if r.grantee_id == grantee_id]
        if status_filter is not None:
            results = [r for r in results if r.status == status_filter]
        return results

    async def find_active_by_patient_and_grantee(
        self,
        patient_id: str,
        grantee_id: str,
    ) -> list[ConsentRecord]:
        """Find active consents for a specific patient and grantee."""
        now = datetime.now(timezone.utc)
        return [
            r for r in self._consents.values()
            if r.patient_id == patient_id
            and r.grantee_id == grantee_id
            and r.status == ConsentStatus.ACTIVE
            and r.effective_from <= now
            and (r.expires_at is None or r.expires_at > now)
        ]

    async def get_expired_active_consents(self) -> list[ConsentRecord]:
        """Retrieve all consents currently marked ACTIVE whose expires_at is past."""
        now = datetime.now(timezone.utc)
        return [
            r for r in self._consents.values()
            if r.status == ConsentStatus.ACTIVE and r.expires_at is not None and r.expires_at <= now
        ]

    async def list_all(self) -> list[ConsentRecord]:
        """List all consent records in store."""
        return list(self._consents.values())


consent_repository = ConsentRepository()


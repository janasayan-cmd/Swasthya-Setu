"""Patient data access repository and database team contract definition.

DATABASE TEAM DEPENDENCY — PHASE 4
====================================
See app/schemas/patient.py for the full entity field contract.

Patient vs User distinction:
  USER  → authentication identity (users table, Phase 2)
  PATIENT → clinical subject (patients table, Phase 4)

The patient record uses a stable patient ID as canonical clinical identifier.
Patient user_id is a NULLABLE link to an authentication account.

Until the database team delivers the patients table and ORM model,
this repository operates on an in-memory store.

Integration points are documented with "NOTE FOR DATABASE TEAM" comments.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.schemas.patient import BiologicalSex, PatientStatus


@dataclass
class PatientRecord:
    """Internal contract representing a patient entity from the database."""
    id: str
    user_id: str | None
    first_name: str
    last_name: str
    date_of_birth: date
    sex: BiologicalSex
    status: PatientStatus
    created_at: datetime
    updated_at: datetime
    preferred_language: str | None = None
    phone: str | None = None
    email: str | None = None
    sovereign_id: str | None = None
    city: str | None = None


class PatientRepository(BaseRepository[Any]):
    """Repository managing patient entity data access.

    In-memory implementation is the functional fallback until the Database
    Team delivers the patients table, ORM model, and migrations.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session=session)  # type: ignore[arg-type]
        self._patients: dict[str, PatientRecord] = {}          # id → record
        self._user_to_patient: dict[str, str] = {}             # user_id → patient_id

    # -----------------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------------

    async def create(self, record: PatientRecord) -> PatientRecord:
        """Persist a new patient record.

        NOTE FOR DATABASE TEAM:
            async with self.session.begin():
                orm = PatientModel(**dataclasses.asdict(record))
                self.session.add(orm)
            return map_orm_to_record(orm)
        """
        self._patients[record.id] = record
        if record.user_id:
            self._user_to_patient[record.user_id] = record.id
        return record

    async def update(self, patient_id: str, updates: dict) -> PatientRecord | None:
        """Apply a partial update to a patient record.

        Only keys present in `updates` are changed. Omitted keys are preserved.

        NOTE FOR DATABASE TEAM: use UPDATE with selective SET clause.
        """
        record = self._patients.get(patient_id)
        if record is None:
            return None
        updated = replace(record, **updates, updated_at=datetime.now(timezone.utc))
        self._patients[patient_id] = updated
        return updated

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    async def get_by_id(self, patient_id: str) -> PatientRecord | None:
        """Retrieve patient by primary key.

        NOTE FOR DATABASE TEAM:
            stmt = select(PatientModel).where(PatientModel.id == patient_id)
            result = await self.session.execute(stmt)
            return map_orm_to_record(result.scalar_one_or_none())
        """
        return self._patients.get(patient_id)

    async def get_by_user_id(self, user_id: str) -> PatientRecord | None:
        """Retrieve the patient record linked to an authentication user.

        NOTE FOR DATABASE TEAM:
            stmt = select(PatientModel).where(PatientModel.user_id == user_id)
        """
        patient_id = self._user_to_patient.get(user_id)
        return self._patients.get(patient_id) if patient_id else None

    async def register_patient_for_user(self, patient: PatientRecord) -> PatientRecord:
        """Convenience method: create or replace the patient record for a user.
        Used in test setup / seeding.
        """
        return await self.create(patient)

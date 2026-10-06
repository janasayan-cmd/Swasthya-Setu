"""Identity Resolution Service (Phase 45).

Resolves external patient identity deterministically against HealthSetu patients
while strictly enforcing non-negotiable safety boundaries:
- AI MUST NOT autonomously declare a patient match or merge patients.
- Same name != Same patient.
- Same phone != Same patient.
- Same email != Same patient.
- Same date of birth != Same patient.
- Same external ID across different source organizations != Same patient.
- Ambiguous identity -> STOP -> REVIEW_REQUIRED.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import (
    AIPatientMatchProhibitedException,
    IngestionIdentityConflictException,
    IngestionIdentityUnresolvedException,
)
from datetime import date, datetime, timezone
from app.repositories.interoperability_repository import InteroperabilityRepository
from app.repositories.patient_repository import PatientRecord, PatientRepository
from app.schemas.ingestion import IdentityMatchOutcome
from app.schemas.patient import BiologicalSex, PatientStatus

logger = logging.getLogger("app.services.identity_resolution")


class IdentityResolutionService:
    """Deterministic, safety-gated patient identity resolution engine."""

    def __init__(
        self,
        interop_repo: InteroperabilityRepository,
        patient_repo: PatientRepository,
    ) -> None:
        self.interop_repo = interop_repo
        self.patient_repo = patient_repo

    def clear(self) -> None:
        """Clear identity mappings and patient cache for test isolation."""
        self.interop_repo.clear()
        self.patient_repo._patients.clear()
        self.patient_repo._user_to_patient.clear()

    def register_external_identifier(
        self,
        system: str,
        value: str,
        patient_id: str,
    ) -> None:
        """Register a deterministic mapping between an external identifier and internal patient ID."""
        self.interop_repo._identity_mappings[(system.lower().strip(), value.strip())] = patient_id

    def register_patient_demographics(
        self,
        patient_id: str,
        full_name: str,
        dob: str,
        gender: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        """Register patient demographics in patient repository for candidate matching."""
        parts = full_name.strip().split()
        first_name = parts[0]
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        d = date.fromisoformat(dob)
        sex = BiologicalSex.MALE if gender.lower() == "male" else BiologicalSex.FEMALE
        rec = PatientRecord(
            id=patient_id,
            user_id=None,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=d,
            sex=sex,
            status=PatientStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            phone=phone,
            email=email,
        )
        self.patient_repo._patients[patient_id] = rec

    async def resolve_patient_identity(
        self,
        source_system: str,
        external_patient_id: Optional[str] = None,
        healthsetu_patient_id: Optional[str] = None,
        demographics: Optional[Dict[str, Any]] = None,
        is_ai_agent: bool = False,
    ) -> Tuple[IdentityMatchOutcome, Optional[str], Optional[str]]:
        """Resolve external patient identifier to canonical HealthSetu patient ID.

        Returns: (outcome, resolved_patient_id, reason_detail)
        """
        # 1. AI Safety Boundary (Non-negotiable)
        if is_ai_agent:
            raise AIPatientMatchProhibitedException(
                "AI cannot autonomously declare patient identity matches, merge records, or assign clinical identities."
            )

        source_clean = source_system.lower().strip()
        ext_id_clean = external_patient_id.strip() if external_patient_id else None

        # 2. Direct Explicit HealthSetu Patient ID resolution
        if healthsetu_patient_id:
            hs_id = healthsetu_patient_id.strip()
            existing_patient = await self.patient_repo.get_by_id(hs_id)
            if not existing_patient:
                logger.warning(f"Target HealthSetu patient ID '{hs_id}' does not exist.")
                return IdentityMatchOutcome.NO_MATCH, None, f"Patient '{hs_id}' not found in HealthSetu."

            # Check for conflict with previously stored deterministic external mapping
            if ext_id_clean:
                mapped_id = await self.interop_repo.resolve_identity(source_clean, ext_id_clean)
                if mapped_id and mapped_id != hs_id:
                    logger.error(
                        f"Identity conflict: External ID '{ext_id_clean}' in '{source_clean}' is mapped to '{mapped_id}' but request specifies '{hs_id}'"
                    )
                    return (
                        IdentityMatchOutcome.CONFLICT,
                        None,
                        f"Conflict: External ID '{ext_id_clean}' is already linked to patient '{mapped_id}', not '{hs_id}'.",
                    )

                # Link if not yet mapped
                if not mapped_id:
                    await self.interop_repo.map_identity(source_clean, ext_id_clean, hs_id)

            return IdentityMatchOutcome.MATCH_CONFIRMED, hs_id, "Deterministic patient ID confirmed."

        # 3. Known External Identifier Mapping lookup
        if ext_id_clean:
            mapped_patient_id = await self.interop_repo.resolve_identity(source_clean, ext_id_clean)
            if mapped_patient_id:
                patient_rec = await self.patient_repo.get_by_id(mapped_patient_id)
                if patient_rec:
                    return (
                        IdentityMatchOutcome.MATCH_CONFIRMED,
                        mapped_patient_id,
                        f"Resolved via registered external mapping from '{source_clean}'.",
                    )
                else:
                    return (
                        IdentityMatchOutcome.CONFLICT,
                        None,
                        f"Mapped patient ID '{mapped_patient_id}' no longer exists in repository.",
                    )

        # 4. Demographic matching (Guard against false-positive conflation)
        if demographics:
            name = (demographics.get("name") or "").strip().lower()
            phone = (demographics.get("phone") or "").strip()
            email = (demographics.get("email") or "").strip().lower()

            # Search existing patients
            matched_candidates = []
            for pat in self.patient_repo._patients.values():
                full_name = f"{pat.first_name} {pat.last_name}".strip().lower()
                if (name and full_name == name) or (phone and pat.phone == phone) or (email and pat.email == email):
                    matched_candidates.append(pat)

            if len(matched_candidates) > 1:
                # Ambiguity: Multiple candidates found! MUST STOP -> REVIEW_REQUIRED
                logger.warning(
                    f"Multiple demographic matches found ({len(matched_candidates)}) for inbound payload from '{source_clean}'."
                )
                return (
                    IdentityMatchOutcome.MULTIPLE_MATCHES,
                    None,
                    f"Ambiguous demographic match: {len(matched_candidates)} candidate patients found. Manual review required.",
                )

            if len(matched_candidates) == 1:
                candidate = matched_candidates[0]
                # A demographic candidate is NEVER automatically confirmed without deterministic identifier!
                return (
                    IdentityMatchOutcome.MATCH_CANDIDATE,
                    candidate.id,
                    f"Single demographic candidate matched ('{candidate.id}'). Requires confirmation before automatic integration.",
                )

        # 5. No identifier or demographic found
        if not ext_id_clean and not demographics:
            return (
                IdentityMatchOutcome.INSUFFICIENT_INFORMATION,
                None,
                "Inbound payload contains neither patient identifier nor demographic details.",
            )

        return (
            IdentityMatchOutcome.NO_MATCH,
            None,
            f"External patient ID '{ext_id_clean}' from '{source_clean}' is unmapped in HealthSetu.",
        )

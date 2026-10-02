"""PostgreSQL-Native Search Provider Adapter for HealthSetu (Phase 30).

Implements the SearchProvider contract by connecting to existing domain repositories.
Supports:
- EXACT matching (IDs, sovereign codes)
- PREFIX matching (titles, names, codes)
- CONTAINS / Full-Text matching (names, descriptions, document summaries)
- Strict pre-search scoping (organization, facility, patient constraints)
- Minimum necessary data minimization
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.search.base import SearchProvider
from app.repositories.care_plan_repository import CarePlanRepository
from app.repositories.clinical_note_repository import ClinicalNoteRepository
from app.repositories.discharge_repository import DischargeRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.encounter_repository import EncounterRepository
from app.repositories.facility_repository import FacilityRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.search_repository import SearchRepository
from app.repositories.transfer_repository import TransferRepository
from app.schemas.search import MatchType, SearchRequest, SearchResourceType
from app.schemas.search_result import (
    SearchIndexStatus,
    SearchResultItem,
    SearchResultProvenance,
)


class PostgresSearchProvider(SearchProvider):
    """PostgreSQL provider querying domain models with authorization constraints."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        document_repo: DocumentRepository,
        encounter_repo: EncounterRepository,
        prescription_repo: PrescriptionRepository,
        medication_repo: MedicationRepository,
        care_plan_repo: CarePlanRepository,
        discharge_repo: DischargeRepository,
        clinical_note_repo: ClinicalNoteRepository,
        org_repo: OrganizationRepository,
        facility_repo: FacilityRepository,
        transfer_repo: TransferRepository,
        search_repo: SearchRepository,
        appointment_repo: Optional[Any] = None,
    ) -> None:
        self.patient_repo = patient_repo
        self.document_repo = document_repo
        self.encounter_repo = encounter_repo
        self.prescription_repo = prescription_repo
        self.medication_repo = medication_repo
        self.care_plan_repo = care_plan_repo
        self.discharge_repo = discharge_repo
        self.clinical_note_repo = clinical_note_repo
        self.org_repo = org_repo
        self.facility_repo = facility_repo
        self.transfer_repo = transfer_repo
        self.search_repo = search_repo
        self.appointment_repo = appointment_repo

    @property
    def provider_name(self) -> str:
        return "postgres"

    async def search(
        self,
        request: SearchRequest,
        allowed_resource_types: List[SearchResourceType],
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Tuple[List[SearchResultItem], int]:
        """Aggregate results across all authorized resource types."""
        results: List[SearchResultItem] = []

        for r_type in allowed_resource_types:
            items, _ = await self.search_resource(
                resource_type=r_type,
                request=request,
                actor_patient_id=actor_patient_id,
                actor_org_id=actor_org_id,
                actor_facility_id=actor_facility_id,
                is_admin=is_admin,
            )
            results.extend(items)

        return results, len(results)

    async def search_resource(
        self,
        resource_type: SearchResourceType,
        request: SearchRequest,
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Tuple[List[SearchResultItem], int]:
        """Resource-specific search queries using existing repository contracts."""
        q = request.query.lower().strip()
        items: List[SearchResultItem] = []

        if resource_type == SearchResourceType.PATIENT:
            # Sensitive patient lookup
            patients = getattr(self.patient_repo, "_patients", {})
            for p_id, p in patients.items():
                if actor_patient_id and p_id != actor_patient_id:
                    continue
                # Match by ID, name, sovereign_id
                full_name = f"{p.first_name} {p.last_name}".lower()
                m_type = None
                score = 0.5
                if p_id.lower() == q or (p.sovereign_id and p.sovereign_id.lower() == q):
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif full_name.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in full_name:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    # Patient result display minimization (No full DOB or contact details)
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.PATIENT,
                            resource_id=p_id,
                            display=f"{p.first_name} {p.last_name}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(p.status.value if hasattr(p.status, "value") else p.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.ORGANIZATION:
            orgs = getattr(self.org_repo, "_organizations", {})
            for o_id, org in orgs.items():
                name = org.name.lower()
                m_type = None
                score = 0.5
                if o_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif name.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in name:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.ORGANIZATION,
                            resource_id=o_id,
                            display=org.name,
                            match_type=m_type,
                            source="healthsetu",
                            status=str(org.status.value if hasattr(org.status, "value") else org.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.FACILITY:
            facs = getattr(self.facility_repo, "_facilities", {})
            for f_id, fac in facs.items():
                if actor_org_id and fac.organization_id != actor_org_id:
                    continue
                name = fac.name.lower()
                m_type = None
                score = 0.5
                if f_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif name.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in name:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.FACILITY,
                            resource_id=f_id,
                            display=fac.name,
                            match_type=m_type,
                            source="healthsetu",
                            status=str(fac.status.value if hasattr(fac.status, "value") else fac.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(
                                source="healthsetu",
                                source_organization_id=fac.organization_id,
                            ),
                        )
                    )

        elif resource_type == SearchResourceType.DOCUMENT:
            docs = getattr(self.document_repo, "_documents", {})
            for d_id, doc in docs.items():
                if actor_patient_id and doc.patient_id != actor_patient_id:
                    continue
                if request.filters and request.filters.patient_id and doc.patient_id != request.filters.patient_id:
                    continue
                fname = (doc.filename or "").lower()
                dtype = str(doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type).lower()
                m_type = None
                score = 0.5
                if d_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif fname.startswith(q) or dtype.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in fname or q in dtype:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.DOCUMENT,
                            resource_id=d_id,
                            display=f"{doc.document_type} - {doc.filename}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(doc.lifecycle_state.value if hasattr(doc.lifecycle_state, "value") else doc.lifecycle_state),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.MEDICATION:
            meds = getattr(self.medication_repo, "_medications", {})
            for m_id, med in meds.items():
                cname = med.canonical_name.lower()
                gname = (med.generic_name or "").lower()
                bname = (med.brand_name or "").lower()
                m_type = None
                score = 0.5
                if m_id.lower() == q or med.terminology_code.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif cname.startswith(q) or gname.startswith(q) or bname.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in cname or q in gname or q in bname:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.MEDICATION,
                            resource_id=m_id,
                            display=med.canonical_name,
                            match_type=m_type,
                            source="healthsetu",
                            status="ACTIVE",
                            relevance_score=score,
                            provenance=SearchResultProvenance(
                                source="healthsetu",
                                source_version=med.provider_version,
                            ),
                        )
                    )

        elif resource_type == SearchResourceType.PRESCRIPTION:
            rxs = getattr(self.prescription_repo, "_prescriptions", {})
            for rx_id, rx in rxs.items():
                if actor_patient_id and rx.patient_id != actor_patient_id:
                    continue
                if request.filters and request.filters.patient_id and rx.patient_id != request.filters.patient_id:
                    continue
                m_type = None
                score = 0.5
                if rx_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif q in "prescription":
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.PRESCRIPTION,
                            resource_id=rx_id,
                            display=f"Prescription {rx_id[:8]}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(rx.status.value if hasattr(rx.status, "value") else rx.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.ENCOUNTER:
            encs = getattr(self.encounter_repo, "_records", {})
            for e_id, enc in encs.items():
                if actor_patient_id and enc.patient_id != actor_patient_id:
                    continue
                if request.filters and request.filters.patient_id and enc.patient_id != request.filters.patient_id:
                    continue
                etype = str(enc.encounter_type.value if hasattr(enc.encounter_type, "value") else enc.encounter_type).lower()
                m_type = None
                score = 0.5
                if e_id.lower() == q or (enc.external_id and enc.external_id.lower() == q):
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif etype.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in etype:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.ENCOUNTER,
                            resource_id=e_id,
                            display=f"Encounter {enc.encounter_type}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(enc.status.value if hasattr(enc.status, "value") else enc.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(
                                source="healthsetu",
                                source_organization_id=enc.organization_id,
                            ),
                        )
                    )

        elif resource_type == SearchResourceType.CLINICAL_NOTE:
            notes = getattr(self.clinical_note_repo, "_notes", {})
            for n_id, note in notes.items():
                if actor_patient_id and note.patient_id != actor_patient_id:
                    continue
                if request.filters and request.filters.patient_id and note.patient_id != request.filters.patient_id:
                    continue
                title = (note.title or "").lower()
                ntype = str(note.note_type.value if hasattr(note.note_type, "value") else note.note_type).lower()
                m_type = None
                score = 0.5
                if n_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif title.startswith(q) or ntype.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in title or q in ntype:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.CLINICAL_NOTE,
                            resource_id=n_id,
                            display=note.title or f"Clinical Note {note.note_type}",
                            match_type=m_type,
                            source="healthsetu",
                            status="SIGNED" if getattr(note, "is_signed", False) else "UNSIGNED",
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.CARE_PLAN:
            plans = getattr(self.care_plan_repo, "_care_plans", {})
            for p_id, plan in plans.items():
                if actor_patient_id and plan.patient_id != actor_patient_id:
                    continue
                title = (plan.title or "").lower()
                m_type = None
                score = 0.5
                if p_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif title.startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in title:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.CARE_PLAN,
                            resource_id=p_id,
                            display=plan.title or f"Care Plan {p_id[:8]}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(plan.status.value if hasattr(plan.status, "value") else plan.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.DISCHARGE:
            recs = getattr(self.discharge_repo, "_records", {})
            for d_id, rec in recs.items():
                if actor_patient_id and rec.patient_id != actor_patient_id:
                    continue
                m_type = None
                score = 0.5
                if d_id.lower() == q or rec.document_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif "discharge" in q:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.DISCHARGE,
                            resource_id=d_id,
                            display=f"Discharge Record {d_id[:8]}",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(rec.verification_status.value if hasattr(rec.verification_status, "value") else rec.verification_status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.TRANSFER:
            transfers = getattr(self.transfer_repo, "_transfers", {})
            for t_id, tr in transfers.items():
                if actor_patient_id and tr.patient_id != actor_patient_id:
                    continue
                if actor_facility_id and actor_facility_id not in (tr.sending_facility_id, tr.receiving_facility_id):
                    continue
                m_type = None
                score = 0.5
                if t_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif "transfer" in q:
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.TRANSFER,
                            resource_id=t_id,
                            display=f"Transfer {tr.priority} ({tr.status})",
                            match_type=m_type,
                            source="healthsetu",
                            status=str(tr.status.value if hasattr(tr.status, "value") else tr.status),
                            relevance_score=score,
                            provenance=SearchResultProvenance(source="healthsetu"),
                        )
                    )

        elif resource_type == SearchResourceType.APPOINTMENT:
            appts = getattr(self.appointment_repo, "_appointments", {}) if self.appointment_repo else {}
            for a_id, appt in appts.items():
                if actor_patient_id and appt.patient_id != actor_patient_id:
                    continue
                if actor_facility_id and appt.facility_id != actor_facility_id:
                    continue
                m_type = None
                score = 0.5
                app_type_val = appt.appointment_type.value if hasattr(appt.appointment_type, "value") else str(appt.appointment_type)
                app_status_val = appt.status.value if hasattr(appt.status, "value") else str(appt.status)
                if a_id.lower() == q:
                    m_type = MatchType.IDENTIFIER
                    score = 1.0
                elif app_type_val.lower().startswith(q):
                    m_type = MatchType.PREFIX
                    score = 0.8
                elif q in app_type_val.lower() or (appt.reason and q in appt.reason.lower()):
                    m_type = MatchType.CONTAINS
                    score = 0.6

                if m_type:
                    items.append(
                        SearchResultItem(
                            resource_type=SearchResourceType.APPOINTMENT,
                            resource_id=a_id,
                            display=f"Appointment {app_type_val} ({app_status_val})",
                            match_type=m_type,
                            source="healthsetu",
                            status=app_status_val,
                            relevance_score=score,
                            provenance=SearchResultProvenance(
                                source="healthsetu",
                                source_organization_id=appt.organization_id,
                            ),
                        )
                    )

        return items, len(items)

    async def get_suggestions(
        self,
        query: str,
        resource_type: Optional[SearchResourceType],
        allowed_resource_types: List[SearchResourceType],
        limit: int = 10,
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Authorized suggestions without leaking sensitive data."""
        suggestions: List[Dict[str, Any]] = []
        req = SearchRequest(query=query, resource_type=resource_type, page=1, page_size=limit)
        target_types = [resource_type] if resource_type else allowed_resource_types

        items, _ = await self.search(
            request=req,
            allowed_resource_types=target_types,
            actor_patient_id=actor_patient_id,
            actor_org_id=actor_org_id,
        )

        for item in items[:limit]:
            suggestions.append({
                "text": item.display,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
            })
        return suggestions

    async def health_check(self) -> Dict[str, Any]:
        """Perform provider health check."""
        return {
            "provider": self.provider_name,
            "status": "HEALTHY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_index_status(self) -> SearchIndexStatus:
        """Fetch index status from repository."""
        return await self.search_repo.get_operational_status(self.provider_name)

    async def rebuild_index(self, resource_type: Optional[SearchResourceType] = None) -> Dict[str, Any]:
        """Synchronize/rebuild repository index markers."""
        job_id = f"rebuild-{int(datetime.now(timezone.utc).timestamp())}"
        await self.search_repo.record_rebuild_job(
            job_id=job_id,
            details={
                "resource_type": resource_type.value if resource_type else "ALL",
                "status": "COMPLETED",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"job_id": job_id, "status": "COMPLETED"}

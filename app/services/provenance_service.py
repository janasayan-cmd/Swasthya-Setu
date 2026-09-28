from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from app.schemas.provenance import (
    ProvenanceCategory,
    ProvenanceVerificationState,
    ProvenanceRecord,
)

class ProvenanceService:
    """
    Manages provenance evaluation, creation, and integrity validation
    across disparate clinical sources (patient input, clinician input,
    extracted documents, OCR, interoperability imports, AI output).
    """

    def create_provenance(
        self,
        category: ProvenanceCategory,
        source_system: str = "HealthSetu",
        source_organization_id: Optional[str] = None,
        author_id: Optional[str] = None,
        verification_state: ProvenanceVerificationState = ProvenanceVerificationState.UNVERIFIED,
        verified_by: Optional[str] = None,
        original_resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceRecord:
        now = datetime.now(timezone.utc)
        verified_at = now if verification_state == ProvenanceVerificationState.CLINICIAN_VERIFIED else None

        return ProvenanceRecord(
            provenance_id=f"prov_{uuid.uuid4().hex[:12]}",
            category=category,
            source_system=source_system,
            source_organization_id=source_organization_id,
            author_id=author_id,
            recorded_at=now,
            verification_state=verification_state,
            verified_by=verified_by,
            verified_at=verified_at,
            original_resource_id=original_resource_id,
            metadata=metadata or {},
        )

    def verify_provenance(
        self,
        provenance: ProvenanceRecord,
        verified_by: str,
    ) -> ProvenanceRecord:
        """
        Transitions unverified / patient-reported / extracted provenance
        to clinician-verified upon explicit human clinical review.
        """
        provenance.verification_state = ProvenanceVerificationState.CLINICIAN_VERIFIED
        provenance.verified_by = verified_by
        provenance.verified_at = datetime.now(timezone.utc)
        return provenance

    def assess_provenance_completeness(self, record_data: Dict[str, Any]) -> List[str]:
        """
        Returns a list of missing provenance attributes.
        """
        missing: List[str] = []
        if not record_data.get("source") and not record_data.get("provenance"):
            missing.append("source")
        if not record_data.get("created_at") and not record_data.get("recorded_at"):
            missing.append("timestamp")
        return missing

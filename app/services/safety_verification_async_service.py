"""Phase 58: Safety Verification Asynchronous Job Orchestrator (Phase 22 Integration).

Orchestrates background processing of large evidence harvesting and consistency evaluation
without carrying sensitive patient identifiers.
"""

from typing import Any, Dict, Optional

from app.schemas.safety_verification import (
    CollectEvidenceRequest,
    RunVerificationRequest,
)
from app.services.safety_verification_service import (
    SafetyVerificationService,
    get_safety_verification_service,
)


class SafetyVerificationAsyncService:
    """Manages asynchronous verification task execution."""

    def __init__(self, verification_service: Optional[SafetyVerificationService] = None) -> None:
        self.verification_service = verification_service or get_safety_verification_service()

    async def execute_background_evidence_collection(
        self,
        verification_id: str,
        actor_id: str,
        actor_role: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Execute evidence collection in background worker."""
        req = CollectEvidenceRequest(force_refresh=force_refresh)
        items = self.verification_service.collect_evidence(
            verification_id=verification_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "verification_id": verification_id,
            "evidence_count": len(items),
        }

    async def execute_background_verification_run(
        self,
        verification_id: str,
        actor_id: str,
        actor_role: str,
        require_strict_assurance: bool = True,
        require_strict_effectiveness: bool = True,
    ) -> Dict[str, Any]:
        """Execute verification evaluation in background worker."""
        req = RunVerificationRequest(
            require_strict_assurance=require_strict_assurance,
            require_strict_effectiveness=require_strict_effectiveness,
        )
        v = self.verification_service.verify(
            verification_id=verification_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "verification_id": v.verification_id,
            "verification_status": v.verification_status.value,
        }

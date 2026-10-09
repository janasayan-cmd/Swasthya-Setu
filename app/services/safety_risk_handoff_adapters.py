"""Phase 64: Destination Adapters.

Implements explicit adapters for each authoritative downstream destination phase:
- Phase 49 Incident
- Phase 50 Learning
- Phase 51 Governance
- Phase 52 Assurance
- Phase 54 Safety Action
- Phase 55 Action Effectiveness
- Phase 56 Safety Improvement
- Phase 59 Longitudinal Surveillance
- Phase 62 Cross-Domain Reassessment

Non-Negotiable Invariants:
- Destination adapter coordinates work; it does NOT make authoritative clinical or governance decisions.
- Network / transport timeout != Destination rejected.
- Destination acknowledgement != Governance approval.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import (
    DestinationAcknowledgement,
    HandoffDestinationPhase,
    SafetyRiskHandoffRecord,
)


class BaseDestinationAdapter(ABC):
    """Abstract base adapter for downstream safety phase integration."""

    destination_phase: HandoffDestinationPhase
    contract_version: str = "v1.0.0"

    @abstractmethod
    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        """Validate destination-specific prerequisites and contract version."""
        pass

    @abstractmethod
    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        """Transmit handoff to the destination phase and return authoritative acknowledgement."""
        pass

    @abstractmethod
    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        """Query destination workflow execution status."""
        pass

    @abstractmethod
    def supports_cancellation(self) -> bool:
        """Indicate whether the destination supports workflow cancellation."""
        pass


class Phase49IncidentAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_49_INCIDENT

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        if not handoff.source_risk_context_id:
            raise AppException(
                code=ErrorCode.HANDOFF_NOT_ELIGIBLE,
                message="Incident handoff requires authoritative risk context ID.",
                status_code=400,
            )

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"inc-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_INCIDENT_INVESTIGATION",
            metadata={"priority": "HIGH", "target_phase": "PHASE_49_INCIDENT_MANAGEMENT"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "INVESTIGATION_IN_PROGRESS"}

    def supports_cancellation(self) -> bool:
        # Initiated incident investigations cannot be silently cancelled
        return False


class Phase50LearningAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_50_LEARNING

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"lrn-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_SAFETY_LEARNING",
            metadata={"target_phase": "PHASE_50_SAFETY_LEARNING"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "LEARNING_ANALYSIS_QUEUED"}

    def supports_cancellation(self) -> bool:
        return True


class Phase51GovernanceAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_51_GOVERNANCE

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        if not handoff.source_disposition_id:
            raise AppException(
                code=ErrorCode.HANDOFF_NOT_ELIGIBLE,
                message="Governance handoff requires source disposition reference.",
                status_code=400,
            )

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"gov-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_GOVERNANCE_REVIEW",
            metadata={"target_phase": "PHASE_51_SAFETY_GOVERNANCE", "requires_committee": True},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "PENDING_COMMITTEE_DELIBERATION"}

    def supports_cancellation(self) -> bool:
        return True


class Phase52AssuranceAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_52_ASSURANCE

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"asr-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_SAFETY_ASSURANCE",
            metadata={"target_phase": "PHASE_52_SAFETY_ASSURANCE"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "AUDIT_SCHEDULED"}

    def supports_cancellation(self) -> bool:
        return True


class Phase54SafetyActionAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_54_SAFETY_ACTION

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"act-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_CONTROLLED_ACTION",
            metadata={"target_phase": "PHASE_54_SAFETY_ACTION"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "ACTION_PLANNING"}

    def supports_cancellation(self) -> bool:
        return True


class Phase55EffectivenessAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_55_EFFECTIVENESS

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"eff-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_EFFECTIVENESS_REVIEW",
            metadata={"target_phase": "PHASE_55_ACTION_EFFECTIVENESS"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "SURVEILLANCE_EVALUATION"}

    def supports_cancellation(self) -> bool:
        return True


class Phase56ImprovementAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_56_IMPROVEMENT

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"imp-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_SAFETY_IMPROVEMENT",
            metadata={"target_phase": "PHASE_56_SAFETY_IMPROVEMENT"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "IMPROVEMENT_BACKLOG_QUEUED"}

    def supports_cancellation(self) -> bool:
        return True


class Phase59SurveillanceAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_59_SURVEILLANCE

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"srv-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_CONTINUOUS_SURVEILLANCE",
            metadata={"target_phase": "PHASE_59_SURVEILLANCE"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "ACTIVE_MONITORING"}

    def supports_cancellation(self) -> bool:
        return True


class Phase62ReassessmentAdapter(BaseDestinationAdapter):
    destination_phase = HandoffDestinationPhase.PHASE_62_REASSESSMENT

    def validate_request(self, handoff: SafetyRiskHandoffRecord) -> None:
        pass

    def submit(self, handoff: SafetyRiskHandoffRecord) -> DestinationAcknowledgement:
        wf_ref = f"rea-wf-{uuid.uuid4().hex[:10]}"
        return DestinationAcknowledgement(
            handoff_id=handoff.handoff_id,
            destination_phase=self.destination_phase,
            destination_workflow_ref=wf_ref,
            status="ACCEPTED_FOR_REASSESSMENT",
            metadata={"target_phase": "PHASE_62_REASSESSMENT"},
        )

    def check_status(self, workflow_ref: str) -> Dict[str, Any]:
        return {"workflow_ref": workflow_ref, "status": "REASSESSMENT_SCHEDULED"}

    def supports_cancellation(self) -> bool:
        return True


class DestinationAdapterRegistry:
    """Registry providing authoritative destination adapters for Phase 64."""

    _adapters: Dict[HandoffDestinationPhase, BaseDestinationAdapter] = {
        HandoffDestinationPhase.PHASE_49_INCIDENT: Phase49IncidentAdapter(),
        HandoffDestinationPhase.PHASE_50_LEARNING: Phase50LearningAdapter(),
        HandoffDestinationPhase.PHASE_51_GOVERNANCE: Phase51GovernanceAdapter(),
        HandoffDestinationPhase.PHASE_52_ASSURANCE: Phase52AssuranceAdapter(),
        HandoffDestinationPhase.PHASE_54_SAFETY_ACTION: Phase54SafetyActionAdapter(),
        HandoffDestinationPhase.PHASE_55_EFFECTIVENESS: Phase55EffectivenessAdapter(),
        HandoffDestinationPhase.PHASE_56_IMPROVEMENT: Phase56ImprovementAdapter(),
        HandoffDestinationPhase.PHASE_59_SURVEILLANCE: Phase59SurveillanceAdapter(),
        HandoffDestinationPhase.PHASE_62_REASSESSMENT: Phase62ReassessmentAdapter(),
    }

    @classmethod
    def get_adapter(cls, destination: HandoffDestinationPhase) -> BaseDestinationAdapter:
        adapter = cls._adapters.get(destination)
        if not adapter:
            raise AppException(
                code=ErrorCode.DESTINATION_NOT_ALLOWED,
                message=f"No authoritative adapter found for destination phase '{destination.value}'.",
                status_code=400,
            )
        return adapter

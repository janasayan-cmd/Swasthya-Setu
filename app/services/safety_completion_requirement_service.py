"""Phase 65: Safety Completion Requirement Service.

Derives and aggregates the completion requirement register from authoritative
disposition, handoffs, follow-ups, and completion policy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.safety_completion_requirement import (
    CompletionRequirementRecord,
    RequirementStatus,
    RequirementType,
)
from app.schemas.safety_risk_disposition import RiskDispositionRecord, RiskDispositionType
from app.schemas.safety_risk_handoff import HandoffDestinationPhase, SafetyRiskHandoffRecord


class SafetyCompletionRequirementService:
    """Manages the lifecycle and aggregation of the completion requirement register."""

    @staticmethod
    def aggregate_requirements(
        completion_id: str,
        disposition: RiskDispositionRecord,
        handoffs: List[SafetyRiskHandoffRecord],
        policy_version: str = "v1.0.0",
    ) -> List[CompletionRequirementRecord]:
        """Derive explicit completion requirements from authoritative sources."""
        requirements: List[CompletionRequirementRecord] = []

        # 1. Base mandatory governance requirement: Human review
        requirements.append(
            CompletionRequirementRecord(
                completion_id=completion_id,
                requirement_type=RequirementType.REQUIRED_REVIEW,
                description="Governed human completion review and verification of package.",
                originating_phase="PHASE_63",
                originating_record_ref=disposition.disposition_id,
                is_mandatory=True,
                status=RequirementStatus.PENDING,
                provenance="GOVERNED_COMPLETION_POLICY",
                applicable_policy_version=policy_version,
            )
        )

        # 2. Derive requirements from each required handoff
        for handoff in handoffs:
            # Handoff completion requirement
            req_type = RequirementType.REQUIRED_HANDOFF
            dest_str = handoff.destination_phase.value if hasattr(handoff.destination_phase, "value") else str(handoff.destination_phase)

            if handoff.destination_phase == HandoffDestinationPhase.PHASE_49_INCIDENT:
                req_type = RequirementType.REQUIRED_INCIDENT_WORKFLOW
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_51_GOVERNANCE:
                req_type = RequirementType.REQUIRED_GOVERNANCE_WORKFLOW
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_52_ASSURANCE:
                req_type = RequirementType.REQUIRED_ASSURANCE_WORKFLOW
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_54_SAFETY_ACTION:
                req_type = RequirementType.REQUIRED_CONTROLLED_ACTION_WORKFLOW
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_55_EFFECTIVENESS:
                req_type = RequirementType.REQUIRED_EFFECTIVENESS_WORKFLOW
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_59_SURVEILLANCE:
                req_type = RequirementType.REQUIRED_MONITORING_REGISTRATION
            elif handoff.destination_phase == HandoffDestinationPhase.PHASE_62_REASSESSMENT:
                req_type = RequirementType.REQUIRED_REASSESSMENT

            requirements.append(
                CompletionRequirementRecord(
                    completion_id=completion_id,
                    requirement_type=req_type,
                    description=f"Downstream workflow execution and outcome from {dest_str}",
                    originating_phase="PHASE_64",
                    originating_record_ref=handoff.handoff_id,
                    destination_phase=dest_str,
                    is_mandatory=True,
                    status=RequirementStatus.SATISFIED if handoff.state.value == "COMPLETED" else RequirementStatus.PENDING,
                    provenance="PHASE_64_HANDOFF",
                    applicable_policy_version=policy_version,
                )
            )

            # Destination outcome requirement
            requirements.append(
                CompletionRequirementRecord(
                    completion_id=completion_id,
                    requirement_type=RequirementType.REQUIRED_DESTINATION_OUTCOME,
                    description=f"Reconciled authoritative terminal outcome for handoff {handoff.handoff_id}",
                    originating_phase="PHASE_64",
                    originating_record_ref=handoff.handoff_id,
                    destination_phase=dest_str,
                    is_mandatory=True,
                    status=RequirementStatus.SATISFIED if handoff.reconciliation and handoff.reconciliation.get("state") == "MATCHED" else RequirementStatus.PENDING,
                    provenance="PHASE_64_OUTCOME",
                    applicable_policy_version=policy_version,
                )
            )

        # 3. Derive requirements from disposition type specifics
        if disposition.disposition_type == RiskDispositionType.ADDITIONAL_EVIDENCE_REQUIRED:
            requirements.append(
                CompletionRequirementRecord(
                    completion_id=completion_id,
                    requirement_type=RequirementType.REQUIRED_EVIDENCE,
                    description="Additional clinical evidence verification as mandated by Phase 63 disposition.",
                    originating_phase="PHASE_63",
                    originating_record_ref=disposition.disposition_id,
                    is_mandatory=True,
                    status=RequirementStatus.PENDING,
                    provenance="PHASE_63_DISPOSITION",
                    applicable_policy_version=policy_version,
                )
            )
        elif disposition.disposition_type == RiskDispositionType.CONTINUE_MONITORING:
            requirements.append(
                CompletionRequirementRecord(
                    completion_id=completion_id,
                    requirement_type=RequirementType.REQUIRED_MONITORING_REGISTRATION,
                    description="Post-closure surveillance registration through Phase 59 contract.",
                    originating_phase="PHASE_63",
                    originating_record_ref=disposition.disposition_id,
                    is_mandatory=True,
                    status=RequirementStatus.PENDING,
                    provenance="PHASE_63_DISPOSITION",
                    applicable_policy_version=policy_version,
                )
            )

        return requirements

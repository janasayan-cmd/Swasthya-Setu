"""Phase 65: Safety Completion Package Service.

Assembles the 22-item authorized completion package for governance review and closure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.safety_completion_package import CompletionPackageRecord
from app.schemas.safety_completion_readiness import ReadinessEvaluationRecord
from app.schemas.safety_risk_disposition import RiskDispositionRecord
from app.schemas.safety_risk_handoff import SafetyRiskHandoffRecord
from app.schemas.safety_workflow_completion import SafetyWorkflowCompletionRecord


class SafetyCompletionPackageService:
    """Generates immutable, traceable completion packages."""

    @staticmethod
    def generate_package(
        completion: SafetyWorkflowCompletionRecord,
        disposition: RiskDispositionRecord,
        handoffs: List[SafetyRiskHandoffRecord],
        readiness: ReadinessEvaluationRecord,
    ) -> CompletionPackageRecord:
        """Assemble the 22-point authorized completion package."""
        handoff_inv = [
            {
                "handoff_id": h.handoff_id,
                "destination_phase": h.destination_phase.value if hasattr(h.destination_phase, "value") else str(h.destination_phase),
                "state": h.state.value if hasattr(h.state, "value") else str(h.state),
                "retry_count": h.retry_count,
            }
            for h in handoffs
        ]

        dest_outcomes = [
            {
                "outcome_ref_id": o.get("outcome_ref_id"),
                "destination_phase": o.get("destination_phase"),
                "status": o.get("authoritative_destination_status"),
                "is_terminal": o.get("is_terminal"),
                "is_reconciled": o.get("is_reconciled"),
            }
            for o in completion.outcomes
        ]

        fups = [
            {
                "follow_up_id": f.get("follow_up_id"),
                "destination_phase": f.get("destination_phase"),
                "description": f.get("description"),
                "status": f.get("status"),
            }
            for f in completion.follow_ups
        ]

        monitoring_refs = [
            h.acknowledgement.destination_workflow_ref
            for h in handoffs
            if str(h.destination_phase).endswith("PHASE_59_SURVEILLANCE") and h.acknowledgement
        ]

        reassessment_refs = [
            h.acknowledgement.destination_workflow_ref
            for h in handoffs
            if str(h.destination_phase).endswith("PHASE_62_REASSESSMENT") and h.acknowledgement
        ]

        return CompletionPackageRecord(
            completion_id=completion.completion_id,
            package_revision=f"v{completion.version}.0.0",
            source_review_id=completion.source_review_id,
            source_disposition_id=completion.source_disposition_id,
            source_disposition_revision=completion.source_revision,
            source_risk_context_id=completion.source_risk_context_id,
            required_handoff_inventory=handoff_inv,
            handoff_status_summary={
                "total": len(handoffs),
                "completed": readiness.completed_handoffs,
                "pending": readiness.pending_handoffs,
            },
            destination_outcome_summary=dest_outcomes,
            outcome_reconciliation_status="RECONCILED" if readiness.pending_outcomes == 0 else "PENDING",
            requirement_register_summary={
                "total": readiness.total_requirements,
                "satisfied": readiness.satisfied_requirements,
                "pending": readiness.pending_requirements,
                "blocked": readiness.blocked_requirements,
            },
            evidence_completeness_summary={
                "missing_evidence_count": len(readiness.missing_evidence_refs),
                "missing_evidence_refs": readiness.missing_evidence_refs,
            },
            outstanding_follow_up_obligations=fups,
            unresolved_questions=[],
            conflicts_and_limitations=readiness.limitations,
            version_and_provenance_summary={
                "contract_version": completion.contract_version,
                "applicable_policy_version": completion.applicable_policy_version,
                "provenance_reference": completion.provenance_reference,
            },
            required_monitoring_references=monitoring_refs,
            required_reassessment_references=reassessment_refs,
            readiness_result=readiness.readiness_state.value if hasattr(readiness.readiness_state, "value") else str(readiness.readiness_state),
            blockers_and_reasons=readiness.blockers,
            applicable_policy_version=completion.applicable_policy_version,
            evaluation_timestamp=readiness.evaluated_at,
            authorized_reviewer_requirements={
                "required_roles": ["ADMIN", "CLINICAL_SAFETY_OFFICER"],
                "separation_of_duties_required": True,
            },
            previous_completion_attempts=len(completion.history),
            reopen_or_supersession_history=completion.reopen_history,
            generated_at=datetime.now(timezone.utc),
            generated_by="system",
            is_authoritative=True,
        )

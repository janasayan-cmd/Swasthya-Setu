"""Phase 63: Clinical Safety Review Package Assembly Service.

Constructs the comprehensive 26-item governed review package from Phase 62 risk context,
supporting evidence, question tracking, and longitudinal lifecycle history.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.safety_review_package import SafetyReviewPackage
from app.schemas.safety_risk_review import SafetyRiskReviewRecord


class SafetyReviewPackageService:
    """Assembles authorized review packages for clinical safety reviewers."""

    @classmethod
    def assemble_package(
        cls,
        review: SafetyRiskReviewRecord,
        phase62_assessment: Optional[Any] = None,
    ) -> SafetyReviewPackage:
        """Construct the 26-item review package."""
        # Extract findings and risk context if phase62_assessment is present
        source_findings: List[Dict[str, Any]] = []
        consolidated_findings: List[Dict[str, Any]] = []
        risk_concern = "Governed clinical risk surveillance concern"
        analytical_summary: Dict[str, Any] = {}
        uncertainty: Dict[str, Any] = {"level": "MODERATE", "state": "QUANTIFIED"}

        if phase62_assessment:
            risk_concern = getattr(phase62_assessment, "concern_summary", risk_concern)
            source_findings = [f.model_dump() if hasattr(f, "model_dump") else dict(f) for f in getattr(phase62_assessment, "findings", [])]
            consolidated_findings = [cf.model_dump() if hasattr(cf, "model_dump") else dict(cf) for cf in getattr(phase62_assessment, "consolidated_findings", [])]
            analytical_summary = {
                "cross_domain_correlation": getattr(phase62_assessment, "correlation_outcome", "CORRELATED"),
                "reconciliation_state": getattr(phase62_assessment, "reconciliation_state", "RECONCILED"),
                "risk_priority": getattr(phase62_assessment, "risk_priority", "ROUTINE"),
            }
            uncertainty = {
                "uncertainty_state": getattr(phase62_assessment, "uncertainty_state", "LOW_UNCERTAINTY"),
            }

        # Supporting & counter evidence
        supporting_evidence = [
            e.model_dump() for e in review.evidence_items if not e.is_counter_evidence
        ]
        counter_evidence = [
            e.model_dump() for e in review.evidence_items if e.is_counter_evidence
        ]
        evidence_limitations = [
            lim for e in review.evidence_items for lim in e.limitations
        ]

        # Questions
        unresolved_questions = [
            q.model_dump() for q in review.questions
        ]

        # Dispositions & actions
        previous_decisions = [
            a.model_dump() for a in review.actions
        ]
        previous_dispositions = [
            d.model_dump() for d in review.dispositions
        ]

        # Reopen and reassessment history
        reopen_history = [
            {"reopen_count": review.reopen_count, "reopen_reason": review.reopen_reason}
        ] if review.is_reopened else []

        reassessment_history = [
            h.model_dump() for h in review.history if "REASSESS" in (h.action or "").upper()
        ]

        package = SafetyReviewPackage(
            review_id=review.review_id,
            assessment_id=review.assessment_id,
            risk_context={"assessment_id": review.assessment_id, "state": review.state.value},
            risk_concern=risk_concern,
            source_findings=source_findings,
            consolidated_findings=consolidated_findings,
            analytical_summary=analytical_summary,
            supporting_evidence=supporting_evidence,
            counter_evidence=counter_evidence,
            evidence_limitations=evidence_limitations,
            uncertainty=uncertainty,
            scope=review.scope,
            time_window={"created_at": review.created_at.isoformat(), "current_time": datetime.now(timezone.utc).isoformat()},
            application_version=review.application_version,
            configuration_version=review.configuration_version,
            safety_control_version=review.safety_control_version,
            provenance_metadata={"origin": review.provenance, "creator": review.created_by},
            incident_references=[],
            assurance_references=[],
            effectiveness_references=[],
            surveillance_status="ACTIVE_SURVEILLANCE",
            previous_decisions=previous_decisions,
            previous_dispositions=previous_dispositions,
            reassessment_history=reassessment_history,
            reopen_history=reopen_history,
            unresolved_questions=unresolved_questions,
            recommended_review_path="GOVERNED_HUMAN_TRIAGE",
            routing_requirements=["PHASE_51_GOVERNANCE", "PHASE_59_SURVEILLANCE"],
            generated_at=datetime.now(timezone.utc),
        )

        review.review_package = package
        return package

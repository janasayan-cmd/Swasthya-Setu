"""Phase 63: Clinical Safety Review Package Schemas.

Defines the governed 26-item review package constructed from Phase 62 context,
supporting evidence, unresolved questions, and lifecycle history.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class SafetyReviewPackage(BaseModel):
    """Complete 26-item governed review package for clinical risk reviewers."""

    model_config = ConfigDict(extra="ignore")

    package_id: str = Field(default_factory=lambda: f"pkg-{uuid.uuid4().hex[:12]}")
    review_id: str
    assessment_id: str

    # 1. Risk context
    risk_context: Dict[str, Any] = Field(default_factory=dict)
    # 2. Risk concern
    risk_concern: str = "Unspecified risk concern"
    # 3. Source findings
    source_findings: List[Dict[str, Any]] = Field(default_factory=list)
    # 4. Consolidated findings
    consolidated_findings: List[Dict[str, Any]] = Field(default_factory=list)
    # 5. Analytical summary
    analytical_summary: Dict[str, Any] = Field(default_factory=dict)
    # 6. Supporting evidence
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    # 7. Counter-evidence
    counter_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    # 8. Evidence limitations
    evidence_limitations: List[str] = Field(default_factory=list)
    # 9. Uncertainty
    uncertainty: Dict[str, Any] = Field(default_factory=dict)
    # 10. Scope
    scope: Dict[str, Any] = Field(default_factory=dict)
    # 11. Time window
    time_window: Dict[str, Any] = Field(default_factory=dict)
    # 12. Application version
    application_version: str = "v1.0.0"
    # 13. Configuration version
    configuration_version: str = "v1.0.0"
    # 14. Safety-control version
    safety_control_version: str = "v1.0.0"
    # 15. Source/provenance metadata
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)
    # 16. Incident references
    incident_references: List[str] = Field(default_factory=list)
    # 17. Assurance references
    assurance_references: List[str] = Field(default_factory=list)
    # 18. Effectiveness references
    effectiveness_references: List[str] = Field(default_factory=list)
    # 19. Surveillance status
    surveillance_status: str = "MONITORED"
    # 20. Previous decisions
    previous_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    # 21. Previous dispositions
    previous_dispositions: List[Dict[str, Any]] = Field(default_factory=list)
    # 22. Reassessment history
    reassessment_history: List[Dict[str, Any]] = Field(default_factory=list)
    # 23. Reopen history
    reopen_history: List[Dict[str, Any]] = Field(default_factory=list)
    # 24. Unresolved questions
    unresolved_questions: List[Dict[str, Any]] = Field(default_factory=list)
    # 25. Recommended review path
    recommended_review_path: Optional[str] = None
    # 26. Routing requirements
    routing_requirements: List[str] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

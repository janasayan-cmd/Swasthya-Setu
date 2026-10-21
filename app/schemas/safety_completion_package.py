"""Phase 65: Safety Completion Package Schemas.

Defines schemas for the 22-point authorized completion package.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompletionPackageRecord(BaseModel):
    """Immutable completion package containing all 22 required governance items."""

    model_config = ConfigDict(extra="ignore")

    package_id: str = Field(default_factory=lambda: f"pkg-{uuid.uuid4().hex[:12]}")
    completion_id: str
    package_revision: str = "v1.0.0"

    # 1. Source risk-review reference
    source_review_id: str

    # 2. Source risk-disposition reference and revision
    source_disposition_id: str
    source_disposition_revision: str = "v1.0.0"

    # 3. Applicable risk-context reference
    source_risk_context_id: str

    # 4. Required-handoff inventory
    required_handoff_inventory: List[Dict[str, Any]] = Field(default_factory=list)

    # 5. Handoff status summary
    handoff_status_summary: Dict[str, Any] = Field(default_factory=dict)

    # 6. Destination outcome summary
    destination_outcome_summary: List[Dict[str, Any]] = Field(default_factory=list)

    # 7. Outcome reconciliation status
    outcome_reconciliation_status: str = "RECONCILED"

    # 8. Requirement register summary
    requirement_register_summary: Dict[str, Any] = Field(default_factory=dict)

    # 9. Evidence completeness summary
    evidence_completeness_summary: Dict[str, Any] = Field(default_factory=dict)

    # 10. Outstanding follow-up obligations
    outstanding_follow_up_obligations: List[Dict[str, Any]] = Field(default_factory=list)

    # 11. Unresolved questions
    unresolved_questions: List[str] = Field(default_factory=list)

    # 12. Conflicts and limitations
    conflicts_and_limitations: List[str] = Field(default_factory=list)

    # 13. Version and provenance summary
    version_and_provenance_summary: Dict[str, Any] = Field(default_factory=dict)

    # 14. Required monitoring references
    required_monitoring_references: List[str] = Field(default_factory=list)

    # 15. Required reassessment references
    required_reassessment_references: List[str] = Field(default_factory=list)

    # 16. Completion-readiness result
    readiness_result: str

    # 17. Blockers and reasons
    blockers_and_reasons: List[str] = Field(default_factory=list)

    # 18. Applicable policy version
    applicable_policy_version: str = "v1.0.0"

    # 19. Evaluation timestamp
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 20. Authorized reviewer requirements
    authorized_reviewer_requirements: Dict[str, Any] = Field(default_factory=dict)

    # 21. Previous completion attempts
    previous_completion_attempts: int = 0

    # 22. Reopen or supersession history
    reopen_or_supersession_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Meta
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = "system"
    is_authoritative: bool = True

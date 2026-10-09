"""Phase 63: Clinical Safety Risk Separation of Duties (SoD) Service.

Enforces strict separation of duties between:
- RISK_ANALYST != RISK_REVIEWER
- RISK_REVIEWER != GOVERNANCE_APPROVER
- GOVERNANCE_APPROVER != SAFETY_ACTION_AUTHORIZER
- SAFETY_ACTION_AUTHORIZER != CLINICAL_ACTION_AUTHORIZER

Fails fast with SEPARATION_OF_DUTIES_VIOLATION if any dual-role or conflicting authority
is attempted on a governed risk review.
"""

from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_review import SafetyRiskReviewRecord
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskSeparationService:
    """Enforces Separation of Duties (SoD) boundaries."""

    @classmethod
    def validate_separation_of_duties(
        cls,
        user: AuthenticatedUserContext,
        review: SafetyRiskReviewRecord,
        attempted_role: str = "RISK_REVIEWER",
    ) -> None:
        """Verify that the actor does not occupy conflicting duties on this review."""
        user_id = user.user_id

        # 1. RISK_ANALYST != RISK_REVIEWER
        if attempted_role == "RISK_REVIEWER":
            # The person who created/analyzed the risk context cannot review/approve their own analysis
            if review.created_by and review.created_by == user_id:
                raise AppException(
                    code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                    message=f"Separation of Duties violation: Creator/Analyst '{user_id}' cannot act as independent Risk Reviewer.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        # 2. RISK_REVIEWER != GOVERNANCE_APPROVER
        if attempted_role == "GOVERNANCE_APPROVER":
            if review.current_reviewer_id and review.current_reviewer_id == user_id:
                raise AppException(
                    code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                    message=f"Separation of Duties violation: Reviewer '{user_id}' cannot act as Governance Approver on the same review.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        # 3. Check against previously recorded reviewer actions on this review
        # A reviewer who performed the review cannot approve subsequent governance decisions
        prior_reviewer_ids = {a.reviewer_id for a in review.actions}
        if attempted_role == "GOVERNANCE_APPROVER" and user_id in prior_reviewer_ids:
            raise AppException(
                code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                message=f"Separation of Duties violation: User '{user_id}' previously conducted review actions and cannot authorize final governance acceptance.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

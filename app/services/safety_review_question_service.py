"""Phase 63: Clinical Safety Unresolved-Question Service.

Manages explicit tracking, assignment, resolution, and reopening of questions
relevant to governed risk review without silent backend assumptions.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_review_question import (
    CreateQuestionRequest,
    QuestionStatus,
    ResolveQuestionRequest,
    UnresolvedQuestionRecord,
)
from app.schemas.safety_risk_review import SafetyRiskReviewRecord
from app.schemas.user import AuthenticatedUserContext


class SafetyReviewQuestionService:
    """Manages unresolved questions within a risk review."""

    @classmethod
    def create_question(
        cls,
        review: SafetyRiskReviewRecord,
        request: CreateQuestionRequest,
        user: AuthenticatedUserContext,
    ) -> UnresolvedQuestionRecord:
        """Create a new explicit question tracking an unresolved issue."""
        q_record = UnresolvedQuestionRecord(
            review_id=review.review_id,
            category=request.category,
            question_text=request.question_text,
            created_by=user.user_id,
            assigned_to=request.assigned_to,
            evidence_references=request.evidence_references or [],
            metadata=request.metadata or {},
        )
        review.questions.append(q_record)
        return q_record

    @classmethod
    def resolve_question(
        cls,
        review: SafetyRiskReviewRecord,
        question_id: str,
        request: ResolveQuestionRequest,
        user: AuthenticatedUserContext,
    ) -> UnresolvedQuestionRecord:
        """Mark an unresolved question as resolved with verified rationale."""
        target_q: Optional[UnresolvedQuestionRecord] = None
        for q in review.questions:
            if q.question_id == question_id:
                target_q = q
                break

        if not target_q:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Question '{question_id}' not found in review '{review.review_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if target_q.status == QuestionStatus.RESOLVED:
            return target_q

        target_q.status = QuestionStatus.RESOLVED
        target_q.resolution_summary = request.resolution_summary
        target_q.resolved_by = user.user_id
        target_q.resolved_at = datetime.now(timezone.utc)
        if request.evidence_references:
            target_q.evidence_references.extend(request.evidence_references)

        return target_q

    @classmethod
    def reopen_question(
        cls,
        review: SafetyRiskReviewRecord,
        question_id: str,
        user: AuthenticatedUserContext,
    ) -> UnresolvedQuestionRecord:
        """Reopen a previously resolved question due to new counter-evidence or conflict."""
        target_q: Optional[UnresolvedQuestionRecord] = None
        for q in review.questions:
            if q.question_id == question_id:
                target_q = q
                break

        if not target_q:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message=f"Question '{question_id}' not found in review '{review.review_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        target_q.status = QuestionStatus.REOPENED
        target_q.reopened_at = datetime.now(timezone.utc)
        target_q.resolution_summary = None
        target_q.resolved_by = None
        target_q.resolved_at = None
        return target_q

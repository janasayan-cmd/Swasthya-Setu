"""Phase 63: Clinical Safety Review Concurrency Service.

Provides optimistic concurrency control and version protection for safety risk reviews.
Fails fast with CONCURRENCY_CONFLICT if an update is attempted against a stale review state.
"""

from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_review import SafetyRiskReviewRecord


class SafetyRiskReviewConcurrencyService:
    """Manages optimistic concurrency checking and version incrementing."""

    @classmethod
    def check_version(
        cls,
        review: SafetyRiskReviewRecord,
        expected_version_tag: Optional[int],
    ) -> None:
        """Validate that the incoming request's expected version matches current version."""
        if expected_version_tag is not None and review.version_tag != expected_version_tag:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=f"Concurrency conflict on review '{review.review_id}': expected version {expected_version_tag}, but current version is {review.version_tag}.",
                status_code=status.HTTP_409_CONFLICT,
            )

    @classmethod
    def increment_version(cls, review: SafetyRiskReviewRecord) -> int:
        """Increment version tag after state modification."""
        review.version_tag += 1
        return review.version_tag

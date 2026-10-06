"""Phase 50: Safety Learning Trend Calculation Service.

Calculates event/incident frequencies, failure rates with strict denominator
validation, and handles small-sample thresholds without overinterpretation.
"""

import logging
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import SafetyLearningInsufficientDataException, SafetyLearningRateUnavailableException
from app.schemas.safety_analysis import TrendMetric

logger = logging.getLogger("app.safety_trend_service")


class SafetyTrendService:
    """Service governing trend calculations and denominator integrity."""

    def calculate_trend_metric(
        self,
        metric_name: str,
        count: int,
        denominator: Optional[int] = None,
        time_window_label: Optional[str] = None,
        require_valid_rate: bool = False,
    ) -> TrendMetric:
        """Calculate a single trend metric, ensuring denominator integrity."""
        if denominator is not None and denominator > 0:
            rate = round(count / denominator, 4)
            return TrendMetric(
                metric_name=metric_name,
                count=count,
                denominator=denominator,
                rate=rate,
                rate_available=True,
                time_window_label=time_window_label,
            )
        elif require_valid_rate:
            raise SafetyLearningRateUnavailableException(
                f"Rate calculation unavailable for '{metric_name}': valid positive denominator is required."
            )
        else:
            return TrendMetric(
                metric_name=metric_name,
                count=count,
                denominator=None,
                rate=None,
                rate_available=False,
                time_window_label=time_window_label,
            )

    def validate_sample_sufficiency(self, count: int, min_required: Optional[int] = None) -> bool:
        """Check if sample size is sufficient to infer patterns rather than random noise."""
        threshold = min_required if min_required is not None else settings.SAFETY_LEARNING_MIN_SAMPLE_SIZE
        return count >= threshold


# Global singleton
safety_trend_service = SafetyTrendService()

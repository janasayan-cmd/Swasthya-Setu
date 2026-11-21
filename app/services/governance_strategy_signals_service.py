"""Phase 79: Strategic Change Signals Service.

Detects, tracks, and escalates strategic change signals arising from recurring
milestone delays, persistent dependency failures, declining capability indicators,
or operational adoption gaps.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_signals import (
    CreateSignalRequest,
    ReviewSignalRequest,
    SignalCategory,
    SignalDisposition,
    SignalSeverity,
    StrategicChangeSignalRecord,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategySignalsService:
    """Manages strategic change signal detection, severity evaluation, and risk escalation."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def record_signal(
        self,
        tenant_id: str,
        request: CreateSignalRequest,
    ) -> StrategicChangeSignalRecord:
        signal_id = f"SCS-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicChangeSignalRecord(
            signal_id=signal_id,
            tenant_id=tenant_id,
            category=request.category,
            affected_roadmap_ids=request.affected_roadmap_ids,
            source_references=request.source_references or [],
            detection_rule=request.detection_rule,
            observation_period=request.observation_period,
            severity=request.severity,
            evidence_limitations=request.evidence_limitations or "",
            strategic_implication=request.strategic_implication,
            recommended_destination=request.recommended_destination,
            disposition=SignalDisposition.ACTIVE,
            reviewed_by=None,
            review_notes=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            detected_at=now_str,
        )
        return self.repository.save_signal(record)

    def review_signal(
        self,
        tenant_id: str,
        reviewer_id: str,
        signal_id: str,
        request: ReviewSignalRequest,
    ) -> StrategicChangeSignalRecord:
        signal = self.repository.get_signal(signal_id)
        if not signal or signal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SIGNAL_NOT_FOUND,
                message=f"Strategic change signal '{signal_id}' was not found.",
                status_code=404,
            )

        updated = signal.model_copy(
            update={
                "disposition": request.disposition,
                "reviewed_by": reviewer_id,
                "review_notes": request.review_notes,
            }
        )
        return self.repository.save_signal(updated)

    def escalate_signal_to_phase_63(
        self,
        tenant_id: str,
        reviewer_id: str,
        signal_id: str,
        risk_rationale: str,
    ) -> StrategicChangeSignalRecord:
        """Escalates a strategic change signal indicating clinical safety implications to Phase 63."""
        signal = self.repository.get_signal(signal_id)
        if not signal or signal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SIGNAL_NOT_FOUND,
                message=f"Strategic change signal '{signal_id}' was not found.",
                status_code=404,
            )

        notes = f"Escalated to Phase 63 Clinical Risk Governance by {reviewer_id}: {risk_rationale}"
        updated = signal.model_copy(
            update={
                "disposition": SignalDisposition.ESCALATED_PHASE_63,
                "reviewed_by": reviewer_id,
                "review_notes": notes,
            }
        )
        return self.repository.save_signal(updated)

    def get_signal(
        self,
        tenant_id: str,
        signal_id: str,
    ) -> StrategicChangeSignalRecord:
        signal = self.repository.get_signal(signal_id)
        if not signal or signal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SIGNAL_NOT_FOUND,
                message=f"Strategic change signal '{signal_id}' was not found.",
                status_code=404,
            )
        return signal

    def list_signals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[SignalCategory] = None,
        severity: Optional[SignalSeverity] = None,
        disposition: Optional[SignalDisposition] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicChangeSignalRecord]:
        return self.repository.list_signals(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            category=category,
            severity=severity,
            disposition=disposition,
            skip=skip,
            limit=limit,
        )

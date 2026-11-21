"""Phase 79: Strategic Execution Monitoring Service.

Synchronizes and evaluates execution health of approved Phase 78 strategic roadmaps,
objectives, and milestones against upstream delivery and adoption evidence.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
    CreateExecutionMonitoringRequest,
    MonitoredWorkflowType,
    MonitoringHealthStatus,
    ReconcileExecutionMonitoringRequest,
    StrategicExecutionMonitoringRecord,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyExecutionMonitoringService:
    """Manages strategic execution monitoring, evidence freshness, and synchronization."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def create_monitoring_record(
        self,
        tenant_id: str,
        request: CreateExecutionMonitoringRequest,
    ) -> StrategicExecutionMonitoringRecord:
        existing = self.repository.get_monitoring_by_item(
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            monitored_item_type=request.monitored_item_type,
            monitored_item_id=request.monitored_item_id,
        )
        now_str = _get_utc_now_str()
        freshness = request.evidence_freshness_timestamp or now_str

        if existing:
            # Update existing record
            updated = existing.model_copy(
                update={
                    "source_status": request.source_status,
                    "health_status": request.health_status,
                    "evidence_freshness_timestamp": freshness,
                    "analytical_observation": request.analytical_observation or existing.analytical_observation,
                    "last_synchronized_at": now_str,
                }
            )
            return self.repository.save_monitoring_record(updated)

        monitoring_id = f"SEM-{uuid.uuid4().hex[:8].upper()}"
        record = StrategicExecutionMonitoringRecord(
            monitoring_id=monitoring_id,
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            monitored_item_type=request.monitored_item_type,
            monitored_item_id=request.monitored_item_id,
            source_status=request.source_status,
            health_status=request.health_status,
            evidence_freshness_timestamp=freshness,
            is_stale=False,
            analytical_observation=request.analytical_observation or "",
            detected_issue_count=0,
            last_synchronized_at=now_str,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
        )
        return self.repository.save_monitoring_record(record)

    def reconcile_monitoring_record(
        self,
        tenant_id: str,
        monitoring_id: str,
        request: ReconcileExecutionMonitoringRequest,
    ) -> StrategicExecutionMonitoringRecord:
        record = self.repository.get_monitoring_record(monitoring_id)
        if not record or record.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.EXECUTION_MONITOR_RECORD_NOT_FOUND,
                message=f"Strategic execution monitoring record '{monitoring_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        freshness = request.evidence_freshness_timestamp or record.evidence_freshness_timestamp

        updated = record.model_copy(
            update={
                "source_status": request.source_status,
                "health_status": request.health_status,
                "analytical_observation": request.analytical_observation if request.analytical_observation is not None else record.analytical_observation,
                "detected_issue_count": request.detected_issue_count if request.detected_issue_count is not None else record.detected_issue_count,
                "evidence_freshness_timestamp": freshness,
                "is_stale": request.health_status == MonitoringHealthStatus.STALE_EVIDENCE,
                "last_synchronized_at": now_str,
            }
        )
        return self.repository.save_monitoring_record(updated)

    def get_monitoring_record(
        self,
        tenant_id: str,
        monitoring_id: str,
    ) -> StrategicExecutionMonitoringRecord:
        record = self.repository.get_monitoring_record(monitoring_id)
        if not record or record.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.EXECUTION_MONITOR_RECORD_NOT_FOUND,
                message=f"Strategic execution monitoring record '{monitoring_id}' was not found.",
                status_code=404,
            )
        return record

    def list_monitoring_records(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        monitored_item_type: Optional[MonitoredWorkflowType] = None,
        health_status: Optional[MonitoringHealthStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicExecutionMonitoringRecord]:
        return self.repository.list_monitoring_records(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            monitored_item_type=monitored_item_type,
            health_status=health_status,
            skip=skip,
            limit=limit,
        )

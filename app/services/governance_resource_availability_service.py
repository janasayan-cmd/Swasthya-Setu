"""Phase 86: Resource Availability Evidence Service.

Ingests, records, and evaluates resource availability observations.
Explicitly preserves uncertainty — missing data = UNKNOWN, never AVAILABLE.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_common import ResourceAvailabilityStatus
from app.schemas.governance_resource_availability import (
    ResourceAvailabilityObservationRecord,
    ResourceAvailabilitySummary,
    SubmitAvailabilityObservationRequest,
)


class GovernanceResourceAvailabilityService:

    STALE_THRESHOLD_HOURS = 24

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def submit_observation(
        self, tenant_id: str, resource_id: str, user_id: str, request: SubmitAvailabilityObservationRequest
    ) -> ResourceAvailabilityObservationRecord:
        resource = self.repo.get_resource(resource_id, tenant_id)
        if not resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource '{resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        obs_time = request.observation_timestamp or now
        record = ResourceAvailabilityObservationRecord(
            observation_id=f"obs-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            resource_id=resource_id,
            source_system=request.source_system,
            observed_status=request.observed_status,
            observation_timestamp=obs_time,
            verification_timestamp=now,
            data_freshness_minutes=int((now - obs_time).total_seconds() / 60),
            evidence_ref=request.evidence_ref,
            organizational_scope=request.organizational_scope,
            source_reliability=request.source_reliability,
            failure_details=request.failure_details,
            limitation_details=request.limitation_details,
            recorded_by=user_id,
            created_at=now,
        )
        return self.repo.save_observation(record)

    def get_observation(self, tenant_id: str, observation_id: str) -> ResourceAvailabilityObservationRecord:
        record = self.repo.get_observation(observation_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.AVAILABILITY_OBSERVATION_NOT_FOUND,
                message=f"Availability observation '{observation_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_observations(self, tenant_id: str, resource_id: Optional[str] = None) -> List[ResourceAvailabilityObservationRecord]:
        return self.repo.list_observations(tenant_id, resource_id)

    def get_resource_availability_summary(self, tenant_id: str, resource_id: str) -> ResourceAvailabilitySummary:
        resource = self.repo.get_resource(resource_id, tenant_id)
        if not resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource '{resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        all_obs = self.repo.list_observations(tenant_id, resource_id)
        latest = self.repo.get_latest_observation(resource_id, tenant_id)

        if not latest:
            return ResourceAvailabilitySummary(
                resource_id=resource_id,
                resource_name=resource.resource_name,
                tenant_id=tenant_id,
                latest_status=ResourceAvailabilityStatus.UNKNOWN,
                observation_count=0,
                is_stale=True,
                conflict_detected=False,
            )

        now = datetime.utcnow()
        is_stale = (now - latest.observation_timestamp) > timedelta(hours=self.STALE_THRESHOLD_HOURS)

        # Detect conflicting observations in the last hour
        recent_obs = [
            o for o in all_obs
            if (now - o.observation_timestamp) < timedelta(hours=1)
        ]
        statuses = {o.observed_status for o in recent_obs}
        conflict_detected = (
            len(statuses) > 1
            and ResourceAvailabilityStatus.AVAILABLE_VERIFIED in statuses
            and (ResourceAvailabilityStatus.UNAVAILABLE in statuses or ResourceAvailabilityStatus.DEGRADED in statuses)
        )

        effective_status = latest.observed_status
        if is_stale:
            effective_status = ResourceAvailabilityStatus.STALE
        elif conflict_detected:
            effective_status = ResourceAvailabilityStatus.CONFLICTING

        return ResourceAvailabilitySummary(
            resource_id=resource_id,
            resource_name=resource.resource_name,
            tenant_id=tenant_id,
            latest_status=effective_status,
            last_observation_at=latest.observation_timestamp,
            observation_count=len(all_obs),
            is_stale=is_stale,
            conflict_detected=conflict_detected,
        )


_availability_service: Optional[GovernanceResourceAvailabilityService] = None


def get_governance_resource_availability_service() -> GovernanceResourceAvailabilityService:
    global _availability_service
    if _availability_service is None:
        _availability_service = GovernanceResourceAvailabilityService(
            get_governance_resource_dependency_repository()
        )
    return _availability_service

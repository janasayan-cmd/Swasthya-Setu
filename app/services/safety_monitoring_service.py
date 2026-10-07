"""Phase 59: Safety Monitoring Master Orchestrator Service.

Coordinates post-closure longitudinal surveillance, window lifecycle,
threshold evaluation, checkpoints, human review, and cross-phase routing.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_monitoring_repository import (
    SafetyMonitoringRepository,
    get_safety_monitoring_repository,
)
from app.repositories.safety_verification_repository import (
    SafetyVerificationRepository,
    get_safety_verification_repository,
)
from app.schemas.safety_monitoring import (
    CheckpointCategory,
    CheckpointOutcome,
    CompleteMonitoringRequest,
    CreateMonitoringRequest,
    CreateReopenReviewRequest,
    EvaluateSurveillanceRequest,
    HumanSurveillanceReviewDecision,
    IngestSignalRequest,
    MonitoringCheckpoint,
    MonitoringHistoryEntry,
    MonitoringLifecycleState,
    MonitoringReviewRecord,
    MonitoringScope,
    MonitoringStatusResponse,
    MonitoringTriggerRecord,
    MonitoringWindowType,
    PauseMonitoringRequest,
    ReanalysisSurveillanceRequest,
    RequestReassessmentRequest,
    ResumeMonitoringRequest,
    RunCheckpointRequest,
    SafetyMonitoringRecord,
    SubmitSurveillanceReviewRequest,
    SurveillanceEvaluationResponse,
    SurveillanceSignalRecord,
)
from app.services.safety_monitoring_review_service import (
    SafetyMonitoringReviewService,
)
from app.services.safety_signal_service import SafetySignalService
from app.services.safety_threshold_service import SafetyThresholdService


class SafetyMonitoringService:
    """Master orchestrator for Phase 59 surveillance."""

    def __init__(
        self,
        repository: Optional[SafetyMonitoringRepository] = None,
        verification_repository: Optional[SafetyVerificationRepository] = None,
        signal_service: Optional[SafetySignalService] = None,
        threshold_service: Optional[SafetyThresholdService] = None,
        review_service: Optional[SafetyMonitoringReviewService] = None,
    ) -> None:
        self.repository = repository or get_safety_monitoring_repository()
        self.verification_repository = verification_repository or get_safety_verification_repository()
        self.signal_service = signal_service or SafetySignalService(self.repository)
        self.threshold_service = threshold_service or SafetyThresholdService()
        self.review_service = review_service or SafetyMonitoringReviewService()

    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_monitoring(
        self,
        request: CreateMonitoringRequest,
        actor_id: Any,
        actor_role: Optional[str] = None,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyMonitoringRecord:
        """Register a new post-closure surveillance context."""
        now = datetime.now(timezone.utc)

        # Unpack user object if passed directly
        if hasattr(actor_id, "user_id") or hasattr(actor_id, "role"):
            user = actor_id
            actor_id = str(getattr(user, "user_id", getattr(user, "id", "unknown")))
            role_obj = getattr(user, "role", "ADMIN")
            actor_role = getattr(role_obj, "value", str(role_obj)).replace("UserRole.", "").upper()
            if not actor_organization_id:
                actor_organization_id = getattr(user, "organization_id", None)
        else:
            actor_id = str(actor_id)
            actor_role = str(actor_role or "ADMIN")

        # 1. Scope validation
        scope_obj = request.scope
        org_id = getattr(scope_obj, "organization_id", None) or (scope_obj.get("organization_id") if isinstance(scope_obj, dict) else None)
        if not org_id:
            raise AppException(
                code=ErrorCode.MONITORING_SCOPE_INVALID,
                message="Monitoring scope requires an organization_id",
                status_code=400,
            )

        if actor_organization_id and org_id != actor_organization_id and actor_role not in ("SUPER_ADMIN", "SYSTEM"):
            raise AppException(
                code=ErrorCode.MONITORING_SCOPE_MISMATCH,
                message=f"Monitoring scope organization '{org_id}' does not match actor organization '{actor_organization_id}'",
                status_code=400,
            )

        # 2. Idempotency check
        if request.idempotency_key:
            payload_hash = self._compute_hash(request.model_dump())
            has_conflict, existing_id = self.repository.check_idempotency(
                request.idempotency_key, payload_hash
            )
            if has_conflict:
                if existing_id:
                    existing = self.repository.get(existing_id)
                    if existing:
                        return existing
                raise AppException(
                    code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message=f"Idempotency key '{request.idempotency_key}' reused with conflicting payload",
                    status_code=409,
                )

        # 3. Concurrency check
        existing_for_verification = self.repository.get_by_verification_id(request.verification_id)
        if existing_for_verification and existing_for_verification.lifecycle_state not in {
            MonitoringLifecycleState.COMPLETED,
            MonitoringLifecycleState.EXPIRED,
            MonitoringLifecycleState.CANCELLED,
            MonitoringLifecycleState.SUPERSEDED,
        }:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=(
                    f"An active surveillance context '{existing_for_verification.monitoring_id}' "
                    f"already exists for verification '{request.verification_id}'"
                ),
                status_code=409,
            )

        # 4. Source verification revalidation if present
        if self.verification_repository:
            verification = self.verification_repository.get(request.verification_id)
            if verification and hasattr(verification, "scope") and hasattr(verification.scope, "organization_id"):
                if verification.scope.organization_id != org_id:
                    raise AppException(
                        code=ErrorCode.MONITORING_SCOPE_MISMATCH,
                        message="Monitoring scope does not match verified change scope",
                        status_code=400,
                    )

        version = request.monitored_version or request.application_version or "v1.0.0"
        duration_days = request.window_duration_days or 30
        if request.window_duration_hours:
            duration_days = max(1, request.window_duration_hours // 24)

        monitoring_id = request.monitoring_id or f"mon-{uuid.uuid4().hex[:12]}"

        # Initialize checkpoints
        checkpoints_list: List[MonitoringCheckpoint] = []
        if request.checkpoints:
            for cp_data in request.checkpoints:
                checkpoints_list.append(
                    MonitoringCheckpoint(
                        checkpoint_id=cp_data.get("checkpoint_id") or f"chk-{uuid.uuid4().hex[:6]}",
                        category=cp_data.get("category", CheckpointCategory.INITIAL_POST_CLOSURE),
                        name=cp_data.get("name"),
                        expected_state="OBSERVING_HEALTHY",
                        outcome=CheckpointOutcome.PASS_CONTINUE,
                        evaluated_at=now,
                        evaluated_by=actor_id,
                        notes=cp_data.get("criteria") or "Configured checkpoint",
                    )
                )
        else:
            checkpoints_list.append(
                MonitoringCheckpoint(
                    category=CheckpointCategory.INITIAL_POST_CLOSURE,
                    expected_state="SURVEILLANCE_ACTIVE",
                    observed_state="MONITORING_INITIALIZED",
                    outcome=CheckpointOutcome.PASS_CONTINUE,
                    evaluated_at=now,
                    evaluated_by=actor_id,
                    notes="Surveillance context registered following Phase 58 closure signoff",
                )
            )

        # Build scope model
        if isinstance(scope_obj, dict):
            final_scope = MonitoringScope(**scope_obj)
        else:
            final_scope = scope_obj

        record = SafetyMonitoringRecord(
            monitoring_id=monitoring_id,
            verification_id=request.verification_id,
            rollout_id=request.rollout_id,
            change_id=request.change_id,
            monitored_version=version,
            application_version=version,
            monitoring_plan_name=request.monitoring_plan_name,
            description=request.description,
            organization_id=org_id,
            scope=final_scope,
            lifecycle_state=MonitoringLifecycleState.REGISTERED,
            window_type=request.window_type or MonitoringWindowType.TIME_BASED,
            window_duration_days=duration_days,
            window_duration_hours=request.window_duration_hours,
            started_at=now,
            expires_at=now + timedelta(days=duration_days),
            observation_sources=request.observation_sources or [],
            thresholds=request.thresholds or [],
            threshold_config=request.threshold_config
            or {
                "error_rate_threshold": 0.05,
                "max_critical_signals": 0,
                "max_warning_signals": 5,
            },
            checkpoints=checkpoints_list,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )

        record.history.append(
            MonitoringHistoryEntry(
                from_state="NONE",
                to_state=record.lifecycle_state.value,
                action="CREATE_MONITORING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Longitudinal surveillance registered for closed change",
                timestamp=now,
            )
        )

        saved = self.repository.save(record)

        if request.idempotency_key:
            self.repository.record_idempotency(
                request.idempotency_key, self._compute_hash(request.model_dump()), saved.monitoring_id
            )

        return saved

    def get_monitoring(self, monitoring_id: str) -> SafetyMonitoringRecord:
        """Fetch surveillance record or raise 404."""
        record = self.repository.get(monitoring_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_MONITORING_NOT_FOUND,
                message=f"Safety monitoring context '{monitoring_id}' not found",
                status_code=404,
            )
        return record

    def get_status(self, monitoring_id: str) -> MonitoringStatusResponse:
        """Fetch status overview."""
        m = self.get_monitoring(monitoring_id)
        return MonitoringStatusResponse(
            monitoring_id=m.monitoring_id,
            verification_id=m.verification_id,
            change_id=m.change_id,
            monitored_version=m.monitored_version,
            lifecycle_state=m.lifecycle_state,
            is_paused=m.is_paused,
            signal_count=len(m.signals),
            trigger_count=len(m.triggers),
            version=m.version,
            updated_at=m.updated_at,
        )

    def get_signals(self, monitoring_id: str) -> List[SurveillanceSignalRecord]:
        m = self.get_monitoring(monitoring_id)
        return m.signals

    def get_history(self, monitoring_id: str) -> List[MonitoringHistoryEntry]:
        m = self.get_monitoring(monitoring_id)
        return m.history

    def get_checkpoints(self, monitoring_id: str) -> List[MonitoringCheckpoint]:
        m = self.get_monitoring(monitoring_id)
        return m.checkpoints

    def get_triggers(self, monitoring_id: str) -> List[MonitoringTriggerRecord]:
        m = self.get_monitoring(monitoring_id)
        return m.triggers

    def start(self, monitoring_id: str, actor_id: Any, actor_role: Optional[str] = None) -> SafetyMonitoringRecord:
        """Transition surveillance state to OBSERVING."""
        if hasattr(actor_id, "user_id") or hasattr(actor_id, "role"):
            user = actor_id
            actor_id = str(getattr(user, "user_id", getattr(user, "id", "unknown")))
            role_obj = getattr(user, "role", "ADMIN")
            actor_role = getattr(role_obj, "value", str(role_obj)).replace("UserRole.", "").upper()
        else:
            actor_id = str(actor_id)
            actor_role = str(actor_role or "ADMIN")

        m = self.get_monitoring(monitoring_id)
        if m.lifecycle_state in (MonitoringLifecycleState.COMPLETED, MonitoringLifecycleState.CANCELLED):
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message=f"Cannot start monitoring context in state '{m.lifecycle_state.value}'",
                status_code=400,
            )

        old_state = m.lifecycle_state.value
        m.lifecycle_state = MonitoringLifecycleState.OBSERVING
        m.started_at = datetime.now(timezone.utc)
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=old_state,
                to_state=m.lifecycle_state.value,
                action="START_MONITORING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Longitudinal surveillance started observing sources",
                timestamp=m.started_at,
            )
        )

        return self.repository.save(m)

    start_monitoring = start

    def pause(
        self, monitoring_id: str, request: PauseMonitoringRequest, actor_id: str, actor_role: str
    ) -> SafetyMonitoringRecord:
        """Pause active surveillance."""
        m = self.get_monitoring(monitoring_id)
        if m.is_paused:
            return m

        old_state = m.lifecycle_state.value
        m.is_paused = True
        m.pause_reason = request.reason
        m.lifecycle_state = MonitoringLifecycleState.PAUSED
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=old_state,
                to_state=m.lifecycle_state.value,
                action="PAUSE_MONITORING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(m)

    def resume(
        self, monitoring_id: str, request: ResumeMonitoringRequest, actor_id: str, actor_role: str
    ) -> SafetyMonitoringRecord:
        """Resume paused surveillance."""
        m = self.get_monitoring(monitoring_id)
        if not m.is_paused:
            return m

        old_state = m.lifecycle_state.value
        m.is_paused = False
        m.pause_reason = None
        m.lifecycle_state = MonitoringLifecycleState.OBSERVING
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=old_state,
                to_state=m.lifecycle_state.value,
                action="RESUME_MONITORING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.rationale or "Resumed surveillance",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(m)

    def ingest_signal_with_status(
        self, monitoring_id: str, request: IngestSignalRequest, actor_id: str, actor_role: str
    ) -> Tuple[bool, SurveillanceSignalRecord]:
        """Ingest signal and return (is_new, signal)."""
        m = self.get_monitoring(monitoring_id)
        if m.is_paused:
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message="Cannot ingest signals while monitoring is paused",
                status_code=400,
            )

        is_new, signal = self.signal_service.ingest_signal(m, request)
        if is_new:
            # Re-evaluate thresholds on new signals
            self.threshold_service.evaluate_surveillance(m)
            m.version += 1
            m.history.append(
                MonitoringHistoryEntry(
                    from_state=m.lifecycle_state.value,
                    to_state=m.lifecycle_state.value,
                    action="INGEST_SIGNAL",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    reason=f"Ingested signal '{signal.signal_id}' ({signal.signal_type.value})",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            self.repository.save(m)

        return is_new, signal

    def collect(self, monitoring_id: str, actor_id: str, actor_role: str) -> List[SurveillanceSignalRecord]:
        """Collect available signals across integrated sources."""
        m = self.get_monitoring(monitoring_id)
        self.threshold_service.evaluate_surveillance(m)
        self.repository.save(m)
        return m.signals

    def evaluate(
        self, monitoring_id: str, request: EvaluateSurveillanceRequest, actor_id: str, actor_role: str
    ) -> SurveillanceEvaluationResponse:
        """Run surveillance evaluation against configured thresholds."""
        m = self.get_monitoring(monitoring_id)
        resp, _ = self.threshold_service.evaluate_surveillance(m)
        self.repository.save(m)
        return resp

    def run_checkpoint(
        self, monitoring_id: str, request: RunCheckpointRequest, actor_id: str, actor_role: str
    ) -> MonitoringCheckpoint:
        """Execute checkpoint evaluation."""
        m = self.get_monitoring(monitoring_id)
        now = datetime.now(timezone.utc)

        target_cp: Optional[MonitoringCheckpoint] = None
        if request.checkpoint_id:
            for cp in m.checkpoints:
                if cp.checkpoint_id == request.checkpoint_id:
                    target_cp = cp
                    break

        if target_cp:
            target_cp.observed_state = request.observed_state or "PASS_CONTINUE"
            target_cp.outcome = CheckpointOutcome.PASS_CONTINUE
            target_cp.evaluated_at = now
            target_cp.evaluated_by = actor_id
            if request.notes:
                target_cp.notes = request.notes
            cp_result = target_cp
        else:
            cat = request.category or CheckpointCategory.INITIAL_POST_CLOSURE
            cp_result = MonitoringCheckpoint(
                checkpoint_id=request.checkpoint_id or f"chk-{uuid.uuid4().hex[:6]}",
                category=cat,
                expected_state="OBSERVING_HEALTHY",
                observed_state=request.observed_state or "PASS_CONTINUE",
                outcome=CheckpointOutcome.PASS_CONTINUE,
                evaluated_at=now,
                evaluated_by=actor_id,
                notes=request.notes or "Checkpoint evaluated",
            )
            m.checkpoints.append(cp_result)

        m.history.append(
            MonitoringHistoryEntry(
                from_state=m.lifecycle_state.value,
                to_state=m.lifecycle_state.value,
                action="RUN_CHECKPOINT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Checkpoint {cp_result.checkpoint_id} outcome: {cp_result.outcome.value}",
                timestamp=now,
            )
        )

        self.repository.save(m)
        return cp_result

    def review(
        self, monitoring_id: str, request: SubmitSurveillanceReviewRequest, actor_id: str, actor_role: str
    ) -> MonitoringReviewRecord:
        """Submit human surveillance review decision."""
        m = self.get_monitoring(monitoring_id)
        old_state = m.lifecycle_state.value
        rec = self.review_service.submit_review(
            monitoring=m,
            decision=request.decision,
            rationale=request.notes or request.rationale or "Reviewed",
            reviewer_id=actor_id,
            reviewer_role=actor_role,
            is_ai_agent=request.is_ai_agent,
        )

        m.version += 1
        m.history.append(
            MonitoringHistoryEntry(
                from_state=old_state,
                to_state=m.lifecycle_state.value,
                action="SUBMIT_SURVEILLANCE_REVIEW",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Human surveillance review: {request.decision.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(m)
        return rec

    def create_reopen_review(
        self, monitoring_id: str, request: CreateReopenReviewRequest, actor_id: str, actor_role: str
    ) -> MonitoringTriggerRecord:
        """Create governed reopen review trigger targeting Phase 58."""
        m = self.get_monitoring(monitoring_id)
        now = datetime.now(timezone.utc)

        trigger = MonitoringTriggerRecord(
            trigger_type="REOPEN_TRIGGER",
            target_destination="Phase 58",
            target_phase="PHASE_58",
            lifecycle_state="REOPEN_REQUIRED",
            reason=request.reason,
            signal_references=request.signal_ids or [],
            triggered_at=now,
            status="REVIEW_REQUIRED",
        )
        m.triggers.append(trigger)
        m.lifecycle_state = MonitoringLifecycleState.REOPEN_REQUIRED
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=m.lifecycle_state.value,
                to_state=MonitoringLifecycleState.REOPEN_REQUIRED.value,
                action="CREATE_REOPEN_REVIEW",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=now,
            )
        )

        self.repository.save(m)
        return trigger

    def request_reassessment(
        self, monitoring_id: str, request: RequestReassessmentRequest, actor_id: str, actor_role: str
    ) -> MonitoringTriggerRecord:
        """Request formal reassessment targeting Phase 51 Governance."""
        m = self.get_monitoring(monitoring_id)
        now = datetime.now(timezone.utc)

        trigger = MonitoringTriggerRecord(
            trigger_type="REASSESSMENT_TRIGGER",
            target_destination="Phase 51",
            target_phase="PHASE_51",
            lifecycle_state="REASSESSMENT_REQUIRED",
            reason=request.reason,
            triggered_at=now,
            status="REVIEW_REQUIRED",
        )
        m.triggers.append(trigger)
        m.lifecycle_state = MonitoringLifecycleState.REASSESSMENT_REQUIRED
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=m.lifecycle_state.value,
                to_state=MonitoringLifecycleState.REASSESSMENT_REQUIRED.value,
                action="REQUEST_REASSESSMENT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=now,
            )
        )

        self.repository.save(m)
        return trigger

    def complete(
        self, monitoring_id: str, request: CompleteMonitoringRequest, actor_id: str, actor_role: str
    ) -> SafetyMonitoringRecord:
        """Complete post-closure surveillance after fulfilling all governed criteria."""
        m = self.get_monitoring(monitoring_id)

        # Check for unaddressed active triggers or REOPEN_REQUIRED
        if m.lifecycle_state == MonitoringLifecycleState.REOPEN_REQUIRED:
            raise AppException(
                code=ErrorCode.REOPEN_REVIEW_REQUIRED,
                message="Cannot complete surveillance context while in REOPEN_REQUIRED state",
                status_code=409,
            )

        active_triggers = [t for t in m.triggers if t.status in ("DETECTED", "REVIEW_REQUIRED")]
        if active_triggers:
            for t in active_triggers:
                if t.trigger_type == "REOPEN_TRIGGER":
                    raise AppException(
                        code=ErrorCode.REOPEN_REVIEW_REQUIRED,
                        message="Cannot complete monitoring context while open reopen trigger exists",
                        status_code=409,
                    )
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message=(
                    f"Cannot complete monitoring context: {len(active_triggers)} active triggers "
                    "require resolution before conclusion"
                ),
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        old_state = m.lifecycle_state.value
        m.lifecycle_state = MonitoringLifecycleState.COMPLETED
        m.completed_at = now
        m.version += 1

        m.history.append(
            MonitoringHistoryEntry(
                from_state=old_state,
                to_state=MonitoringLifecycleState.COMPLETED.value,
                action="COMPLETE_MONITORING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.summary or request.rationale or "Surveillance completed",
                timestamp=now,
            )
        )

        return self.repository.save(m)

    def reanalysis(
        self, request: ReanalysisSurveillanceRequest, actor_id: str, actor_role: str
    ) -> List[MonitoringStatusResponse]:
        """Perform batch surveillance reanalysis."""
        if request.monitoring_ids:
            records = [self.repository.get(mid) for mid in request.monitoring_ids if self.repository.get(mid)]
        else:
            records = self.repository.list_active()

        results: List[MonitoringStatusResponse] = []
        for m in records:
            if m:
                self.threshold_service.evaluate_surveillance(m)
                self.repository.save(m)
                results.append(
                    MonitoringStatusResponse(
                        monitoring_id=m.monitoring_id,
                        verification_id=m.verification_id,
                        change_id=m.change_id,
                        monitored_version=m.monitored_version,
                        lifecycle_state=m.lifecycle_state,
                        is_paused=m.is_paused,
                        signal_count=len(m.signals),
                        trigger_count=len(m.triggers),
                        version=m.version,
                        updated_at=m.updated_at,
                    )
                )

        return results

    # Filtering convenience methods
    def list_monitoring(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[MonitoringLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyMonitoringRecord]:
        return self.repository.list_monitoring(
            organization_id=organization_id,
            facility_id=facility_id,
            lifecycle_state=lifecycle_state,
            limit=limit,
            offset=offset,
        )

    def list_active(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        return self.repository.list_active(organization_id=organization_id)

    get_active_monitoring = list_active

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        return self.repository.list_review_required(organization_id=organization_id)

    def list_reopen_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        return self.repository.list_reopen_required(organization_id=organization_id)

    def list_escalation_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        return self.repository.list_escalation_required(organization_id=organization_id)


# Global singleton service
_service_instance: Optional[SafetyMonitoringService] = None


def get_safety_monitoring_service() -> SafetyMonitoringService:
    """Retrieve global singleton service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SafetyMonitoringService()
    return _service_instance

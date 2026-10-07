"""Phase 58: Safety Verification Core Service.

Authoritative orchestrator for post-rollout change verification, evidence consolidation,
human-in-the-loop review, controlled closure, and historical reopening.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_rollout_repository import (
    SafetyRolloutRepository,
    get_safety_rollout_repository,
)
from app.repositories.safety_verification_repository import (
    SafetyVerificationRepository,
    get_safety_verification_repository,
)
from app.schemas.safety_verification import (
    AssuranceOutcomeStatus,
    ClosureEligibilityResponse,
    CollectEvidenceRequest,
    ControlledClosureRequest,
    CreateVerificationRequest,
    EffectivenessOutcomeStatus,
    EvidenceReference,
    FinalizeVerificationRequest,
    HumanVerificationReviewRecord,
    ReanalysisVerificationRequest,
    ReassessmentVerificationRequest,
    ReopenVerificationRequest,
    RunVerificationRequest,
    SafetyVerificationRecord,
    SubmitReviewRequest,
    VerificationAssuranceResponse,
    VerificationEffectivenessResponse,
    VerificationHistoryEntry,
    VerificationLifecycleState,
    VerificationStatusResponse,
)
from app.services.safety_verification_closure_service import SafetyVerificationClosureService
from app.services.safety_verification_evidence_service import SafetyVerificationEvidenceService
from app.services.safety_verification_review_service import SafetyVerificationReviewService


class SafetyVerificationService:
    """Core domain service for Phase 58 release verification and closure governance."""

    def __init__(
        self,
        repository: Optional[SafetyVerificationRepository] = None,
        rollout_repository: Optional[SafetyRolloutRepository] = None,
        evidence_service: Optional[SafetyVerificationEvidenceService] = None,
        review_service: Optional[SafetyVerificationReviewService] = None,
        closure_service: Optional[SafetyVerificationClosureService] = None,
    ) -> None:
        self.repository = repository or get_safety_verification_repository()
        self.rollout_repository = rollout_repository or get_safety_rollout_repository()
        self.evidence_service = evidence_service or SafetyVerificationEvidenceService(self.rollout_repository)
        self.review_service = review_service or SafetyVerificationReviewService(self.rollout_repository)
        self.closure_service = closure_service or SafetyVerificationClosureService(self.rollout_repository)

    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_verification(
        self, request: CreateVerificationRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Create a new formal change verification workflow."""
        # 1. Idempotency check
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

        # 2. Concurrency check
        existing_for_rollout = self.repository.get_by_rollout_id(request.rollout_id)
        if existing_for_rollout and existing_for_rollout.verification_status not in {
            VerificationLifecycleState.CLOSED,
            VerificationLifecycleState.FAILED,
            VerificationLifecycleState.SUPERSEDED,
        }:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=f"An active verification '{existing_for_rollout.verification_id}' already exists for rollout '{request.rollout_id}'",
                status_code=409,
            )

        # 3. Source rollout verification
        rollout = self.rollout_repository.get(request.rollout_id)
        if not rollout:
            raise AppException(
                code=ErrorCode.SAFETY_ROLLOUT_NOT_FOUND,
                message=f"Source rollout '{request.rollout_id}' not found",
                status_code=404,
            )

        now = datetime.now(timezone.utc)
        record = SafetyVerificationRecord(
            rollout_id=request.rollout_id,
            change_id=request.change_id,
            change_proposal_id=request.change_proposal_id,
            approved_version=request.approved_version,
            deployed_version=request.deployed_version,
            scope=request.scope,
            verification_status=VerificationLifecycleState.COLLECTING_EVIDENCE,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )

        # 4. Initial Evidence Collection
        ev_items, ass_stat, eff_stat, sc_stat = self.evidence_service.collect_evidence_from_sources(record)
        record.evidence_items = ev_items
        record.assurance_status = ass_stat
        record.effectiveness_status = eff_stat
        record.safety_control_status = sc_stat

        # Record history
        record.history.append(
            VerificationHistoryEntry(
                from_state="NONE",
                to_state=record.verification_status.value,
                action="CREATE_VERIFICATION",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Verification record initiated from completed rollout",
                timestamp=now,
            )
        )

        saved = self.repository.save(record)

        if request.idempotency_key:
            self.repository.record_idempotency(
                request.idempotency_key, self._compute_hash(request.model_dump()), saved.verification_id
            )

        return saved

    def get_verification(self, verification_id: str) -> SafetyVerificationRecord:
        """Fetch verification by ID or raise 404."""
        record = self.repository.get(verification_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_VERIFICATION_NOT_FOUND,
                message=f"Safety verification '{verification_id}' not found",
                status_code=404,
            )
        return record

    def get_status(self, verification_id: str) -> VerificationStatusResponse:
        """Fetch status overview."""
        v = self.get_verification(verification_id)
        return VerificationStatusResponse(
            verification_id=v.verification_id,
            rollout_id=v.rollout_id,
            change_id=v.change_id,
            approved_version=v.approved_version,
            deployed_version=v.deployed_version,
            verification_status=v.verification_status,
            closure_eligible=v.closure_eligible,
            blocking_reasons=v.blocking_reasons,
            version=v.version,
            updated_at=v.updated_at,
        )

    def get_evidence(self, verification_id: str) -> List[EvidenceReference]:
        """Fetch linked evidence references."""
        v = self.get_verification(verification_id)
        return v.evidence_items

    def get_history(self, verification_id: str) -> List[VerificationHistoryEntry]:
        """Fetch immutable history trail."""
        v = self.get_verification(verification_id)
        return v.history

    def collect_evidence(
        self, verification_id: str, request: CollectEvidenceRequest, actor_id: str, actor_role: str
    ) -> List[EvidenceReference]:
        """Trigger evidence collection and update verification health."""
        v = self.get_verification(verification_id)

        ev_items, ass_stat, eff_stat, sc_stat = self.evidence_service.collect_evidence_from_sources(v)
        v.evidence_items = ev_items
        v.assurance_status = ass_stat
        v.effectiveness_status = eff_stat
        v.safety_control_status = sc_stat

        is_complete, missing = self.evidence_service.validate_completeness(ev_items)
        is_consistent, conflicts = self.evidence_service.validate_consistency(v, ev_items)

        old_state = v.verification_status.value
        if not is_complete:
            v.verification_status = VerificationLifecycleState.EVIDENCE_INCOMPLETE
            v.blocking_reasons = [f"Missing evidence: {m}" for m in missing]
        elif not is_consistent:
            v.verification_status = VerificationLifecycleState.EVIDENCE_CONFLICTED
            v.blocking_reasons = conflicts
        else:
            v.verification_status = VerificationLifecycleState.VERIFICATION_IN_PROGRESS
            v.blocking_reasons.clear()

        v.version += 1
        v.history.append(
            VerificationHistoryEntry(
                from_state=old_state,
                to_state=v.verification_status.value,
                action="COLLECT_EVIDENCE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Evidence collected: {len(ev_items)} items. Complete={is_complete}, Consistent={is_consistent}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(v)
        return v.evidence_items

    def verify(
        self, verification_id: str, request: RunVerificationRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Run verification evaluation engine."""
        v = self.get_verification(verification_id)

        is_complete, missing = self.evidence_service.validate_completeness(v.evidence_items)
        if not is_complete:
            v.verification_status = VerificationLifecycleState.EVIDENCE_INCOMPLETE
            v.blocking_reasons = [f"Missing evidence: {m}" for m in missing]
            self.repository.save(v)
            raise AppException(
                code=ErrorCode.EVIDENCE_INCOMPLETE,
                message=f"Verification cannot proceed: missing evidence ({', '.join(missing)})",
                status_code=400,
            )

        is_consistent, conflicts = self.evidence_service.validate_consistency(v, v.evidence_items)
        if not is_consistent:
            v.verification_status = VerificationLifecycleState.EVIDENCE_CONFLICTED
            v.blocking_reasons = conflicts
            self.repository.save(v)
            raise AppException(
                code=ErrorCode.EVIDENCE_CONFLICTED,
                message=f"Verification cannot proceed: evidence conflicts ({', '.join(conflicts)})",
                status_code=400,
            )

        # Check safety controls
        if v.safety_control_status != "PASSED":
            v.verification_status = VerificationLifecycleState.VERIFICATION_BLOCKED
            v.blocking_reasons.append("Active safety controls not verified")
            self.repository.save(v)
            raise AppException(
                code=ErrorCode.SAFETY_CONTROL_FAILED,
                message="Verification blocked: active runtime safety controls have not passed",
                status_code=400,
            )

        # Check assurance if strictly required
        if request.require_strict_assurance and v.assurance_status != AssuranceOutcomeStatus.ASSURANCE_PASS:
            v.verification_status = VerificationLifecycleState.VERIFICATION_BLOCKED
            v.blocking_reasons.append(f"Assurance status is {v.assurance_status.value}")
            self.repository.save(v)
            raise AppException(
                code=ErrorCode.ASSURANCE_PENDING,
                message="Verification blocked: Phase 52 assurance has not confirmed safety controls",
                status_code=400,
            )

        old_state = v.verification_status.value
        v.verification_status = VerificationLifecycleState.HUMAN_REVIEW_REQUIRED
        v.version += 1

        v.history.append(
            VerificationHistoryEntry(
                from_state=old_state,
                to_state=v.verification_status.value,
                action="RUN_VERIFICATION",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Verification checks passed; human supervisor review required",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(v)

    def review(
        self, verification_id: str, request: SubmitReviewRequest, actor_id: str, actor_role: str
    ) -> HumanVerificationReviewRecord:
        """Submit human verification decision."""
        v = self.get_verification(verification_id)
        old_state = v.verification_status.value

        review_rec = self.review_service.submit_review(
            verification=v,
            decision=request.decision,
            rationale=request.rationale,
            reviewer_id=actor_id,
            reviewer_role=actor_role,
            conditions=request.conditions,
            is_ai_agent=request.is_ai_agent,
        )

        v.version += 1
        v.history.append(
            VerificationHistoryEntry(
                from_state=old_state,
                to_state=v.verification_status.value,
                action="SUBMIT_HUMAN_REVIEW",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Human review decision: {request.decision.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(v)
        return review_rec

    def finalize(
        self, verification_id: str, request: FinalizeVerificationRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Finalize verification result into closure pending state."""
        v = self.get_verification(verification_id)

        if v.verification_status not in {
            VerificationLifecycleState.VERIFIED,
            VerificationLifecycleState.CONDITIONALLY_VERIFIED,
        }:
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message=f"Cannot finalize verification in state '{v.verification_status.value}'. Must be VERIFIED.",
                status_code=400,
            )

        old_state = v.verification_status.value
        v.verification_status = VerificationLifecycleState.CLOSURE_PENDING
        v.version += 1

        v.history.append(
            VerificationHistoryEntry(
                from_state=old_state,
                to_state=v.verification_status.value,
                action="FINALIZE_VERIFICATION",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.notes or "Verification finalized and queued for controlled closure",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(v)

    def close(
        self, verification_id: str, request: ControlledClosureRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Execute controlled change closure."""
        v = self.get_verification(verification_id)
        closed = self.closure_service.execute_closure(
            verification=v,
            rationale=request.rationale,
            actor_id=actor_id,
            actor_role=actor_role,
            monitoring_window_days=request.monitoring_window_days or 30,
            monitoring_owner=request.monitoring_owner,
            expected_signals=request.expected_signals,
        )
        return self.repository.save(closed)

    def reopen(
        self, verification_id: str, request: ReopenVerificationRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Execute controlled change reopening."""
        v = self.get_verification(verification_id)
        reopened = self.closure_service.execute_reopen(
            verification=v,
            reason=request.reason,
            actor_id=actor_id,
            actor_role=actor_role,
            triggering_evidence_id=request.triggering_evidence_id,
        )
        return self.repository.save(reopened)

    def reassess(
        self, verification_id: str, request: ReassessmentVerificationRequest, actor_id: str, actor_role: str
    ) -> SafetyVerificationRecord:
        """Request formal reassessment of change verification."""
        v = self.get_verification(verification_id)
        old_state = v.verification_status.value
        v.verification_status = VerificationLifecycleState.REASSESSMENT_REQUIRED
        v.closure_eligible = False
        v.version += 1

        v.history.append(
            VerificationHistoryEntry(
                from_state=old_state,
                to_state=v.verification_status.value,
                action="REQUEST_REASSESSMENT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(v)

    def evaluate_closure_eligibility(self, verification_id: str) -> ClosureEligibilityResponse:
        """Evaluate closure eligibility against all mandatory gates."""
        v = self.get_verification(verification_id)
        return self.closure_service.evaluate_closure_eligibility(v)

    def get_assurance(self, verification_id: str) -> VerificationAssuranceResponse:
        """Fetch linked Phase 52 assurance details."""
        v = self.get_verification(verification_id)
        p52_evidence = [e for e in v.evidence_items if e.source_phase == "Phase 52"]
        return VerificationAssuranceResponse(
            verification_id=v.verification_id,
            assurance_status=v.assurance_status,
            evidence_references=p52_evidence,
            is_satisfactory=v.assurance_status == AssuranceOutcomeStatus.ASSURANCE_PASS,
        )

    def get_effectiveness(self, verification_id: str) -> VerificationEffectivenessResponse:
        """Fetch linked Phase 55 effectiveness details."""
        v = self.get_verification(verification_id)
        p55_evidence = [e for e in v.evidence_items if e.source_phase == "Phase 55"]
        return VerificationEffectivenessResponse(
            verification_id=v.verification_id,
            effectiveness_status=v.effectiveness_status,
            evidence_references=p55_evidence,
            is_satisfactory=v.effectiveness_status in {
                EffectivenessOutcomeStatus.EFFECTIVENESS_SUFFICIENT,
                EffectivenessOutcomeStatus.EFFECTIVENESS_CONDITIONAL,
            },
        )

    def reanalysis(
        self, request: ReanalysisVerificationRequest, actor_id: str, actor_role: str
    ) -> List[VerificationStatusResponse]:
        """Perform batch evidence reanalysis on specified or all pending verifications."""
        if request.verification_ids:
            records = [self.repository.get(vid) for vid in request.verification_ids if self.repository.get(vid)]
        else:
            records = self.repository.list_pending()

        results: List[VerificationStatusResponse] = []
        for v in records:
            if v:
                self.evidence_service.collect_evidence_from_sources(v)
                eligibility = self.closure_service.evaluate_closure_eligibility(v)
                v.closure_eligible = eligibility.eligible
                self.repository.save(v)
                results.append(
                    VerificationStatusResponse(
                        verification_id=v.verification_id,
                        rollout_id=v.rollout_id,
                        change_id=v.change_id,
                        approved_version=v.approved_version,
                        deployed_version=v.deployed_version,
                        verification_status=v.verification_status,
                        closure_eligible=v.closure_eligible,
                        blocking_reasons=v.blocking_reasons,
                        version=v.version,
                        updated_at=v.updated_at,
                    )
                )

        return results

    # Filtering convenience methods
    def list_verifications(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        verification_status: Optional[VerificationLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyVerificationRecord]:
        return self.repository.list_verifications(
            organization_id=organization_id,
            facility_id=facility_id,
            verification_status=verification_status,
            limit=limit,
            offset=offset,
        )

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        return self.repository.list_pending(organization_id=organization_id)

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        return self.repository.list_review_required(organization_id=organization_id)

    def list_closure_pending(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        return self.repository.list_closure_pending(organization_id=organization_id)

    def list_reopened(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        return self.repository.list_reopened(organization_id=organization_id)


# Global singleton service
_service_instance: Optional[SafetyVerificationService] = None


def get_safety_verification_service() -> SafetyVerificationService:
    """Retrieve global singleton service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SafetyVerificationService()
    return _service_instance

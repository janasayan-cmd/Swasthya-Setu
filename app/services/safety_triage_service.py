"""Phase 60: Safety Triage Master Orchestrator Service.

Coordinates surveillance signal intake, classification, severity evaluation,
uncertainty quantification, human oversight review, and governed routing.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_triage_repository import (
    SafetyTriageRepository,
    get_safety_triage_repository,
)
from app.schemas.safety_triage import (
    ClassifySignalRequest,
    CreateTriageRequest,
    EvaluateSeverityRequest,
    EvaluateTriageRequest,
    ExecuteRoutingRequest,
    GovernedSignalSeverity,
    ReanalysisTriageRequest,
    RequestTriageReassessmentRequest,
    RoutingDecisionRecord,
    RoutingDestination,
    SafetyTriageRecord,
    SignalClassification,
    SubmitTriageReviewRequest,
    TriageEvaluationResponse,
    TriageEvidenceItem,
    TriageHistoryEntry,
    TriageLifecycleState,
    TriageReviewRecord,
    TriageScope,
    TriageSignalItem,
    TriageStatusResponse,
)
from app.services.safety_routing_service import SafetyRoutingService
from app.services.safety_signal_classification_service import (
    SafetySignalClassificationService,
)
from app.services.safety_signal_severity_service import (
    SafetySignalSeverityService,
)
from app.services.safety_triage_review_service import (
    SafetyTriageReviewService,
)


class SafetyTriageService:
    """Master orchestrator for Phase 60 safety signal triage."""

    def __init__(
        self,
        repository: Optional[SafetyTriageRepository] = None,
        classification_service: Optional[SafetySignalClassificationService] = None,
        severity_service: Optional[SafetySignalSeverityService] = None,
        routing_service: Optional[SafetyRoutingService] = None,
        review_service: Optional[SafetyTriageReviewService] = None,
    ) -> None:
        self.repository = repository or get_safety_triage_repository()
        self.classification_service = classification_service or SafetySignalClassificationService()
        self.severity_service = severity_service or SafetySignalSeverityService()
        self.routing_service = routing_service or SafetyRoutingService()
        self.review_service = review_service or SafetyTriageReviewService()

    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_triage(
        self,
        request: CreateTriageRequest,
        actor_id: Any,
        actor_role: Optional[str] = None,
        actor_organization_id: Optional[str] = None,
    ) -> SafetyTriageRecord:
        """Create a new safety triage context."""
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

        # 1. Scope and Organization Validation
        scope_obj = request.scope
        org_id = getattr(scope_obj, "organization_id", None) or (scope_obj.get("organization_id") if isinstance(scope_obj, dict) else None)
        if not org_id:
            raise AppException(
                code=ErrorCode.SCOPE_MISMATCH,
                message="Triage scope requires an organization_id",
                status_code=400,
            )

        if actor_organization_id and org_id != actor_organization_id and actor_role not in ("SUPER_ADMIN", "SYSTEM"):
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message=f"Triage organization '{org_id}' does not match actor organization '{actor_organization_id}'",
                status_code=403,
            )

        # 2. Idempotency Check
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

        triage_id = request.triage_id or f"trg-{uuid.uuid4().hex[:12]}"
        version = request.version or "v1.0.0"

        # Build Scope
        final_scope = TriageScope(**scope_obj) if isinstance(scope_obj, dict) else scope_obj

        # Build primary signal item
        signals_list: List[TriageSignalItem] = []
        sig_data = request.signal_data or {}
        primary_item = TriageSignalItem(
            signal_id=request.primary_signal_id,
            source=sig_data.get("source", "Phase 59"),
            source_record_id=sig_data.get("source_record_id"),
            signal_type=sig_data.get("signal_type", "UNKNOWN_SIGNAL"),
            severity=sig_data.get("severity", "MEDIUM").upper(),
            version=version,
            scope=sig_data.get("scope") or final_scope.model_dump(),
            metadata=sig_data.get("metadata") or {},
        )
        signals_list.append(primary_item)

        # Append related signals
        if request.related_signals:
            for rs in request.related_signals:
                signals_list.append(
                    TriageSignalItem(
                        signal_id=rs.get("signal_id") or f"sig-{uuid.uuid4().hex[:6]}",
                        source=rs.get("source", "Phase 59"),
                        source_record_id=rs.get("source_record_id"),
                        signal_type=rs.get("signal_type", "RELATED_SIGNAL"),
                        severity=rs.get("severity", "MEDIUM").upper(),
                        version=version,
                        scope=rs.get("scope") or final_scope.model_dump(),
                        metadata=rs.get("metadata") or {},
                    )
                )

        # Append evidence items
        evidence_list: List[TriageEvidenceItem] = []
        if request.evidence_items:
            for ev in request.evidence_items:
                evidence_list.append(
                    TriageEvidenceItem(
                        evidence_id=ev.get("evidence_id") or f"evi-{uuid.uuid4().hex[:6]}",
                        evidence_type=ev.get("evidence_type", "TELEMETRY_LOG"),
                        source_phase=ev.get("source_phase", "Phase 18"),
                        reference_id=ev.get("reference_id", "ref-001"),
                        description=ev.get("description", "Traceable evidence reference"),
                        metadata=ev.get("metadata") or {},
                    )
                )

        record = SafetyTriageRecord(
            triage_id=triage_id,
            primary_signal_id=request.primary_signal_id,
            monitoring_id=request.monitoring_id,
            verification_id=request.verification_id,
            change_id=request.change_id,
            rollout_id=request.rollout_id,
            organization_id=org_id,
            scope=final_scope,
            version=version,
            lifecycle_state=TriageLifecycleState.RECEIVED,
            signals=signals_list,
            evidence=evidence_list,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )

        record.history.append(
            TriageHistoryEntry(
                from_state="NONE",
                to_state=record.lifecycle_state.value,
                action="CREATE_TRIAGE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Surveillance signal ingested into safety triage",
                timestamp=now,
            )
        )

        # Initial Classification and Severity assessment
        self.classification_service.classify(record)
        self.severity_service.evaluate_severity_and_uncertainty(record)

        saved = self.repository.save(record)

        if request.idempotency_key:
            self.repository.record_idempotency(
                request.idempotency_key, self._compute_hash(request.model_dump()), saved.triage_id
            )

        return saved

    def get_triage(self, triage_id: str) -> SafetyTriageRecord:
        """Retrieve triage record by ID or raise 404."""
        record = self.repository.get(triage_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_TRIAGE_NOT_FOUND,
                message=f"Safety triage context '{triage_id}' not found",
                status_code=404,
            )
        return record

    def get_status(self, triage_id: str) -> TriageStatusResponse:
        """Get triage status overview."""
        r = self.get_triage(triage_id)
        return TriageStatusResponse(
            triage_id=r.triage_id,
            primary_signal_id=r.primary_signal_id,
            lifecycle_state=r.lifecycle_state,
            classification=r.classification,
            governed_severity=r.governed_severity,
            uncertainty_state=r.uncertainty_state,
            priority=r.priority,
            requires_human_review=r.requires_human_review,
            is_escalated=r.is_escalated,
            reopen_triggered=r.reopen_triggered,
            routes_count=len(r.routing_decisions),
            updated_at=r.updated_at,
        )

    def get_signals(self, triage_id: str) -> List[TriageSignalItem]:
        r = self.get_triage(triage_id)
        return r.signals

    def get_evidence(self, triage_id: str) -> List[TriageEvidenceItem]:
        r = self.get_triage(triage_id)
        return r.evidence

    def get_history(self, triage_id: str) -> List[TriageHistoryEntry]:
        r = self.get_triage(triage_id)
        return r.history

    def classify_signal(
        self,
        triage_id: str,
        request: ClassifySignalRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyTriageRecord:
        """Classify the signal context."""
        record = self.get_triage(triage_id)
        old_state = record.lifecycle_state.value

        target_class, requires_review = self.classification_service.classify(
            record=record,
            explicit_classification=request.classification,
            is_ai_agent=request.is_ai_agent,
            ai_metadata=request.ai_metadata,
        )

        record.history.append(
            TriageHistoryEntry(
                from_state=old_state,
                to_state=record.lifecycle_state.value,
                action="CLASSIFY_SIGNAL",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.rationale or f"Classified as {target_class.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(record)

    def evaluate_severity(
        self,
        triage_id: str,
        request: EvaluateSeverityRequest,
        actor_id: str,
        actor_role: str,
    ) -> SafetyTriageRecord:
        """Run severity and uncertainty evaluation."""
        record = self.get_triage(triage_id)
        old_state = record.lifecycle_state.value

        # Append additional evidence if provided
        if request.additional_evidence:
            for ev in request.additional_evidence:
                record.evidence.append(
                    TriageEvidenceItem(
                        evidence_id=ev.get("evidence_id") or f"evi-{uuid.uuid4().hex[:6]}",
                        evidence_type=ev.get("evidence_type", "CORROBORATING_DATA"),
                        source_phase=ev.get("source_phase", "Phase 18"),
                        reference_id=ev.get("reference_id", "ref-auto"),
                        description=ev.get("description", "Additional evidence"),
                        metadata=ev.get("metadata") or {},
                    )
                )

        sev, unc, priority = self.severity_service.evaluate_severity_and_uncertainty(record)

        record.history.append(
            TriageHistoryEntry(
                from_state=old_state,
                to_state=record.lifecycle_state.value,
                action="EVALUATE_SEVERITY",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Evaluated severity: {sev.value}, uncertainty: {unc.value}, priority: {priority.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(record)

    def evaluate_triage(
        self,
        triage_id: str,
        request: EvaluateTriageRequest,
        actor_id: str,
        actor_role: str,
    ) -> TriageEvaluationResponse:
        """Execute complete triage evaluation and determine routing."""
        record = self.get_triage(triage_id)

        # 1. Classify if still unclassified
        if record.classification == SignalClassification.UNKNOWN:
            self.classification_service.classify(record)

        # 2. Evaluate Severity & Uncertainty
        self.severity_service.evaluate_severity_and_uncertainty(record)

        # 3. Determine Routing Decisions
        decisions = self.routing_service.determine_routing(record)

        record.history.append(
            TriageHistoryEntry(
                from_state=record.lifecycle_state.value,
                to_state=record.lifecycle_state.value,
                action="EVALUATE_TRIAGE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="End-to-end triage evaluation executed",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(record)

        return TriageEvaluationResponse(
            triage_id=record.triage_id,
            lifecycle_state=record.lifecycle_state,
            classification=record.classification,
            governed_severity=record.governed_severity,
            uncertainty_state=record.uncertainty_state,
            priority=record.priority,
            requires_human_review=record.requires_human_review,
            routing_decisions=record.routing_decisions,
            escalation_reason="Escalated due to critical severity or safety control breach" if record.is_escalated else None,
        )

    def submit_review(
        self,
        triage_id: str,
        request: SubmitTriageReviewRequest,
        actor_id: str,
        actor_role: str,
    ) -> TriageReviewRecord:
        """Submit governed human review."""
        record = self.get_triage(triage_id)
        old_state = record.lifecycle_state.value

        rev = self.review_service.submit_review(
            record=record,
            decision=request.decision,
            rationale=request.rationale,
            reviewer_id=actor_id,
            reviewer_role=actor_role,
            routing_destination=request.routing_destination,
            is_ai_agent=request.is_ai_agent,
        )

        record.history.append(
            TriageHistoryEntry(
                from_state=old_state,
                to_state=record.lifecycle_state.value,
                action="SUBMIT_TRIAGE_REVIEW",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Human triage review: {request.decision.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(record)
        return rev

    def execute_routing(
        self,
        triage_id: str,
        request: ExecuteRoutingRequest,
        actor_id: str,
        actor_role: str,
    ) -> RoutingDecisionRecord:
        """Execute authorized routing to an authoritative downstream phase."""
        record = self.get_triage(triage_id)

        # Check if already routed to the same destination
        existing = [d for d in record.routing_decisions if d.destination == request.destination and d.status == "ROUTED"]
        if existing:
            raise AppException(
                code=ErrorCode.ROUTING_ALREADY_COMPLETED,
                message=f"Routing destination '{request.destination.value}' already executed for this triage context",
                status_code=409,
            )

        now = datetime.now(timezone.utc)
        target = request.target_phase or "Phase 58"
        if request.destination == RoutingDestination.PHASE_49_INCIDENT_ROUTING:
            target = "Phase 49"
            record.lifecycle_state = TriageLifecycleState.INCIDENT_ROUTING_REQUIRED
            record.is_escalated = True
        elif request.destination == RoutingDestination.PHASE_58_REOPEN_REVIEW:
            target = "Phase 58"
            record.lifecycle_state = TriageLifecycleState.REOPEN_REQUIRED
            record.reopen_triggered = True
        elif request.destination == RoutingDestination.PHASE_52_ASSURANCE_REVIEW:
            target = "Phase 52"
            record.lifecycle_state = TriageLifecycleState.ASSURANCE_ROUTING_REQUIRED
        elif request.destination == RoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW:
            target = "Phase 55"
            record.lifecycle_state = TriageLifecycleState.EFFECTIVENESS_ROUTING_REQUIRED
        elif request.destination == RoutingDestination.PHASE_51_GOVERNANCE_REVIEW:
            target = "Phase 51"
            record.lifecycle_state = TriageLifecycleState.GOVERNANCE_ROUTING_REQUIRED
        elif request.destination == RoutingDestination.CONTINUE_MONITORING:
            target = "Phase 59"
            record.lifecycle_state = TriageLifecycleState.ROUTED

        dec = RoutingDecisionRecord(
            destination=request.destination,
            target_phase=target,
            reason=request.reason,
            applicable_rule="GOV-P60-AUTHORIZED-ROUTE",
            requires_human_review=False,
            routed_at=now,
            status="ROUTED",
        )
        record.routing_decisions.append(dec)

        record.history.append(
            TriageHistoryEntry(
                from_state=record.lifecycle_state.value,
                to_state=record.lifecycle_state.value,
                action="EXECUTE_ROUTING",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Routed to {request.destination.value} ({target})",
                timestamp=now,
            )
        )

        self.repository.save(record)
        return dec

    def request_reassessment(
        self,
        triage_id: str,
        request: RequestTriageReassessmentRequest,
        actor_id: str,
        actor_role: str,
    ) -> RoutingDecisionRecord:
        """Request formal reassessment targeting Phase 51/58."""
        record = self.get_triage(triage_id)
        now = datetime.now(timezone.utc)

        record.lifecycle_state = TriageLifecycleState.REASSESSMENT_REQUIRED

        dec = RoutingDecisionRecord(
            destination=RoutingDestination.PHASE_58_REASSESSMENT,
            target_phase="Phase 58",
            reason=request.reason,
            applicable_rule="GOV-P60-REASSESS-REQ",
            requires_human_review=True,
            routed_at=now,
            status="ROUTED",
        )
        record.routing_decisions.append(dec)

        record.history.append(
            TriageHistoryEntry(
                from_state=record.lifecycle_state.value,
                to_state=TriageLifecycleState.REASSESSMENT_REQUIRED.value,
                action="REQUEST_REASSESSMENT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=now,
            )
        )

        self.repository.save(record)
        return dec

    def reanalysis(
        self,
        request: ReanalysisTriageRequest,
        actor_id: str,
        actor_role: str,
    ) -> List[TriageStatusResponse]:
        """Perform batch triage reanalysis."""
        if request.triage_ids:
            records = [self.repository.get(tid) for tid in request.triage_ids if self.repository.get(tid)]
        else:
            records = self.repository.list_triage()

        results: List[TriageStatusResponse] = []
        for r in records:
            if r:
                self.classification_service.classify(r)
                self.severity_service.evaluate_severity_and_uncertainty(r)
                self.repository.save(r)
                results.append(
                    TriageStatusResponse(
                        triage_id=r.triage_id,
                        primary_signal_id=r.primary_signal_id,
                        lifecycle_state=r.lifecycle_state,
                        classification=r.classification,
                        governed_severity=r.governed_severity,
                        uncertainty_state=r.uncertainty_state,
                        priority=r.priority,
                        requires_human_review=r.requires_human_review,
                        is_escalated=r.is_escalated,
                        reopen_triggered=r.reopen_triggered,
                        routes_count=len(r.routing_decisions),
                        updated_at=r.updated_at,
                    )
                )

        return results

    # Filtering convenience methods
    def list_triage(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[TriageLifecycleState] = None,
        severity: Optional[GovernedSignalSeverity] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyTriageRecord]:
        return self.repository.list_triage(
            organization_id=organization_id,
            facility_id=facility_id,
            lifecycle_state=lifecycle_state,
            severity=severity,
            limit=limit,
            offset=offset,
        )

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_review_required(organization_id=organization_id)

    def list_high_priority(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_high_priority(organization_id=organization_id)

    def list_escalation_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_escalation_required(organization_id=organization_id)

    def list_reopen_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_reopen_required(organization_id=organization_id)

    def list_incident_routing_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_incident_routing_required(organization_id=organization_id)

    def list_governance_routing_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        return self.repository.list_governance_routing_required(organization_id=organization_id)


# Global singleton
_service_instance: Optional[SafetyTriageService] = None


def get_safety_triage_service() -> SafetyTriageService:
    """Retrieve global singleton service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SafetyTriageService()
    return _service_instance

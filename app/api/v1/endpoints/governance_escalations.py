"""Phase 67: Governance Escalation REST API Endpoints.

Implements REST API endpoints for:
- Creating, classifying, and routing governance escalations
- Ingesting, aggregating, and separating cross-workflow safety exceptions
- Assigning, reassigning, and acknowledging escalation ownership
- Reviewing, recording authoritative decisions, and conflict management
- Coordinating resolution requirements and downstream reconciliation
- Controlled closure and governed reopening
- Queue monitoring: unassigned, overdue, review-required, conflicted, awaiting-acknowledgement

Base Path: /api/v1/governance-escalations
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.governance_decision_coordination import (
    CrossWorkflowConflictRecord,
    GovernanceDecisionRecord,
    GovernanceReviewRecord,
    RecordGovernanceDecisionRequest,
    RecordGovernanceReviewRequest,
)
from app.schemas.governance_escalation import (
    AcknowledgeEscalationRequest,
    AssignEscalationRequest,
    ClassifyEscalationRequest,
    CreateGovernanceEscalationRequest,
    EscalationHistoryResponse,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
    ReassignEscalationRequest,
    RouteEscalationRequest,
)
from app.schemas.governance_exception import (
    ExceptionAggregationRequest,
    ExceptionSeparationRequest,
    GovernanceExceptionRecord,
    GovernancePriority,
    IngestGovernanceExceptionRequest,
    ReviewGovernanceExceptionRequest,
)
from app.schemas.governance_resolution_requirement import (
    CloseEscalationRequest,
    ExtendDeadlineRequest,
    ReconcileResolutionRequirementRequest,
    ReopenEscalationRequest,
    ResolutionRequirementRecord,
    ResolveEscalationRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.cross_workflow_conflict_service import get_cross_workflow_conflict_service
from app.services.governance_escalation_service import (
    GovernanceEscalationService,
    get_governance_escalation_service,
)
from app.services.governance_exception_ingestion_service import (
    get_governance_exception_ingestion_service,
)

router = APIRouter(prefix="/governance-escalations", tags=["Phase 67 - Governance Escalation"])


# ===========================================================================
# 1. Specialized Queue Endpoints (Declared first to avoid path collision)
# ===========================================================================


@router.get(
    "/queues/unassigned",
    response_model=List[GovernanceEscalationRecord],
    summary="List unassigned escalations requiring owner assignment",
)
def list_unassigned_queue(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all escalations awaiting primary ownership assignment."""
    return service.list_unassigned_queue(current_user, facility_id, limit, offset)


@router.get(
    "/queues/overdue",
    response_model=List[GovernanceEscalationRecord],
    summary="List overdue escalations breaching policy deadlines",
)
def list_overdue_queue(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve active escalations that have exceeded configured response deadlines."""
    return service.list_overdue_queue(current_user, facility_id, limit, offset)


@router.get(
    "/queues/awaiting-acknowledgement",
    response_model=List[GovernanceEscalationRecord],
    summary="List escalations awaiting owner acknowledgement",
)
def list_awaiting_acknowledgement_queue(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve escalations assigned to an owner but not yet formally acknowledged."""
    return service.list_awaiting_acknowledgement_queue(current_user, facility_id, limit, offset)


@router.get(
    "/queues/review-required",
    response_model=List[GovernanceEscalationRecord],
    summary="List escalations currently in formal review or decision states",
)
def list_review_required_queue(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve escalations currently requiring formal review or decision."""
    return service.list_review_required_queue(current_user, facility_id, limit, offset)


@router.get(
    "/queues/conflicted",
    response_model=List[GovernanceEscalationRecord],
    summary="List escalations containing active cross-workflow decision conflicts",
)
def list_conflicted_queue(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve escalations flagged with contradictory authoritative workflow decisions."""
    return service.list_conflicted_queue(current_user, facility_id, limit, offset)


# ===========================================================================
# 2. Ingestion & Root Collection Operations
# ===========================================================================


@router.post(
    "",
    response_model=GovernanceEscalationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new governance escalation",
)
def create_governance_escalation(
    payload: CreateGovernanceEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Initialize a new cross-workflow governance escalation with deterministic priority classification."""
    return service.create_escalation(current_user, payload)


@router.get(
    "",
    response_model=List[GovernanceEscalationRecord],
    summary="List governance escalations for tenant",
)
def list_governance_escalations(
    facility_id: Optional[str] = Query(None),
    priority: Optional[GovernancePriority] = Query(None),
    state: Optional[EscalationLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """List tenant escalations with optional priority, state, and facility filtering."""
    return service.list_escalations(current_user, facility_id, priority, state, limit, offset)


@router.post(
    "/ingest-exception",
    response_model=GovernanceExceptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a raw cross-workflow governance exception with deduplication",
)
def ingest_exception(
    payload: IngestGovernanceExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Ingest a normalized exception from an authoritative upstream/downstream safety workflow."""
    return get_governance_exception_ingestion_service().ingest_exception(current_user, payload)


# ===========================================================================
# 3. Escalation Detail & Workflow Inspection
# ===========================================================================


@router.get(
    "/{escalation_id}",
    response_model=GovernanceEscalationRecord,
    summary="Retrieve governance escalation detail",
)
def get_escalation(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve full domain record for a specific escalation."""
    return service.get_escalation(escalation_id, current_user)


@router.get(
    "/{escalation_id}/status",
    summary="Retrieve escalation lifecycle state summary",
)
def get_escalation_status(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve lightweight lifecycle state, priority, and deadline health."""
    esc = service.get_escalation(escalation_id, current_user)
    return {
        "escalation_id": esc.escalation_id,
        "lifecycle_state": esc.lifecycle_state.value,
        "governance_priority": esc.governance_priority.value,
        "is_acknowledged": esc.is_acknowledged,
        "is_overdue": esc.is_overdue,
        "is_reopened": esc.is_reopened,
        "assigned_owner_id": esc.assigned_owner_id,
        "active_conflicts_count": len(esc.conflicting_decision_ids),
        "aggregated_exceptions_count": len(esc.aggregated_exception_ids),
    }


@router.get(
    "/{escalation_id}/history",
    response_model=EscalationHistoryResponse,
    summary="Retrieve escalation audit transition history",
)
def get_escalation_history(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve complete immutable audit history for all lifecycle changes on this escalation."""
    return service.get_history(current_user, escalation_id)


@router.get(
    "/{escalation_id}/related-workflows",
    response_model=List[str],
    summary="Retrieve linked cross-phase workflow IDs",
)
def get_related_workflows(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all linked workflow IDs across Phases 49 through 66."""
    esc = service.get_escalation(escalation_id, current_user)
    return esc.related_workflow_ids


@router.get(
    "/{escalation_id}/dependencies",
    response_model=List[str],
    summary="Retrieve cross-workflow dependency references",
)
def get_dependencies(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all explicit dependency references required by this escalation."""
    esc = service.get_escalation(escalation_id, current_user)
    return esc.dependency_refs


# ===========================================================================
# 4. Exception Aggregation & Separation Operations
# ===========================================================================


@router.get(
    "/{escalation_id}/exceptions",
    response_model=List[GovernanceExceptionRecord],
    summary="List exceptions aggregated under escalation",
)
def list_exceptions(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all normalized exceptions grouped under this escalation."""
    service.get_escalation(escalation_id, current_user)
    return service.repository.list_exceptions(escalation_id=escalation_id, organization_id=current_user.organization_id)


@router.post(
    "/{escalation_id}/exceptions",
    response_model=GovernanceEscalationRecord,
    summary="Aggregate exceptions into escalation",
)
def aggregate_exceptions(
    escalation_id: str,
    payload: ExceptionAggregationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Correlate and aggregate related governance exceptions into this escalation."""
    return service.aggregate_exceptions(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/exceptions/separate",
    response_model=GovernanceEscalationRecord,
    summary="Separate an incorrectly grouped exception",
)
def separate_exception(
    escalation_id: str,
    payload: ExceptionSeparationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Separate an exception from this escalation with an auditable rationale."""
    return service.separate_exception(current_user, escalation_id, payload)


# ===========================================================================
# 5. Routing, Classification & Ownership Operations
# ===========================================================================


@router.post(
    "/{escalation_id}/classify",
    response_model=GovernanceEscalationRecord,
    summary="Classify or re-evaluate governance priority",
)
def classify_escalation(
    escalation_id: str,
    payload: ClassifyEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Evaluate and set deterministic governance priority level."""
    return service.classify_escalation(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/route",
    response_model=GovernanceEscalationRecord,
    summary="Route escalation to governance domain",
)
def route_escalation(
    escalation_id: str,
    payload: RouteEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Route escalation to target domain and hierarchy."""
    return service.route_escalation(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/assign",
    response_model=GovernanceEscalationRecord,
    summary="Assign responsible owner to escalation",
)
def assign_owner(
    escalation_id: str,
    payload: AssignEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Assign designated owner and compute acknowledgement and review deadlines."""
    return service.assign_owner(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/reassign",
    response_model=GovernanceEscalationRecord,
    summary="Reassign escalation to new owner",
)
def reassign_owner(
    escalation_id: str,
    payload: ReassignEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Reassign ownership with auditable rationale."""
    return service.reassign_owner(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/acknowledge",
    response_model=GovernanceEscalationRecord,
    summary="Acknowledge escalation assignment",
)
def acknowledge_escalation(
    escalation_id: str,
    payload: AcknowledgeEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Assigned owner formally acknowledges receipt and responsibility for escalation."""
    return service.acknowledge_escalation(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/extend-deadline",
    response_model=GovernanceEscalationRecord,
    summary="Authorize a deadline extension",
)
def extend_deadline(
    escalation_id: str,
    payload: ExtendDeadlineRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Record authorized extension for an acknowledgement, review, or resolution deadline."""
    return service.extend_deadline(current_user, escalation_id, payload)


# ===========================================================================
# 6. Reviews & Decisions
# ===========================================================================


@router.post(
    "/{escalation_id}/reviews",
    response_model=GovernanceReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record governance review execution",
)
def record_review(
    escalation_id: str,
    payload: RecordGovernanceReviewRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Record a formal governance review execution."""
    return service.execute_review(current_user, escalation_id, payload)


@router.get(
    "/{escalation_id}/reviews",
    response_model=List[GovernanceReviewRecord],
    summary="List governance reviews recorded for escalation",
)
def list_reviews(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all reviews conducted on this escalation."""
    return service.list_reviews(current_user, escalation_id)


@router.post(
    "/{escalation_id}/decisions",
    response_model=GovernanceDecisionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record authorized governance decision",
)
def record_decision(
    escalation_id: str,
    payload: RecordGovernanceDecisionRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Record an authoritative governance decision with target action instructions."""
    return service.execute_decision(current_user, escalation_id, payload)


@router.get(
    "/{escalation_id}/decisions",
    response_model=List[GovernanceDecisionRecord],
    summary="List governance decisions recorded for escalation",
)
def list_decisions(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all authoritative decisions recorded on this escalation."""
    return service.list_decisions(current_user, escalation_id)


# ===========================================================================
# 7. Cross-Workflow Conflict Management
# ===========================================================================


@router.get(
    "/{escalation_id}/conflicts",
    response_model=List[CrossWorkflowConflictRecord],
    summary="List cross-workflow decision conflicts",
)
def list_conflicts(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve conflicting authoritative records across safety workflows."""
    return service.list_conflicts(current_user, escalation_id)


@router.post(
    "/{escalation_id}/conflicts/{conflict_id}/resolve",
    response_model=CrossWorkflowConflictRecord,
    summary="Resolve a cross-workflow conflict",
)
def resolve_conflict(
    escalation_id: str,
    conflict_id: str,
    resolution_rationale: str = Query(..., description="Documented justification for resolving conflict"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Mark a conflict resolved following authorized reconciliation."""
    return get_cross_workflow_conflict_service().resolve_conflict(
        current_user, escalation_id, conflict_id, resolution_rationale
    )


# ===========================================================================
# 8. Resolution Requirements & Reconciliation
# ===========================================================================


@router.get(
    "/{escalation_id}/resolution-requirements",
    response_model=List[ResolutionRequirementRecord],
    summary="List resolution requirements for escalation",
)
def list_resolution_requirements(
    escalation_id: str,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all mandatory and optional requirements coordinating resolution."""
    return service.list_requirements(current_user, escalation_id)


@router.post(
    "/{escalation_id}/resolution-requirements/{requirement_id}/reconcile",
    response_model=ResolutionRequirementRecord,
    summary="Reconcile an individual resolution requirement",
)
def reconcile_requirement(
    escalation_id: str,
    requirement_id: str,
    payload: ReconcileResolutionRequirementRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Reconcile requirement status against downstream authoritative outcome."""
    return service.reconcile_requirement(current_user, escalation_id, requirement_id, payload)


# ===========================================================================
# 9. Resolution, Closure & Reopening
# ===========================================================================


@router.post(
    "/{escalation_id}/resolve",
    response_model=GovernanceEscalationRecord,
    summary="Resolve escalation following satisfaction of all mandatory requirements",
)
def resolve_escalation(
    escalation_id: str,
    payload: ResolveEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Mark escalation RESOLVED once all mandatory requirements and conflicts are resolved."""
    return service.resolve_escalation(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/close",
    response_model=GovernanceEscalationRecord,
    summary="Controlled administrative closure of escalation",
)
def close_escalation(
    escalation_id: str,
    payload: CloseEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Perform controlled administrative closure with separation of duties verification."""
    return service.close_escalation(current_user, escalation_id, payload)


@router.post(
    "/{escalation_id}/reopen",
    response_model=GovernanceEscalationRecord,
    summary="Reopen resolved or closed escalation upon material new findings",
)
def reopen_escalation(
    escalation_id: str,
    payload: ReopenEscalationRequest,
    service: GovernanceEscalationService = Depends(get_governance_escalation_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Reopen a resolved or closed escalation upon material new evidence or upstream reopening."""
    return service.reopen_escalation(current_user, escalation_id, payload)

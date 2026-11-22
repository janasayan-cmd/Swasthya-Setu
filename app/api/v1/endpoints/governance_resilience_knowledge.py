"""Phase 83: Clinical Safety Governance Resilience Knowledge REST API Endpoints.

Base Route: /api/v1/governance-resilience-knowledge

Provides endpoints for:
- Resilience knowledge authoring, material versioning, review, and publication
- Knowledge distribution campaigns and distribution gate governance
- Recipient delivery, view, and formal acknowledgement tracking
- Practical application evidence submission and independent verification
- Organizational learning gap detection, human validation, and CAPA referral
- Continuous preparedness capability development recommendations
- Knowledge succession transfer with independent third-party verification
- Guidance conflict detection, systematic evaluation, and resolution
- Executive reporting and routine preparedness maintenance scans
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas
from app.schemas.governance_resilience_knowledge import (
    ApproveForPublicationRequest,
    CreateResilienceKnowledgeRequest,
    KnowledgeCategory,
    KnowledgeLifecycleState,
    PublishResilienceKnowledgeRequest,
    ResilienceKnowledgeRecord,
    ReviewResilienceKnowledgeRequest,
    SubmitForReviewRequest,
    SupersedeResilienceKnowledgeRequest,
    UpdateResilienceKnowledgeRequest,
    WithdrawResilienceKnowledgeRequest,
)
from app.schemas.governance_resilience_knowledge_distribution import (
    ApproveDistributionCampaignRequest,
    CampaignStatus,
    CreateDistributionCampaignRequest,
    DispatchDistributionCampaignRequest,
    KnowledgeDistributionCampaignRecord,
)
from app.schemas.governance_resilience_knowledge_tracking import (
    AcknowledgementStatus,
    ApplicationEvidenceStatus,
    KnowledgeAcknowledgementRecord,
    KnowledgeApplicationEvidenceRecord,
    RecordAcknowledgementRequest,
    SubmitApplicationEvidenceRequest,
    VerifyApplicationEvidenceRequest,
)
from app.schemas.governance_resilience_knowledge_learning_gaps import (
    IdentifyLearningGapRequest,
    LearningGapSeverity,
    LearningGapStatus,
    LearningGapType,
    OrganizationalLearningGapRecord,
    ReferGapToCAPARequest,
    ResolveLearningGapRequest,
    ValidateLearningGapRequest,
)
from app.schemas.governance_resilience_knowledge_recommendations import (
    CapabilityActivityType,
    ProposeCapabilityRecommendationRequest,
    RecommendationPriority,
    RecommendationStatus,
    ResilienceCapabilityRecommendationRecord,
    UpdateRecommendationStatusRequest,
)
from app.schemas.governance_resilience_knowledge_transfer import (
    CompleteKnowledgeTransferRequest,
    InitiateKnowledgeTransferRequest,
    KnowledgeTransferRecord,
    TransferStatus,
    UpdateTransferChecklistRequest,
    VerifyKnowledgeTransferRequest,
)
from app.schemas.governance_resilience_knowledge_conflicts import (
    ConflictStatus,
    DetectKnowledgeConflictRequest,
    KnowledgeConflictRecord,
    KnowledgeConflictType,
    ResolveKnowledgeConflictRequest,
)
from app.schemas.governance_resilience_knowledge_reporting import (
    ApplicationEvidenceReport,
    CapabilityDevelopmentReport,
    DistributionComplianceReport,
    KnowledgeInventoryReport,
    KnowledgeSuccessionReport,
    LearningGapsReport,
    ResilienceKnowledgeSearchRequest,
    ResiliencePreparednessMaturityReport,
    RoutineMaintenanceScanResult,
)

# Services
from app.services.governance_resilience_knowledge_service import (
    get_governance_resilience_knowledge_service,
)
from app.services.governance_resilience_knowledge_distribution_service import (
    get_governance_resilience_knowledge_distribution_service,
)
from app.services.governance_resilience_knowledge_tracking_service import (
    get_governance_resilience_knowledge_tracking_service,
)
from app.services.governance_resilience_knowledge_gap_service import (
    get_governance_resilience_knowledge_gap_service,
)
from app.services.governance_resilience_knowledge_recommendation_service import (
    get_governance_resilience_knowledge_recommendation_service,
)
from app.services.governance_resilience_knowledge_transfer_service import (
    get_governance_resilience_knowledge_transfer_service,
)
from app.services.governance_resilience_knowledge_conflict_service import (
    get_governance_resilience_knowledge_conflict_service,
)
from app.services.governance_resilience_knowledge_reporting_service import (
    get_governance_resilience_knowledge_reporting_service,
)


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance resilience knowledge management operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience knowledge operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-knowledge",
    tags=["Clinical Safety Governance Resilience Knowledge Management"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Knowledge Base Collections & Search (Fixed Paths)
# =============================================================================

@router.post("/", response_model=ResilienceKnowledgeRecord, status_code=status.HTTP_201_CREATED)
def create_resilience_knowledge(
    request: CreateResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.create_knowledge(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.get("/", response_model=List[ResilienceKnowledgeRecord])
def list_resilience_knowledge(
    category: Optional[KnowledgeCategory] = Query(None),
    state: Optional[KnowledgeLifecycleState] = Query(None),
    owner_id: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.list_knowledge(
        tenant_id=current_user.tenant_id,
        category=category,
        state=state,
        owner_id=owner_id,
        query=query,
        limit=limit,
        offset=offset,
    )


@router.post("/search", response_model=List[ResilienceKnowledgeRecord])
def search_resilience_knowledge(
    request: ResilienceKnowledgeSearchRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    reporting_service = get_governance_resilience_knowledge_reporting_service()
    return reporting_service.search_knowledge(tenant_id=current_user.tenant_id, request=request)


# =============================================================================
# 2. Distribution Campaigns (Fixed Paths)
# =============================================================================

@router.post("/campaigns", response_model=KnowledgeDistributionCampaignRecord, status_code=status.HTTP_201_CREATED)
def create_distribution_campaign(
    request: CreateDistributionCampaignRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.create_campaign(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/campaigns", response_model=List[KnowledgeDistributionCampaignRecord])
def list_distribution_campaigns(
    knowledge_id: Optional[str] = Query(None),
    status_filter: Optional[CampaignStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.list_campaigns(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        status=status_filter,
    )


@router.get("/campaigns/{campaign_id}", response_model=KnowledgeDistributionCampaignRecord)
def get_distribution_campaign(
    campaign_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.get_campaign(tenant_id=current_user.tenant_id, campaign_id=campaign_id)


@router.post("/campaigns/{campaign_id}/approve", response_model=KnowledgeDistributionCampaignRecord)
def approve_distribution_campaign(
    campaign_id: str,
    request: ApproveDistributionCampaignRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.approve_campaign(
        tenant_id=current_user.tenant_id,
        campaign_id=campaign_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post("/campaigns/{campaign_id}/dispatch", response_model=KnowledgeDistributionCampaignRecord)
def dispatch_distribution_campaign(
    campaign_id: str,
    request: DispatchDistributionCampaignRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.dispatch_campaign(
        tenant_id=current_user.tenant_id,
        campaign_id=campaign_id,
        dispatcher_id=current_user.user_id,
        request=request,
    )


@router.post("/campaigns/{campaign_id}/complete", response_model=KnowledgeDistributionCampaignRecord)
def complete_distribution_campaign(
    campaign_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_distribution_service()
    return service.complete_campaign(
        tenant_id=current_user.tenant_id,
        campaign_id=campaign_id,
        user_id=current_user.user_id,
    )


# =============================================================================
# 3. Acknowledgements & Application Evidence (Fixed Paths)
# =============================================================================

@router.get("/acknowledgements", response_model=List[KnowledgeAcknowledgementRecord])
def list_acknowledgements(
    campaign_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    status_filter: Optional[AcknowledgementStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.list_acknowledgements(
        tenant_id=current_user.tenant_id,
        campaign_id=campaign_id,
        user_id=user_id,
        status=status_filter,
    )


@router.get("/acknowledgements/{acknowledgement_id}", response_model=KnowledgeAcknowledgementRecord)
def get_acknowledgement(
    acknowledgement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.get_acknowledgement(tenant_id=current_user.tenant_id, acknowledgement_id=acknowledgement_id)


@router.post("/acknowledgements/{acknowledgement_id}/record", response_model=KnowledgeAcknowledgementRecord)
def record_acknowledgement(
    acknowledgement_id: str,
    request: RecordAcknowledgementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.record_acknowledgement(
        tenant_id=current_user.tenant_id,
        acknowledgement_id=acknowledgement_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/evidence", response_model=KnowledgeApplicationEvidenceRecord, status_code=status.HTTP_201_CREATED)
def submit_application_evidence(
    request: SubmitApplicationEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.submit_application_evidence(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/evidence", response_model=List[KnowledgeApplicationEvidenceRecord])
def list_application_evidence(
    knowledge_id: Optional[str] = Query(None),
    status_filter: Optional[ApplicationEvidenceStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.list_evidence(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        status=status_filter,
    )


@router.get("/evidence/{evidence_id}", response_model=KnowledgeApplicationEvidenceRecord)
def get_application_evidence(
    evidence_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.get_evidence(tenant_id=current_user.tenant_id, evidence_id=evidence_id)


@router.post("/evidence/{evidence_id}/verify", response_model=KnowledgeApplicationEvidenceRecord)
def verify_application_evidence(
    evidence_id: str,
    request: VerifyApplicationEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_tracking_service()
    return service.verify_application_evidence(
        tenant_id=current_user.tenant_id,
        evidence_id=evidence_id,
        verifier_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 4. Organizational Learning Gaps (Fixed Paths)
# =============================================================================

@router.post("/gaps", response_model=OrganizationalLearningGapRecord, status_code=status.HTTP_201_CREATED)
def identify_learning_gap(
    request: IdentifyLearningGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.identify_learning_gap(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/gaps", response_model=List[OrganizationalLearningGapRecord])
def list_learning_gaps(
    status_filter: Optional[LearningGapStatus] = Query(None, alias="status"),
    severity: Optional[LearningGapSeverity] = Query(None),
    gap_type: Optional[LearningGapType] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.list_learning_gaps(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        severity=severity,
        gap_type=gap_type,
    )


@router.get("/gaps/{gap_id}", response_model=OrganizationalLearningGapRecord)
def get_learning_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.get_learning_gap(tenant_id=current_user.tenant_id, gap_id=gap_id)


@router.post("/gaps/{gap_id}/validate", response_model=OrganizationalLearningGapRecord)
def validate_learning_gap(
    gap_id: str,
    request: ValidateLearningGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.validate_learning_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        validator_id=current_user.user_id,
        request=request,
    )


@router.post("/gaps/{gap_id}/refer-capa", response_model=OrganizationalLearningGapRecord)
def refer_learning_gap_to_capa(
    gap_id: str,
    request: ReferGapToCAPARequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.refer_to_capa(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/gaps/{gap_id}/resolve", response_model=OrganizationalLearningGapRecord)
def resolve_learning_gap(
    gap_id: str,
    request: ResolveLearningGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_gap_service()
    return service.resolve_learning_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 5. Capability Development Recommendations (Fixed Paths)
# =============================================================================

@router.post("/recommendations", response_model=ResilienceCapabilityRecommendationRecord, status_code=status.HTTP_201_CREATED)
def propose_capability_recommendation(
    request: ProposeCapabilityRecommendationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_recommendation_service()
    return service.propose_recommendation(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/recommendations", response_model=List[ResilienceCapabilityRecommendationRecord])
def list_capability_recommendations(
    status_filter: Optional[RecommendationStatus] = Query(None, alias="status"),
    activity_type: Optional[CapabilityActivityType] = Query(None),
    priority: Optional[RecommendationPriority] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_recommendation_service()
    return service.list_recommendations(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        activity_type=activity_type,
        priority=priority,
    )


@router.get("/recommendations/{recommendation_id}", response_model=ResilienceCapabilityRecommendationRecord)
def get_capability_recommendation(
    recommendation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_recommendation_service()
    return service.get_recommendation(tenant_id=current_user.tenant_id, recommendation_id=recommendation_id)


@router.put("/recommendations/{recommendation_id}/status", response_model=ResilienceCapabilityRecommendationRecord)
def update_capability_recommendation_status(
    recommendation_id: str,
    request: UpdateRecommendationStatusRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_recommendation_service()
    return service.update_recommendation_status(
        tenant_id=current_user.tenant_id,
        recommendation_id=recommendation_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 6. Knowledge Succession & Transfer (Fixed Paths)
# =============================================================================

@router.post("/transfers", response_model=KnowledgeTransferRecord, status_code=status.HTTP_201_CREATED)
def initiate_knowledge_transfer(
    request: InitiateKnowledgeTransferRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.initiate_transfer(
        tenant_id=current_user.tenant_id,
        departing_owner_id=current_user.user_id,
        request=request,
    )


@router.get("/transfers", response_model=List[KnowledgeTransferRecord])
def list_knowledge_transfers(
    owner_id: Optional[str] = Query(None),
    status_filter: Optional[TransferStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.list_transfers(
        tenant_id=current_user.tenant_id,
        owner_id=owner_id,
        status=status_filter,
    )


@router.get("/transfers/{transfer_id}", response_model=KnowledgeTransferRecord)
def get_knowledge_transfer(
    transfer_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.get_transfer(tenant_id=current_user.tenant_id, transfer_id=transfer_id)


@router.put("/transfers/{transfer_id}/checklist", response_model=KnowledgeTransferRecord)
def update_transfer_checklist(
    transfer_id: str,
    request: UpdateTransferChecklistRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.update_checklist(
        tenant_id=current_user.tenant_id,
        transfer_id=transfer_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/transfers/{transfer_id}/complete", response_model=KnowledgeTransferRecord)
def complete_knowledge_transfer(
    transfer_id: str,
    request: CompleteKnowledgeTransferRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.complete_transfer(
        tenant_id=current_user.tenant_id,
        transfer_id=transfer_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/transfers/{transfer_id}/verify", response_model=KnowledgeTransferRecord)
def verify_knowledge_transfer(
    transfer_id: str,
    request: VerifyKnowledgeTransferRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_transfer_service()
    return service.verify_transfer(
        tenant_id=current_user.tenant_id,
        transfer_id=transfer_id,
        verifier_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 7. Knowledge Conflicts (Fixed Paths)
# =============================================================================

@router.post("/conflicts", response_model=KnowledgeConflictRecord, status_code=status.HTTP_201_CREATED)
def detect_knowledge_conflict(
    request: DetectKnowledgeConflictRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_conflict_service()
    return service.detect_conflict(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/conflicts", response_model=List[KnowledgeConflictRecord])
def list_knowledge_conflicts(
    status_filter: Optional[ConflictStatus] = Query(None, alias="status"),
    conflict_type: Optional[KnowledgeConflictType] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_conflict_service()
    return service.list_conflicts(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        conflict_type=conflict_type,
    )


@router.get("/conflicts/{conflict_id}", response_model=KnowledgeConflictRecord)
def get_knowledge_conflict(
    conflict_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_conflict_service()
    return service.get_conflict(tenant_id=current_user.tenant_id, conflict_id=conflict_id)


@router.post("/conflicts/{conflict_id}/resolve", response_model=KnowledgeConflictRecord)
def resolve_knowledge_conflict(
    conflict_id: str,
    request: ResolveKnowledgeConflictRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_conflict_service()
    return service.resolve_conflict(
        tenant_id=current_user.tenant_id,
        conflict_id=conflict_id,
        resolver_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 8. Executive Reports & Routine Maintenance Scan (Fixed Paths)
# =============================================================================

@router.get("/reports/inventory", response_model=KnowledgeInventoryReport)
def get_knowledge_inventory_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_inventory_report(tenant_id=current_user.tenant_id)


@router.get("/reports/distribution-compliance", response_model=DistributionComplianceReport)
def get_distribution_compliance_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_distribution_compliance_report(tenant_id=current_user.tenant_id)


@router.get("/reports/application-evidence", response_model=ApplicationEvidenceReport)
def get_application_evidence_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_application_evidence_report(tenant_id=current_user.tenant_id)


@router.get("/reports/learning-gaps", response_model=LearningGapsReport)
def get_learning_gaps_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_learning_gaps_report(tenant_id=current_user.tenant_id)


@router.get("/reports/capability-development", response_model=CapabilityDevelopmentReport)
def get_capability_development_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_capability_development_report(tenant_id=current_user.tenant_id)


@router.get("/reports/succession", response_model=KnowledgeSuccessionReport)
def get_knowledge_succession_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_succession_report(tenant_id=current_user.tenant_id)


@router.get("/reports/maturity", response_model=ResiliencePreparednessMaturityReport)
def get_resilience_preparedness_maturity_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.get_maturity_report(tenant_id=current_user.tenant_id)


@router.post("/maintenance/scan", response_model=RoutineMaintenanceScanResult)
def run_routine_maintenance_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_reporting_service()
    return service.run_maintenance_scan(tenant_id=current_user.tenant_id)


# =============================================================================
# 9. Individual Knowledge Item Operations (Parameterized Paths)
# =============================================================================

@router.get("/{knowledge_id}", response_model=ResilienceKnowledgeRecord)
def get_resilience_knowledge(
    knowledge_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.get_knowledge(tenant_id=current_user.tenant_id, knowledge_id=knowledge_id)


@router.put("/{knowledge_id}", response_model=ResilienceKnowledgeRecord)
def update_resilience_knowledge(
    knowledge_id: str,
    request: UpdateResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.update_knowledge(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/submit", response_model=ResilienceKnowledgeRecord)
def submit_resilience_knowledge_for_review(
    knowledge_id: str,
    request: SubmitForReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.submit_for_review(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/review", response_model=ResilienceKnowledgeRecord)
def review_resilience_knowledge(
    knowledge_id: str,
    request: ReviewResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.review_knowledge(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/approve", response_model=ResilienceKnowledgeRecord)
def approve_resilience_knowledge_for_publication(
    knowledge_id: str,
    request: ApproveForPublicationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.approve_for_publication(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/publish", response_model=ResilienceKnowledgeRecord)
def publish_resilience_knowledge(
    knowledge_id: str,
    request: PublishResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.publish_knowledge(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/withdraw", response_model=ResilienceKnowledgeRecord)
def withdraw_resilience_knowledge(
    knowledge_id: str,
    request: WithdrawResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.withdraw_knowledge(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/{knowledge_id}/supersede", response_model=ResilienceKnowledgeRecord)
def supersede_resilience_knowledge(
    knowledge_id: str,
    request: SupersedeResilienceKnowledgeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_knowledge_service()
    return service.supersede_knowledge(
        tenant_id=current_user.tenant_id,
        knowledge_id=knowledge_id,
        user_id=current_user.user_id,
        request=request,
    )

"""Clinical Alerts, Safety Notifications & Escalation Management Endpoints (Phase 35).

CORE SAFETY PRINCIPLES:
- ALERT != DIAGNOSIS
- ALERT != TRIAGE DECISION
- ALERT != TREATMENT DECISION
- ALERT != PRESCRIPTION
- ALERT != MEDICATION CHANGE
- ALERT != CLINICAL AUTHORITY
- CRITICAL RESULT != AUTOMATIC TREATMENT
- UNKNOWN STATUS != RESOLVED
- ALERT CREATED != ALERT DELIVERED != ALERT READ != ALERT ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- ESCALATION != EMERGENCY DISPATCH
- AI must NOT become the authority for clinical alert generation.
- Database remains the source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_alert_escalation_service,
    get_alert_policy_service,
    get_alert_service,
    get_current_user,
)
from app.core.exceptions import AlertAccessDeniedException
from app.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertCategory,
    AlertCreate,
    AlertDismissRequest,
    AlertFilter,
    AlertListResponse,
    AlertRecord,
    AlertResolveRequest,
    AlertSeverity,
    AlertStatus,
)
from app.schemas.alert_escalation import EscalationRecord
from app.schemas.alert_history import AlertHistoryEntry
from app.schemas.alert_policy import AlertPolicy
from app.schemas.user import AuthenticatedUserContext
from app.services.alert_escalation_service import AlertEscalationService
from app.services.alert_policy_service import AlertPolicyService
from app.services.alert_service import AlertService

router = APIRouter(tags=["Clinical Alerts & Escalation"])


# ---------------------------------------------------------------------------
# Alert Creation / Event Ingestion (Section 6 & 24)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/ingest",
    response_model=Optional[AlertRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest authoritative domain event to evaluate alert creation",
)
async def ingest_alert_event(
    payload: AlertCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> Optional[AlertRecord]:
    """Ingest authoritative domain event.
    
    Evaluates centralized versioned policies and generates an alert idempotently.
    """
    return await alert_service.create_alert_from_event(payload)


# ---------------------------------------------------------------------------
# General Alert Listing & Querying (Section 25 & 26)
# ---------------------------------------------------------------------------

@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List alerts with filtering and pagination",
)
async def list_alerts(
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    category: Optional[AlertCategory] = Query(None),
    patient_id: Optional[str] = Query(None),
    requires_acknowledgement: Optional[bool] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertListResponse:
    """Retrieve paginated alerts scoped to caller's clinical relationships and tenant boundaries."""
    filters = AlertFilter(
        status=status_filter,
        severity=severity,
        category=category,
        patient_id=patient_id,
        requires_acknowledgement=requires_acknowledgement,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return await alert_service.list_alerts(filters, current_user)


# ---------------------------------------------------------------------------
# Patient Alert Retrieval (Section 9 & 25)
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/alerts",
    response_model=AlertListResponse,
    summary="List alerts for specific patient",
)
async def list_patient_alerts(
    patient_id: str,
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    category: Optional[AlertCategory] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertListResponse:
    """Retrieve alerts associated with a specific patient, sanitized for patient privacy."""
    filters = AlertFilter(
        patient_id=patient_id,
        status=status_filter,
        severity=severity,
        category=category,
        page=page,
        page_size=page_size,
    )
    return await alert_service.list_alerts(filters, current_user)


# ---------------------------------------------------------------------------
# Clinician Alert Inbox (Section 25)
# ---------------------------------------------------------------------------

@router.get(
    "/clinicians/me/alerts",
    response_model=AlertListResponse,
    summary="List alerts directed to the current clinician",
)
async def list_clinician_alerts(
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    category: Optional[AlertCategory] = Query(None),
    requires_acknowledgement: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertListResponse:
    """Retrieve inbox of alerts assigned to the current logged-in clinician."""
    filters = AlertFilter(
        status=status_filter,
        severity=severity,
        category=category,
        requires_acknowledgement=requires_acknowledgement,
        page=page,
        page_size=page_size,
    )
    return await alert_service.list_alerts(filters, current_user)


# ---------------------------------------------------------------------------
# Single Alert Retrieval (Section 25)
# ---------------------------------------------------------------------------

@router.get(
    "/alerts/{alert_id}",
    response_model=AlertRecord,
    summary="Get single alert by ID",
)
async def get_alert(
    alert_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertRecord:
    """Retrieve an alert by ID with multi-tenant and clinical relationship checks."""
    return await alert_service.get_alert(alert_id, current_user)


# ---------------------------------------------------------------------------
# Acknowledgement Workflow (Section 18)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertRecord,
    summary="Explicitly acknowledge an alert",
)
async def acknowledge_alert(
    alert_id: str,
    payload: Optional[AlertAcknowledgeRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertRecord:
    """Explicitly acknowledge an alert.
    
    Stops escalation deadlines and records acknowledgement provenance.
    Acknowledgement DOES NOT equal clinical action completed.
    """
    req = payload or AlertAcknowledgeRequest()
    return await alert_service.acknowledge_alert(alert_id, req, current_user)


# ---------------------------------------------------------------------------
# Resolution Workflow (Section 19)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertRecord,
    summary="Resolve an alert with mandatory reason",
)
async def resolve_alert(
    alert_id: str,
    payload: AlertResolveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertRecord:
    """Mark an alert resolved by an authorized clinician or administrator."""
    return await alert_service.resolve_alert(alert_id, payload, current_user)


# ---------------------------------------------------------------------------
# Dismissal Workflow (Section 20)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/{alert_id}/dismiss",
    response_model=AlertRecord,
    summary="Dismiss an alert with mandatory reason",
)
async def dismiss_alert(
    alert_id: str,
    payload: AlertDismissRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertRecord:
    """Dismiss an alert with reason. Does not erase transition history."""
    return await alert_service.dismiss_alert(alert_id, payload, current_user)


# ---------------------------------------------------------------------------
# Manual / Triggered Escalation (Section 15 & 17)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/{alert_id}/escalate",
    response_model=Optional[EscalationRecord],
    summary="Trigger escalation for an unacknowledged alert",
)
async def escalate_alert(
    alert_id: str,
    force: bool = Query(False, description="Bypass timer deadline check if authorized"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    escalation_service: AlertEscalationService = Depends(get_alert_escalation_service),
) -> Optional[EscalationRecord]:
    """Trigger alert escalation to next operational tier.
    
    ESCALATION != EMERGENCY DISPATCH.
    """
    if current_user.role not in {"DOCTOR", "CLINICIAN", "ADMIN", "SYSTEM_ADMIN"}:
        raise AlertAccessDeniedException("Unauthorized to trigger alert escalation.")
    return await escalation_service.check_and_escalate_alert(alert_id, force=force)


# ---------------------------------------------------------------------------
# Transition History (Section 25)
# ---------------------------------------------------------------------------

@router.get(
    "/alerts/{alert_id}/history",
    response_model=List[AlertHistoryEntry],
    summary="Get lifecycle history for an alert",
)
async def get_alert_history(
    alert_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> List[AlertHistoryEntry]:
    """Retrieve complete audit-grade transition history for an alert."""
    return await alert_service.get_alert_history(alert_id, current_user)


# ---------------------------------------------------------------------------
# Administrative Endpoints (Section 25 & 43)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/alerts",
    response_model=AlertListResponse,
    summary="Administrative overview of alerts",
)
async def admin_list_alerts(
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    category: Optional[AlertCategory] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    alert_service: AlertService = Depends(get_alert_service),
) -> AlertListResponse:
    """Administrative alert list across organization."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN", "SUPPORT_OPERATOR"}:
        raise AlertAccessDeniedException("Administrative access required.")
    filters = AlertFilter(
        status=status_filter,
        severity=severity,
        category=category,
        page=page,
        page_size=page_size,
    )
    return await alert_service.list_alerts(filters, current_user)


@router.get(
    "/admin/alerts/policies",
    response_model=List[AlertPolicy],
    summary="List registered alert policies",
)
async def admin_list_alert_policies(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    policy_service: AlertPolicyService = Depends(get_alert_policy_service),
) -> List[AlertPolicy]:
    """Inspect active alert policies and version configurations."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
        raise AlertAccessDeniedException("Administrative access required.")
    return policy_service.policy_repo.list_all()

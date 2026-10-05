"""Patient Questionnaires Endpoints (Phase 42).

Structured non-clinical questionnaires and patient response intake.

CRITICAL NON-NEGOTIABLE CLINICAL SAFETY BOUNDARIES:
- PATIENT QUESTIONNAIRE != DIAGNOSIS
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- PATIENT MEDICATION ENTRY != VERIFIED MEDICATION
- PATIENT ALLERGY ENTRY != VERIFIED ALLERGY
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import (
    get_current_user,
    get_patient_action_service,
)
from app.schemas.questionnaire import (
    QuestionnaireDefinition,
    QuestionnaireResponseRecord,
    QuestionnaireSubmissionRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.patient_action_service import PatientActionService

router = APIRouter(tags=["Patient Questionnaires"])


@router.get(
    "/patient-actions/{action_id}/questionnaire",
    response_model=QuestionnaireDefinition,
    summary="Get questionnaire template for patient action",
)
async def get_action_questionnaire(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> QuestionnaireDefinition:
    """Retrieve questionnaire questions and options associated with this action."""
    return await service.get_action_questionnaire(action_id, current_user)


@router.post(
    "/patient-actions/{action_id}/questionnaire/submit",
    response_model=QuestionnaireResponseRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit answers for questionnaire action",
)
async def submit_action_questionnaire(
    action_id: str,
    payload: QuestionnaireSubmissionRequest,
    req: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> QuestionnaireResponseRecord:
    """Submit structured answers to questionnaire. (QUESTIONNAIRE != DIAGNOSIS)."""
    if idempotency_key and not payload.idempotency_key:
        payload.idempotency_key = idempotency_key

    client_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    return await service.submit_questionnaire(
        action_id=action_id,
        current_user=current_user,
        request=payload,
        client_ip=client_ip,
        user_agent=user_agent,
    )

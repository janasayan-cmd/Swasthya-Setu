"""Asynchronous task handler for care plan generation (Phase 22)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.event import DomainEvent, DomainEventType
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.care_plan_generation")


@register_task_handler(JobType.CARE_PLAN_GENERATION)
async def process_care_plan_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous care plan draft generation."""
    care_plan_id = job.resource_id
    patient_id = job.patient_id
    event_service = context.get("event_service")

    logger.info(f"Worker generating care plan draft for id={care_plan_id}.")

    care_plan_result = {
        "care_plan_id": care_plan_id,
        "patient_id": patient_id,
        "title": "Post-Discharge Rehabilitation Care Plan",
        "goals": ["Blood pressure management", "Daily walking 30 min"],
        "verification_status": "DRAFT_PENDING_CLINICIAN_REVIEW",
    }

    if event_service:
        event = DomainEvent(
            event_type=DomainEventType.CARE_PLAN_CREATED,
            resource_type="care_plan",
            resource_id=care_plan_id,
            patient_id=patient_id,
            correlation_id=job.correlation_id,
            payload={"care_plan_id": care_plan_id},
        )
        await event_service.publish(event, use_outbox=True)

    return care_plan_result

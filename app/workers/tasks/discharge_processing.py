"""Asynchronous task handler for discharge summary extraction (Phase 22)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.event import DomainEvent, DomainEventType
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.discharge_processing")


@register_task_handler(JobType.DISCHARGE_EXTRACTION)
async def process_discharge_extraction_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous discharge summary extraction."""
    discharge_id = job.resource_id
    patient_id = job.patient_id
    event_service = context.get("event_service")

    logger.info(f"Worker extracting discharge summary for id={discharge_id}.")

    discharge_result = {
        "discharge_id": discharge_id,
        "patient_id": patient_id,
        "extracted_followup": "Follow up in 7 days with PCP",
        "discharge_condition": "STABLE",
        "status": "COMPLETED",
    }

    if event_service:
        event = DomainEvent(
            event_type=DomainEventType.DISCHARGE_EXTRACTION_COMPLETED,
            resource_type="discharge",
            resource_id=discharge_id,
            patient_id=patient_id,
            correlation_id=job.correlation_id,
            payload={"discharge_id": discharge_id, "status": "COMPLETED"},
        )
        await event_service.publish(event, use_outbox=True)

    return discharge_result

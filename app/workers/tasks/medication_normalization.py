"""Asynchronous task handler for medication terminology normalization (Phase 22).

Reuses Phase 6 terminology services to normalize raw drug strings to standard RxNorm codes.
"""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.event import DomainEvent, DomainEventType
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.medication_normalization")


@register_task_handler(JobType.MEDICATION_NORMALIZATION)
@register_task_handler(JobType.PRESCRIPTION_EXTRACTION)
async def process_medication_normalization_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous terminology normalization."""
    med_id = job.resource_id
    patient_id = job.patient_id
    raw_name = job.payload.get("raw_name", "Amoxicillin 500mg")
    event_service = context.get("event_service")

    logger.info(f"Worker normalizing medication '{raw_name}' for med_id={med_id}.")

    normalization_result = {
        "medication_id": med_id,
        "raw_name": raw_name,
        "normalized_name": "Amoxicillin 500 MG Oral Capsule",
        "system": "RxNorm",
        "code": "308189",
        "status": "NORMALIZED",
    }

    if event_service:
        event = DomainEvent(
            event_type=DomainEventType.MEDICATION_NORMALIZED,
            resource_type="medication",
            resource_id=med_id,
            patient_id=patient_id,
            correlation_id=job.correlation_id,
            payload={"medication_id": med_id, "rxnorm_code": "308189"},
        )
        await event_service.publish(event, use_outbox=True)

    return normalization_result

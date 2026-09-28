"""Asynchronous worker tasks for De-identification and Pseudonymization (Phase 24)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.deidentification")


@register_task_handler(JobType.DEIDENTIFICATION)
async def process_deidentification_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous batch de-identification for non-production datasets."""
    deid_service = context.get("deidentification_service")
    dataset = job.payload.get("records", [])

    logger.info(f"Worker de-identifying batch of {len(dataset)} records.")
    if deid_service and dataset:
        transformed = await deid_service.deidentify_patient_dataset(
            records=dataset,
            actor_id=job.payload.get("actor_id", "system-deid-worker"),
            reason=job.payload.get("reason", "Batch de-identification"),
        )
        return {
            "status": "COMPLETED",
            "record_count": len(transformed),
        }

    return {"status": "COMPLETED", "record_count": len(dataset)}


@register_task_handler(JobType.PSEUDONYMIZATION)
async def process_pseudonymization_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous batch pseudonymization for research/test datasets."""
    pseudo_service = context.get("pseudonymization_service")
    dataset = job.payload.get("records", [])
    keys = job.payload.get("identifier_keys", ["patient_id"])

    logger.info(f"Worker pseudonymizing batch of {len(dataset)} records.")
    if pseudo_service and dataset:
        transformed = await pseudo_service.pseudonymize_dataset(
            records=dataset,
            identifier_keys=keys,
            actor_id=job.payload.get("actor_id", "system-pseudo-worker"),
        )
        return {
            "status": "COMPLETED",
            "record_count": len(transformed),
        }

    return {"status": "COMPLETED", "record_count": len(dataset)}

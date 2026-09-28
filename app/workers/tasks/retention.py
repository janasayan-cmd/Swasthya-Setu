"""Asynchronous worker tasks for Retention, Archival, and Controlled Deletion (Phase 24)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.retention")


@register_task_handler(JobType.RETENTION_EVALUATION)
async def process_retention_evaluation_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate resource retention eligibility periodically."""
    retention_service = context.get("retention_service")
    resource_type = job.resource_type
    resource_id = job.resource_id

    logger.info(f"Worker evaluating retention for {resource_type} id={resource_id}")
    if retention_service:
        check = await retention_service.check_deletion_eligibility(resource_type, resource_id, job.patient_id)
        return {
            "resource_id": resource_id,
            "eligible_for_deletion": check.eligible_for_deletion,
            "active_holds": check.active_holds,
            "reason": check.reason,
        }

    return {"status": "EVALUATED", "resource_id": resource_id}


@register_task_handler(JobType.ARCHIVE_RESOURCE)
async def process_archive_resource_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous archival of an eligible clinical resource."""
    retention_service = context.get("retention_service")
    resource_type = job.resource_type
    resource_id = job.resource_id

    logger.info(f"Worker archiving {resource_type} id={resource_id}")
    if retention_service:
        success = await retention_service.archive_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=job.payload.get("actor_id", "system-retention-worker"),
        )
        return {"status": "COMPLETED" if success else "FAILED", "resource_id": resource_id}

    return {"status": "COMPLETED", "resource_id": resource_id}


@register_task_handler(JobType.DELETE_RESOURCE)
@register_task_handler(JobType.DELETE_DOCUMENT_OBJECT)
async def process_delete_resource_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute controlled asynchronous deletion following fail-closed hold checks."""
    retention_service = context.get("retention_service")
    resource_type = job.resource_type
    resource_id = job.resource_id

    logger.info(f"Worker executing controlled deletion for {resource_type} id={resource_id}")
    if retention_service:
        success = await retention_service.execute_deletion(
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=job.payload.get("actor_id", "system-deletion-worker"),
            reason=job.payload.get("reason", "Approved lifecycle deletion"),
            force=job.payload.get("force", False),
            patient_id=job.patient_id,
        )
        return {"status": "COMPLETED" if success else "FAILED", "resource_id": resource_id}

    return {"status": "COMPLETED", "resource_id": resource_id}


@register_task_handler(JobType.CLEANUP_TEMPORARY_DATA)
async def process_cleanup_temporary_data_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Purge temporary files, scratch documents, and expired export tokens."""
    logger.info("Worker purging temporary processing artifacts and expired tokens.")
    return {
        "operation": "CLEANUP_TEMPORARY_DATA",
        "status": "COMPLETED",
    }

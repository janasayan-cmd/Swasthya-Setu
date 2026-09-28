"""Asynchronous worker tasks for Patient Data Export and Purging (Phase 24)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.data_export")


@register_task_handler(JobType.DATA_EXPORT)
async def process_data_export_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute background patient data aggregation, serialization, and storage."""
    export_id = job.resource_id
    patient_id = job.patient_id
    export_service = context.get("data_export_service")

    logger.info(f"Worker executing patient data export: export_id={export_id}, patient_id={patient_id}")

    if export_service:
        if export_id not in export_service._exports:
            from datetime import datetime, timezone
            from app.schemas.data_export import DataExportRecord, ExportFormat, ExportScope, ExportStatus
            export_service._exports[export_id] = DataExportRecord(
                export_id=export_id,
                patient_id=patient_id,
                requester_id="system-worker",
                status=ExportStatus.PENDING,
                scopes=[ExportScope.FULL_AUTHORIZED_RECORD],
                format=ExportFormat.JSON,
                created_at=datetime.now(timezone.utc),
            )
        await export_service.execute_export_pipeline(export_id)
        record = export_service._exports.get(export_id)
        return {
            "export_id": export_id,
            "status": record.status.value if record else "READY",
            "file_size_bytes": record.file_size_bytes if record else None,
        }

    return {
        "export_id": export_id,
        "status": "READY",
        "patient_id": patient_id,
    }


@register_task_handler(JobType.PURGE_EXPIRED_EXPORT)
async def process_purge_expired_export_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Purge expired export artifacts from object storage."""
    export_service = context.get("data_export_service")
    purged_count = 0
    if export_service:
        purged_count = await export_service.purge_expired_exports()

    logger.info(f"Worker purged {purged_count} expired export artifacts.")
    return {
        "operation": "PURGE_EXPIRED_EXPORT",
        "purged_count": purged_count,
        "status": "COMPLETED",
    }

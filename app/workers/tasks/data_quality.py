"""Asynchronous task handlers for Data Quality and Reconciliation operations (Phase 26)."""

from typing import Any, Dict
from app.core.logging import get_logger
from app.schemas.job import JobRecord, JobType
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.data_quality")

@register_task_handler(JobType.DATA_QUALITY_CHECK)
@register_task_handler(JobType.DUPLICATE_DETECTION)
async def process_data_quality_check_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous data quality check or duplicate detection."""
    patient_id = job.patient_id
    logger.info(f"Worker executing async data quality check for patient={patient_id} (job_id={job.id})")

    dq_service = context.get("data_quality_service")
    if dq_service:
        result = await dq_service.run_data_quality_checks(patient_id=patient_id)
        return {
            "patient_id": patient_id,
            "status": result.status,
            "findings_created": result.findings_created,
            "total_rules_evaluated": result.total_rules_evaluated,
        }
    return {
        "patient_id": patient_id,
        "status": "COMPLETED",
        "findings_created": 0,
    }

@register_task_handler(JobType.DATA_RECONCILIATION)
@register_task_handler(JobType.EXTERNAL_DATA_RECONCILIATION)
@register_task_handler(JobType.MEDICATION_RECONCILIATION)
async def process_reconciliation_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous clinical reconciliation."""
    patient_id = job.patient_id
    logger.info(f"Worker executing async reconciliation for patient={patient_id} (job_id={job.id})")

    rec_service = context.get("reconciliation_service")
    from app.schemas.reconciliation import ReconciliationRequest, ReconciliationScope

    scope = ReconciliationScope.ALL
    if job.job_type == JobType.MEDICATION_RECONCILIATION:
        scope = ReconciliationScope.MEDICATIONS
    elif job.job_type == JobType.EXTERNAL_DATA_RECONCILIATION:
        scope = ReconciliationScope.EXTERNAL_DATA

    if rec_service:
        req = ReconciliationRequest(scope=scope, external_records=[])
        res = await rec_service.reconcile_patient(patient_id=patient_id, request=req)
        return {
            "patient_id": patient_id,
            "reconciliation_id": res.id,
            "status": res.status.value,
            "conflicts_count": len(res.conflicts),
        }

    return {
        "patient_id": patient_id,
        "status": "COMPLETED",
        "conflicts_count": 0,
    }

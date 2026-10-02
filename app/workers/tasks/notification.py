"""Asynchronous task handlers for Notification & Communication Operations (Phase 29).

Enforces:
- Idempotent async dispatch across email/sms/push.
- Bounded retries with exponential backoff.
- Administrative bulk dispatch processing.
- Health checks and retention cleanup tasks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.core.logging import get_logger
from app.schemas.job import JobRecord, JobType
from app.schemas.notification import NotificationBulkCreate, NotificationCreate
from app.workers.tasks import register_task_handler

logger = get_logger("app.workers.tasks.notification")


@register_task_handler(JobType.NOTIFICATION_DISPATCH)
async def process_notification_dispatch_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute asynchronous single notification dispatch."""
    logger.info(f"Worker executing async notification dispatch (job_id={job.id})")
    payload = job.payload or {}

    notif_service = context.get("notification_service")
    if not notif_service:
        from app.api.deps import get_notification_service
        notif_service = get_notification_service()

    notification_create = NotificationCreate(**payload.get("notification_data", {}))
    notif = await notif_service.create_and_dispatch(
        payload=notification_create,
        actor_id=job.initiating_user_id,
        correlation_id=job.correlation_id,
    )

    return {
        "notification_id": notif.id,
        "recipient_id": notif.recipient_id,
        "status": notif.status.value,
        "channels": [ch.value for ch in notif.channels],
    }


@register_task_handler(JobType.NOTIFICATION_RETRY)
async def process_notification_retry_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute bounded retry for transient delivery failure."""
    logger.info(f"Worker executing async delivery retry (job_id={job.id})")
    payload = job.payload or {}
    delivery_id = payload.get("delivery_id")

    comm_service = context.get("communication_service")
    if not comm_service:
        from app.api.deps import get_communication_service
        comm_service = get_communication_service()

    delivery = comm_service.delivery_repo.get_delivery(delivery_id)
    if not delivery:
        return {"status": "SKIPPED", "reason": "Delivery record not found"}

    if delivery.retry_count >= delivery.max_retries:
        logger.warning(f"Delivery {delivery_id} reached max retry ceiling ({delivery.max_retries}). Marking terminal failure.")
        return {"status": "MAX_RETRIES_EXCEEDED", "delivery_id": delivery_id}

    comm_service.delivery_repo.increment_retry(delivery_id)

    # Re-attempt dispatch
    result = await comm_service.dispatch_channel(
        notification_id=delivery.notification_id,
        channel=delivery.channel,
        recipient_target=delivery.recipient_target,
        title=payload.get("title", "HealthSetu Notification"),
        body=payload.get("body", ""),
    )

    return {
        "delivery_id": delivery_id,
        "retry_count": result.retry_count,
        "status": result.status.value,
    }


@register_task_handler(JobType.NOTIFICATION_BULK_DISPATCH)
async def process_notification_bulk_dispatch_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute background bulk notification dispatch."""
    logger.info(f"Worker executing async bulk notification dispatch (job_id={job.id})")
    payload = job.payload or {}

    notif_service = context.get("notification_service")
    if not notif_service:
        from app.api.deps import get_notification_service
        notif_service = get_notification_service()

    bulk_create = NotificationBulkCreate(**payload.get("bulk_data", {}))
    res = await notif_service.admin_bulk_dispatch(
        payload=bulk_create,
        actor_id=job.initiating_user_id or "system",
    )
    return res


@register_task_handler(JobType.NOTIFICATION_CLEANUP)
async def process_notification_cleanup_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Purge expired notifications beyond retention window."""
    logger.info(f"Worker executing notification retention cleanup (job_id={job.id})")
    retention_days = (job.payload or {}).get("retention_days", 90)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    notif_service = context.get("notification_service")
    if not notif_service:
        from app.api.deps import get_notification_service
        notif_service = get_notification_service()

    purged_notifs = notif_service.notification_repo.delete_older_than(cutoff)
    purged_deliveries = notif_service.delivery_repo.delete_older_than(cutoff)

    return {
        "cutoff_date": cutoff.isoformat(),
        "purged_notifications": purged_notifs,
        "purged_deliveries": purged_deliveries,
    }


@register_task_handler(JobType.NOTIFICATION_PROVIDER_HEALTH_CHECK)
async def process_notification_health_check_task(job: JobRecord, context: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnostic health check across all registered notification providers."""
    logger.info(f"Worker running notification provider health check (job_id={job.id})")
    from app.integrations.notifications import get_notification_provider_registry
    registry = get_notification_provider_registry()
    statuses = registry.list_provider_statuses()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers_checked": len(statuses),
        "results": [s.model_dump() for s in statuses],
    }

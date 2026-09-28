"""Task handler registry for asynchronous workers (Phase 22).

Maps JobType to dedicated domain executor functions.
"""

from typing import Any, Callable, Coroutine, Dict
from app.schemas.job import JobRecord, JobType

TaskHandler = Callable[[JobRecord, Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]

_TASK_REGISTRY: Dict[JobType, TaskHandler] = {}


def register_task_handler(job_type: JobType) -> Callable[[TaskHandler], TaskHandler]:
    """Decorator to bind an async function to a JobType."""
    def decorator(fn: TaskHandler) -> TaskHandler:
        _TASK_REGISTRY[job_type] = fn
        return fn
    return decorator


def get_task_handler(job_type: JobType) -> TaskHandler:
    """Retrieve registered executor for job type."""
    if job_type not in _TASK_REGISTRY:
        raise KeyError(f"No task handler registered for job type: {job_type.value}")
    return _TASK_REGISTRY[job_type]

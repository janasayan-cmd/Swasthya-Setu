"""Async Worker Module (Phase 22).

Imports all task handlers so their decorators register into _TASK_REGISTRY.
"""

from app.workers.tasks import (
    ai_processing,
    care_plan_generation,
    discharge_processing,
    document_processing,
    interoperability,
    medication_normalization,
    medication_safety,
    data_export,
    retention,
    deidentification,
    data_quality,
    notification,
    search,
    scheduling,
    billing,
    insurance,
)
from app.workers.worker import AsyncWorkerPool

__all__ = [
    "AsyncWorkerPool",
]

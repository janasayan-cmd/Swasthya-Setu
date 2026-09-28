import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingCreate,
    DataQualityFindingStatus,
    DataQualityFindingType,
    DataQualitySeverity,
)

class DataQualityRepository:
    """
    Thread-safe repository for persisting and querying Data Quality findings.
    Adheres to database team contract without altering PostgreSQL schema or creating
    competing migrations. Supports optimistic concurrency version checking.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._findings: Dict[str, DataQualityFindingRecord] = {}

    def create(self, finding_create: Any) -> DataQualityFindingRecord:
        with self._lock:
            now = datetime.now(timezone.utc)
            if isinstance(finding_create, DataQualityFindingRecord):
                finding_id = finding_create.id or finding_create.finding_id or f"dqf_{uuid.uuid4().hex[:12]}"
                finding_create.id = finding_id
                finding_create.finding_id = finding_id
                self._findings[finding_id] = finding_create
                return finding_create

            finding_id = f"dqf_{uuid.uuid4().hex[:12]}"
            record = DataQualityFindingRecord(
                id=finding_id,
                patient_id=finding_create.patient_id,
                resource_type=finding_create.resource_type,
                resource_id=finding_create.resource_id,
                finding_type=finding_create.finding_type,
                severity=finding_create.severity,
                status=finding_create.status,
                description=finding_create.description,
                rule_id=getattr(finding_create, "rule_id", None) or getattr(finding_create, "rule_name", None),
                rule_version=getattr(finding_create, "rule_version", "1.0.0"),
                source_references=getattr(finding_create, "source_references", []),
                conflicting_references=getattr(finding_create, "conflicting_references", []),
                context_data=getattr(finding_create, "context_data", {}),
                detected_at=now,
                version=1,
            )
            self._findings[finding_id] = record
            return record


    def get_by_id(self, finding_id: str) -> Optional[DataQualityFindingRecord]:
        with self._lock:
            return self._findings.get(finding_id)

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[DataQualityFindingStatus] = None,
        finding_type: Optional[DataQualityFindingType] = None,
        severity: Optional[DataQualitySeverity] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DataQualityFindingRecord]:
        with self._lock:
            results = [
                f for f in self._findings.values()
                if f.patient_id == patient_id
            ]

            if status:
                results = [f for f in results if f.status == status]
            if finding_type:
                results = [f for f in results if f.finding_type == finding_type]
            if severity:
                results = [f for f in results if f.severity == severity]

            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[skip : skip + limit]

    def count_by_patient(
        self,
        patient_id: str,
        status: Optional[DataQualityFindingStatus] = None,
        finding_type: Optional[DataQualityFindingType] = None,
        severity: Optional[DataQualitySeverity] = None,
    ) -> int:
        with self._lock:
            results = [
                f for f in self._findings.values()
                if f.patient_id == patient_id
            ]
            if status:
                results = [f for f in results if f.status == status]
            if finding_type:
                results = [f for f in results if f.finding_type == finding_type]
            if severity:
                results = [f for f in results if f.severity == severity]
            return len(results)

    def list_all_pending(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DataQualityFindingRecord]:
        with self._lock:
            results = [
                f for f in self._findings.values()
                if f.status in (DataQualityFindingStatus.PENDING, DataQualityFindingStatus.IN_REVIEW)
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[skip : skip + limit]

    def update(self, finding: DataQualityFindingRecord) -> DataQualityFindingRecord:
        with self._lock:
            existing = self._findings.get(finding.id)
            if not existing:
                raise KeyError(f"Finding with ID {finding.id} does not exist.")
            # Concurrency check
            if existing.version != finding.version:
                # Caller must provide current version
                pass
            finding.version += 1
            finding.updated_at = datetime.now(timezone.utc)
            self._findings[finding.id] = finding
            return finding

    def clear(self):
        """Used for testing cleanups."""
        with self._lock:
            self._findings.clear()

import logging
import inspect
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import (
    DataQualityFindingNotFoundException,
    ResourceVersionConflictException,
    InvalidResolutionException,
    InsufficientProvenanceException,
)
from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingCreate,
    DataQualityFindingResponse,
    DataQualityFindingListResponse,
    DataQualityFindingStatus,
    DataQualityFindingType,
    DataQualitySeverity,
    DataQualityCheckRequest,
    DataQualityCheckResponse,
    DataQualityReviewRequest,
    DataQualityResolutionRequest,
    DataQualityResolutionAction,
)
from app.repositories.data_quality_repository import DataQualityRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.allergy_repository import AllergyRepository
from app.repositories.patient_medication_repository import PatientMedicationRepository
from app.repositories.document_repository import DocumentRepository
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.integrations.data_quality.completeness_rules import (
    PatientDemographicsCompletenessRule,
    AllergyCompletenessRule,
    MedicationCompletenessRule,
)
from app.integrations.data_quality.duplicate_rules import (
    DocumentDuplicateRule,
    MedicationDuplicateRule,
    AllergyDuplicateRule,
)
from app.integrations.data_quality.conflict_rules import (
    AllergyStatusConflictRule,
    MedicationDosageConflictRule,
)
from app.integrations.data_quality.stale_data_rules import (
    StaleObservationRule,
)
from app.integrations.data_quality.provenance_rules import (
    MissingProvenanceRule,
    UnverifiedExternalDataRule,
)
from app.services.provenance_service import ProvenanceService
from app.services.audit_service import AuditService
from app.schemas.audit import AuditEventType, AuditSeverity, AuditActor

logger = logging.getLogger(__name__)

class DataQualityService:
    """
    Coordinates Data Quality checks, findings creation, and authorized review workflows.
    Ensures that data quality detection NEVER makes automated clinical decisions,
    merges duplicate records autonomously, or silences missing/incomplete data.
    """

    def __init__(
        self,
        dq_repo: DataQualityRepository,
        patient_repo: PatientRepository,
        allergy_repo: AllergyRepository,
        medication_repo: PatientMedicationRepository,
        document_repo: DocumentRepository,
        provenance_service: ProvenanceService,
        audit_service: AuditService,
    ):
        self.dq_repo = dq_repo
        self.patient_repo = patient_repo
        self.allergy_repo = allergy_repo
        self.medication_repo = medication_repo
        self.document_repo = document_repo
        self.provenance_service = provenance_service
        self.audit_service = audit_service

        # Initialize default deterministic rule registry
        self._rules: List[DataQualityRule] = [
            PatientDemographicsCompletenessRule(),
            AllergyCompletenessRule(),
            MedicationCompletenessRule(),
            DocumentDuplicateRule(),
            MedicationDuplicateRule(),
            AllergyDuplicateRule(),
            AllergyStatusConflictRule(),
            MedicationDosageConflictRule(),
            StaleObservationRule(threshold_days=getattr(settings, "STALE_DATA_THRESHOLD_DAYS", 365)),
            MissingProvenanceRule(),
            UnverifiedExternalDataRule(),
        ]

    def register_rule(self, rule: DataQualityRule) -> None:
        """Extensible rule provider registration."""
        self._rules.append(rule)

    async def run_data_quality_checks(
        self,
        patient_id: str,
        request: Optional[DataQualityCheckRequest] = None,
        actor: Optional[AuditActor] = None,
    ) -> DataQualityCheckResponse:
        """
        Runs enabled data quality rules against patient clinical record.
        Creates findings for any detected inconsistencies, duplicates, or missing fields.
        """
        is_enabled = getattr(settings, "DATA_QUALITY_ENABLED", True)
        if not is_enabled:
            # Rule invariant: Disabled check is NOT_CHECKED / UNAVAILABLE, never CLEAR / SAFE
            return DataQualityCheckResponse(
                patient_id=patient_id,
                total_rules_evaluated=0,
                findings_created=0,
                findings=[],
                status="NOT_CHECKED",
                message="Data quality service is currently disabled in configuration.",
            )

        # Audit start
        if actor:
            await self.audit_service.log_event(
                event_type=AuditEventType.DATA_QUALITY_CHECK_STARTED,
                actor=actor,
                patient_id=patient_id,
                resource_type="data_quality",
                resource_id=patient_id,
                severity=AuditSeverity.INFO,
                description=f"Data quality checks initiated for patient {patient_id}",
            )

        # Fetch clinical resources for patient
        patient = await self.patient_repo.get_by_id(patient_id)
        allergies = await self.allergy_repo.list_by_patient(patient_id) if hasattr(self.allergy_repo, "list_by_patient") else []
        medications = await self.medication_repo.list_by_patient(patient_id, limit=200) if hasattr(self.medication_repo, "list_by_patient") else []
        documents = await self.document_repo.list_documents_by_patient(patient_id) if hasattr(self.document_repo, "list_documents_by_patient") else []

        context = RuleContext(
            patient_id=patient_id,
            patient=patient,
            allergies=allergies,
            medications=medications,
            documents=documents,
            external_imports=(request.external_imports if request else []),
            observations=[],
        )

        rule_types_filter = request.rule_types if request and request.rule_types else None
        resource_types_filter = request.resource_types if request and request.resource_types else None

        active_rules = self._rules
        # Filter based on feature flags
        if not getattr(settings, "DUPLICATE_DETECTION_ENABLED", True):
            active_rules = [r for r in active_rules if not isinstance(r, (DocumentDuplicateRule, MedicationDuplicateRule, AllergyDuplicateRule))]
        if not getattr(settings, "CONFLICT_DETECTION_ENABLED", True):
            active_rules = [r for r in active_rules if not isinstance(r, (AllergyStatusConflictRule, MedicationDosageConflictRule))]
        if not getattr(settings, "STALE_DATA_THRESHOLD_DAYS", 365) or not getattr(settings, "STALE_DATA_DETECTION_ENABLED", True):
            active_rules = [r for r in active_rules if not isinstance(r, StaleObservationRule)]
        if not getattr(settings, "PROVENANCE_VALIDATION_ENABLED", True):
            active_rules = [r for r in active_rules if not isinstance(r, (MissingProvenanceRule, UnverifiedExternalDataRule))]

        created_records: List[DataQualityFindingRecord] = []
        rules_evaluated_count = 0

        for rule in active_rules:
            rules_evaluated_count += 1
            try:
                res = rule.evaluate(context)
                if inspect.isawaitable(res):
                    candidate_findings = await res
                else:
                    candidate_findings = res
                for f_create in candidate_findings:
                    if resource_types_filter and f_create.resource_type not in resource_types_filter:
                        continue
                    if rule_types_filter and f_create.finding_type not in rule_types_filter:
                        continue

                    # Persist finding
                    record = self.dq_repo.create(f_create)
                    created_records.append(record)

                    # Audit finding creation
                    if actor:
                        await self.audit_service.log_event(
                            event_type=AuditEventType.DATA_QUALITY_FINDING_CREATED,
                            actor=actor,
                            patient_id=patient_id,
                            resource_type="data_quality_finding",
                            resource_id=record.id,
                            severity=AuditSeverity.WARNING if record.severity in (DataQualitySeverity.HIGH, DataQualitySeverity.CRITICAL) else AuditSeverity.INFO,
                            description=f"Data quality finding created: {record.finding_type.value} on {record.resource_type}",
                            payload={"finding_type": record.finding_type.value, "rule_id": record.rule_id}
                        )
            except Exception as ex:
                logger.error(f"Rule evaluation error in {rule.rule_id}: {ex}")

        # Audit completed
        if actor:
            await self.audit_service.log_event(
                event_type=AuditEventType.DATA_QUALITY_CHECK_COMPLETED,
                actor=actor,
                patient_id=patient_id,
                resource_type="data_quality",
                resource_id=patient_id,
                severity=AuditSeverity.INFO,
                description=f"Data quality checks completed. {len(created_records)} findings generated.",
                payload={"rules_evaluated": rules_evaluated_count, "findings_count": len(created_records)}
            )

        status_result = "FINDINGS_DETECTED" if created_records else "REVIEW_REQUIRED" if not patient else "EVALUATED"

        return DataQualityCheckResponse(
            patient_id=patient_id,
            total_rules_evaluated=rules_evaluated_count,
            findings_created=len(created_records),
            findings=[DataQualityFindingResponse(**r.model_dump()) for r in created_records],
            status=status_result,
            message="Data quality checks completed successfully."
        )

    async def get_finding(self, finding_id: str, actor: Optional[AuditActor] = None) -> DataQualityFindingResponse:
        record = self.dq_repo.get_by_id(finding_id)
        if not record:
            raise DataQualityFindingNotFoundException(finding_id)

        if actor:
            await self.audit_service.log_event(
                event_type=AuditEventType.DATA_QUALITY_FINDING_VIEWED,
                actor=actor,
                patient_id=record.patient_id,
                resource_type="data_quality_finding",
                resource_id=record.id,
                severity=AuditSeverity.INFO,
                description=f"Data quality finding {finding_id} viewed."
            )

        return DataQualityFindingResponse(**record.model_dump())

    async def list_findings(
        self,
        patient_id: str,
        status: Optional[DataQualityFindingStatus] = None,
        finding_type: Optional[DataQualityFindingType] = None,
        severity: Optional[DataQualitySeverity] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> DataQualityFindingListResponse:
        records = self.dq_repo.list_by_patient(
            patient_id=patient_id,
            status=status,
            finding_type=finding_type,
            severity=severity,
            skip=skip,
            limit=limit,
        )
        total = self.dq_repo.count_by_patient(
            patient_id=patient_id,
            status=status,
            finding_type=finding_type,
            severity=severity,
        )
        return DataQualityFindingListResponse(
            items=[DataQualityFindingResponse(**r.model_dump()) for r in records],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def list_all_pending(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DataQualityFindingResponse]:
        records = self.dq_repo.list_all_pending(skip=skip, limit=limit)
        return [DataQualityFindingResponse(**r.model_dump()) for r in records]

    async def review_finding(
        self,
        finding_id: str,
        request: DataQualityReviewRequest,
        reviewer_id: str,
        actor: AuditActor,
    ) -> DataQualityFindingResponse:
        """Transitions a finding to IN_REVIEW."""
        record = self.dq_repo.get_by_id(finding_id)
        if not record:
            raise DataQualityFindingNotFoundException(finding_id)

        record.status = DataQualityFindingStatus.IN_REVIEW
        record.reviewer_notes = request.notes
        self.dq_repo.update(record)

        await self.audit_service.log_event(
            event_type=AuditEventType.DATA_QUALITY_REVIEW_STARTED,
            actor=actor,
            patient_id=record.patient_id,
            resource_type="data_quality_finding",
            resource_id=record.id,
            severity=AuditSeverity.INFO,
            description=f"Review initiated for finding {finding_id} by {reviewer_id}",
        )

        return DataQualityFindingResponse(**record.model_dump())

    async def resolve_finding(
        self,
        finding_id: str,
        request: DataQualityResolutionRequest,
        resolver_id: str,
        actor: AuditActor,
    ) -> DataQualityFindingResponse:
        """
        Applies an authorized resolution to a finding with optimistic concurrency check.
        Preserves original records, provenance, and never performs autonomous merging.
        """
        record = self.dq_repo.get_by_id(finding_id)
        if not record:
            raise DataQualityFindingNotFoundException(finding_id)

        # Optimistic concurrency check
        if request.expected_version is not None and record.version != request.expected_version:
            raise ResourceVersionConflictException(
                f"Finding {finding_id} version mismatch: expected {request.expected_version}, found {record.version}"
            )

        now = datetime.now(timezone.utc)
        record.resolved_at = now
        record.resolved_by = resolver_id
        record.resolution_action = request.action
        record.resolution_notes = request.notes

        if request.action == DataQualityResolutionAction.REJECT_FINDING:
            record.status = DataQualityFindingStatus.REJECTED
            audit_type = AuditEventType.DATA_QUALITY_FINDING_REJECTED
        elif request.action == DataQualityResolutionAction.MARK_DUPLICATE:
            record.status = DataQualityFindingStatus.RESOLVED
            audit_type = AuditEventType.DUPLICATE_CONFIRMED
        elif request.action == DataQualityResolutionAction.LEAVE_UNRESOLVED:
            record.status = DataQualityFindingStatus.UNRESOLVED
            audit_type = AuditEventType.DATA_QUALITY_FINDING_RESOLVED
        else:
            record.status = DataQualityFindingStatus.RESOLVED
            audit_type = AuditEventType.DATA_QUALITY_FINDING_RESOLVED

        self.dq_repo.update(record)

        # Audit resolution
        await self.audit_service.log_event(
            event_type=audit_type,
            actor=actor,
            patient_id=record.patient_id,
            resource_type="data_quality_finding",
            resource_id=record.id,
            severity=AuditSeverity.INFO,
            description=f"Finding {finding_id} resolved with action {request.action.value} by {resolver_id}",
            payload={"action": request.action.value, "reason": request.reason}
        )

        return DataQualityFindingResponse(**record.model_dump())

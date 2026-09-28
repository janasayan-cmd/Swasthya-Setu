from typing import Any, Dict, List, Optional
from datetime import datetime
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.schemas.data_quality import (
    DataQualityFindingCreate,
    DataQualityFindingType,
    DataQualitySeverity,
    DataQualityFindingStatus,
)
from app.schemas.provenance import ProvenanceCategory, ProvenanceVerificationState

def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

class MissingProvenanceRule(DataQualityRule):
    """
    Validates that clinical resources have identifiable source information,
    timestamps, and verification state.
    """
    @property
    def rule_id(self) -> str:
        return "R-PROV-001"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def name(self) -> str:
        return "Missing Provenance Information"

    @property
    def description(self) -> str:
        return "Detects clinical resources with missing source category, origin system, or timestamps."

    def evaluate(self, context: RuleContext) -> List[DataQualityFindingCreate]:
        findings: List[DataQualityFindingCreate] = []

        # Check medications provenance
        for med in context.medications:
            med_id = _get_val(med, "id", "unknown")
            prov = _get_val(med, "provenance")
            source = _get_val(med, "source")
            created_at = _get_val(med, "created_at")

            if not prov and not source:
                findings.append(DataQualityFindingCreate(
                    patient_id=context.patient_id,
                    resource_type="medication",
                    resource_id=str(med_id),
                    finding_type=DataQualityFindingType.PROVENANCE_MISSING,
                    severity=DataQualitySeverity.MEDIUM,
                    status=DataQualityFindingStatus.PENDING,
                    description=f"Medication {med_id} has no source or provenance metadata.",
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    source_references=[f"medication:{med_id}"],
                    context_data={"medication_id": str(med_id)}
                ))
            elif not created_at and not (prov and getattr(prov, "recorded_at", None)):
                findings.append(DataQualityFindingCreate(
                    patient_id=context.patient_id,
                    resource_type="medication",
                    resource_id=str(med_id),
                    finding_type=DataQualityFindingType.PROVENANCE_MISSING,
                    severity=DataQualitySeverity.LOW,
                    status=DataQualityFindingStatus.PENDING,
                    description=f"Medication {med_id} is missing creation / recording timestamp.",
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    source_references=[f"medication:{med_id}"],
                    context_data={"medication_id": str(med_id)}
                ))

        # Check allergies provenance
        for alg in context.allergies:
            alg_id = _get_val(alg, "id", "unknown")
            prov = _get_val(alg, "provenance")
            source = _get_val(alg, "source")

            if not prov and not source:
                findings.append(DataQualityFindingCreate(
                    patient_id=context.patient_id,
                    resource_type="allergy",
                    resource_id=str(alg_id),
                    finding_type=DataQualityFindingType.PROVENANCE_MISSING,
                    severity=DataQualitySeverity.MEDIUM,
                    status=DataQualityFindingStatus.PENDING,
                    description=f"Allergy {alg_id} has no source or provenance metadata.",
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    source_references=[f"allergy:{alg_id}"],
                    context_data={"allergy_id": str(alg_id)}
                ))

        # Check documents provenance
        for doc in context.documents:
            doc_id = _get_val(doc, "id", "unknown")
            uploaded_by = _get_val(doc, "uploaded_by_user_id") or _get_val(doc, "uploader_id")
            created_at = _get_val(doc, "created_at")

            if not uploaded_by and not created_at:
                findings.append(DataQualityFindingCreate(
                    patient_id=context.patient_id,
                    resource_type="document",
                    resource_id=str(doc_id),
                    finding_type=DataQualityFindingType.PROVENANCE_MISSING,
                    severity=DataQualitySeverity.LOW,
                    status=DataQualityFindingStatus.PENDING,
                    description=f"Document {doc_id} is missing origin user and timestamp.",
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    source_references=[f"document:{doc_id}"],
                    context_data={"document_id": str(doc_id)}
                ))

        return findings

class UnverifiedExternalDataRule(DataQualityRule):
    """
    Validates that data imported from external sources or extracted by AI/OCR
    is clearly marked and routed for verification rather than silently accepted.
    """
    @property
    def rule_id(self) -> str:
        return "R-PROV-002"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def name(self) -> str:
        return "Unverified External or Extracted Data"

    @property
    def description(self) -> str:
        return "Identifies external imported data or AI/OCR extracted records that require clinical verification."

    def evaluate(self, context: RuleContext) -> List[DataQualityFindingCreate]:
        findings: List[DataQualityFindingCreate] = []

        for item in context.external_imports:
            item_id = _get_val(item, "id", "unknown")
            res_type = _get_val(item, "resource_type", "external_resource")
            source_system = _get_val(item, "source_system", "external")
            is_verified = _get_val(item, "is_verified", False)

            if not is_verified:
                findings.append(DataQualityFindingCreate(
                    patient_id=context.patient_id,
                    resource_type=str(res_type),
                    resource_id=str(item_id),
                    finding_type=DataQualityFindingType.VERIFICATION_REQUIRED,
                    severity=DataQualitySeverity.MEDIUM,
                    status=DataQualityFindingStatus.PENDING,
                    description=f"Imported {res_type} from '{source_system}' is unverified and requires clinician review.",
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    source_references=[f"external:{source_system}:{item_id}"],
                    context_data={"source_system": source_system, "is_verified": False}
                ))

        return findings


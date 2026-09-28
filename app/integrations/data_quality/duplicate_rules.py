"""Duplicate detection rules for HealthSetu (Phase 26).

SAFETY INVARIANT:
Possible duplicate != confirmed duplicate.
Duplicate detection must NEVER automatically merge or delete records.
"""

from __future__ import annotations

from typing import Dict, List
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingType,
    FindingSeverity,
)


class DocumentDuplicateRule(DataQualityRule):
    """Detect documents with matching SHA-256 checksums or exact filenames."""

    rule_name = "DocumentDuplicateRule"
    rule_version = "1.0.0"
    category = "DUPLICATE"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        seen_checksums: Dict[str, str] = {}  # checksum -> doc_id

        for doc in context.documents:
            doc_id = getattr(doc, "id", "unknown")
            checksum = getattr(doc, "checksum_sha256", None)

            if checksum:
                if checksum in seen_checksums:
                    prior_id = seen_checksums[checksum]
                    findings.append(
                        DataQualityFindingRecord(
                            patient_id=context.patient_id,
                            resource_type="document",
                            resource_id=doc_id,
                            finding_type=DataQualityFindingType.POSSIBLE_DUPLICATE,
                            severity=FindingSeverity.MEDIUM,
                            description=(
                                f"Document '{doc_id}' shares an identical cryptographic checksum with "
                                f"document '{prior_id}'. Possible duplicate upload."
                            ),
                            rule_name=self.rule_name,
                            rule_version=self.rule_version,
                            conflicting_references=[f"document:{prior_id}"],
                            conflicting_resource_references=[
                                {"resource_type": "document", "resource_id": prior_id, "checksum": checksum}
                            ],
                        )
                    )
                else:
                    seen_checksums[checksum] = doc_id

        return findings


class MedicationDuplicateRule(DataQualityRule):
    """Detect potential therapeutic or identical duplicate active medications."""

    rule_name = "MedicationDuplicateRule"
    rule_version = "1.0.0"
    category = "DUPLICATE"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        active_meds: Dict[str, str] = {}  # normalized_name/code -> med_id

        for med in context.medications:
            status = str(getattr(med, "status", "")).upper()
            if "ACTIVE" not in status:
                continue

            med_id = getattr(med, "id", "unknown")
            drug_name = str(getattr(med, "name", getattr(med, "medication_name", ""))).lower().strip()
            code = getattr(med, "rxnorm_code", None) or drug_name

            if not code:
                continue

            if code in active_meds:
                prior_id = active_meds[code]
                findings.append(
                    DataQualityFindingRecord(
                        patient_id=context.patient_id,
                        resource_type="medication",
                        resource_id=med_id,
                        finding_type=DataQualityFindingType.POSSIBLE_DUPLICATE,
                        severity=FindingSeverity.HIGH,
                        description=(
                            f"Multiple active medication records exist for '{drug_name}' "
                            f"(Record {med_id} and {prior_id}). Requires clinician duplicate review."
                        ),
                        rule_name=self.rule_name,
                        rule_version=self.rule_version,
                        conflicting_resource_references=[
                            {"resource_type": "medication", "resource_id": prior_id, "code": code}
                        ],
                    )
                )
            else:
                active_meds[code] = med_id

        return findings


class AllergyDuplicateRule(DataQualityRule):
    """Detect identical substance allergies logged under multiple records."""

    rule_name = "AllergyDuplicateRule"
    rule_version = "1.0.0"
    category = "DUPLICATE"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        active_allergies: Dict[str, str] = {}

        for allergy in context.allergies:
            is_archived = getattr(allergy, "is_archived", False)
            if is_archived:
                continue

            allergy_id = getattr(allergy, "id", "unknown")
            substance = str(getattr(allergy, "allergen", getattr(allergy, "substance", ""))).lower().strip()
            if not substance:
                continue

            if substance in active_allergies:
                prior_id = active_allergies[substance]
                findings.append(
                    DataQualityFindingRecord(
                        patient_id=context.patient_id,
                        resource_type="allergy",
                        resource_id=allergy_id,
                        finding_type=DataQualityFindingType.DUPLICATE_RECORD,
                        severity=FindingSeverity.LOW,
                        description=f"Duplicate active allergy entries for substance '{substance}' ({allergy_id}, {prior_id}).",
                        rule_name=self.rule_name,
                        rule_version=self.rule_version,
                        conflicting_resource_references=[
                            {"resource_type": "allergy", "resource_id": prior_id, "substance": substance}
                        ],
                    )
                )
            else:
                active_allergies[substance] = allergy_id

        return findings

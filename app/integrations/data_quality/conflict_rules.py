"""Conflict detection rules for HealthSetu (Phase 26).

SAFETY INVARIANT:
The system must identify and report conflicting values across sources,
preserving both records and routing for human clinician review.
Never silently select one value as medically correct.
"""

from __future__ import annotations

from typing import Dict, List
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingType,
    FindingSeverity,
)


class AllergyStatusConflictRule(DataQualityRule):
    """Detect conflicting allergy statuses (e.g. marked ACTIVE by one source, INACTIVE/RESOLVED by another)."""

    rule_name = "AllergyStatusConflictRule"
    rule_version = "1.0.0"
    category = "CONFLICT"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        allergy_states: Dict[str, tuple[str, str]] = {}  # substance -> (status, allergy_id)

        for allergy in context.allergies:
            allergy_id = getattr(allergy, "id", "unknown")
            substance = str(getattr(allergy, "allergen", getattr(allergy, "substance", ""))).lower().strip()
            status = str(getattr(allergy, "status", getattr(allergy, "verification_status", "ACTIVE"))).upper()

            if not substance:
                continue

            if substance in allergy_states:
                prev_status, prev_id = allergy_states[substance]
                if prev_status != status:
                    findings.append(
                        DataQualityFindingRecord(
                            patient_id=context.patient_id,
                            resource_type="allergy",
                            resource_id=allergy_id,
                            finding_type=DataQualityFindingType.CONFLICTING_INFORMATION,
                            severity=FindingSeverity.CRITICAL,
                            description=(
                                f"Allergy '{substance}' has conflicting clinical statuses: "
                                f"'{status}' (record {allergy_id}) vs '{prev_status}' (record {prev_id}). "
                                "Requires urgent clinician reconciliation."
                            ),
                            rule_name=self.rule_name,
                            rule_version=self.rule_version,
                            conflicting_resource_references=[
                                {"resource_type": "allergy", "resource_id": prev_id, "status": prev_status}
                            ],
                        )
                    )
            else:
                allergy_states[substance] = (status, allergy_id)

        return findings


class MedicationDosageConflictRule(DataQualityRule):
    """Detect conflicting active dosages or frequencies for the same medication across encounters."""

    rule_name = "MedicationDosageConflictRule"
    rule_version = "1.0.0"
    category = "CONFLICT"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        med_dosages: Dict[str, tuple[str, str]] = {}  # drug_name -> (dosage, med_id)

        for med in context.medications:
            status = str(getattr(med, "status", "")).upper()
            if "ACTIVE" not in status:
                continue

            med_id = getattr(med, "id", "unknown")
            drug_name = str(getattr(med, "drug_name_raw", getattr(med, "name", getattr(med, "medication_name", "")))).lower().strip()
            dosage = str(getattr(med, "strength_raw", getattr(med, "dosage", getattr(med, "dose", "")))).lower().strip()

            if not drug_name or not dosage:
                continue


            if drug_name in med_dosages:
                prev_dosage, prev_id = med_dosages[drug_name]
                if prev_dosage != dosage:
                    findings.append(
                        DataQualityFindingRecord(
                            patient_id=context.patient_id,
                            resource_type="medication",
                            resource_id=med_id,
                            finding_type=DataQualityFindingType.CONFLICTING_INFORMATION,
                            severity=FindingSeverity.HIGH,
                            description=(
                                f"Active medication '{drug_name}' has diverging dosages recorded across sources: "
                                f"'{dosage}' (record {med_id}) vs '{prev_dosage}' (record {prev_id})."
                            ),
                            rule_name=self.rule_name,
                            rule_version=self.rule_version,
                            conflicting_resource_references=[
                                {"resource_type": "medication", "resource_id": prev_id, "dosage": prev_dosage}
                            ],
                        )
                    )
            else:
                med_dosages[drug_name] = (dosage, med_id)

        return findings

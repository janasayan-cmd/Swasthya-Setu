"""Completeness checking rules for HealthSetu (Phase 26)."""

from __future__ import annotations

from typing import List
from app.integrations.data_quality.base import DataQualityRule, RuleContext
from app.schemas.data_quality import (
    DataQualityFindingRecord,
    DataQualityFindingType,
    FindingSeverity,
    ProvenanceReference,
)


class PatientDemographicsCompletenessRule(DataQualityRule):
    """Detect missing critical patient demographic attributes."""

    rule_name = "PatientDemographicsCompletenessRule"
    rule_version = "1.0.0"
    category = "COMPLETENESS"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        patient = context.patient
        if not patient:
            findings.append(
                DataQualityFindingRecord(
                    patient_id=context.patient_id,
                    resource_type="patient",
                    resource_id=context.patient_id,
                    finding_type=DataQualityFindingType.MISSING_INFORMATION,
                    severity=FindingSeverity.HIGH,
                    description=f"Patient record '{context.patient_id}' not found or demographics are completely missing.",
                    rule_name=self.rule_name,
                    rule_version=self.rule_version,
                )
            )
            return findings


        # Check essential fields: DOB, sex
        missing_fields = []
        if not getattr(patient, "date_of_birth", None):
            missing_fields.append("date_of_birth")
        if not getattr(patient, "sex", None):
            missing_fields.append("sex")

        if missing_fields:
            findings.append(
                DataQualityFindingRecord(
                    patient_id=context.patient_id,
                    resource_type="patient",
                    resource_id=getattr(patient, "id", context.patient_id),
                    finding_type=DataQualityFindingType.INCOMPLETE_RECORD,
                    severity=FindingSeverity.HIGH,
                    description=f"Patient demographic record is missing required fields: {', '.join(missing_fields)}.",
                    rule_name=self.rule_name,
                    rule_version=self.rule_version,
                    source_reference=ProvenanceReference(
                        source="internal_database",
                        source_type="PATIENT_REPORTED",
                        system_id="healthsetu-core",
                    ),
                )
            )
        return findings


class AllergyCompletenessRule(DataQualityRule):
    """Detect allergy records missing critical allergen substance or severity."""

    rule_name = "AllergyCompletenessRule"
    rule_version = "1.0.0"
    category = "COMPLETENESS"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        for allergy in context.allergies:
            allergy_id = getattr(allergy, "id", "unknown")
            substance = getattr(allergy, "allergen", getattr(allergy, "substance", None))
            severity = getattr(allergy, "severity", None)

            missing = []
            if not substance:
                missing.append("substance/allergen")
            if not severity:
                missing.append("severity")

            if missing:
                findings.append(
                    DataQualityFindingRecord(
                        patient_id=context.patient_id,
                        resource_type="allergy",
                        resource_id=allergy_id,
                        finding_type=DataQualityFindingType.MISSING_INFORMATION,
                        severity=FindingSeverity.MEDIUM,
                        description=f"Allergy entry '{allergy_id}' lacks critical fields: {', '.join(missing)}.",
                        rule_name=self.rule_name,
                        rule_version=self.rule_version,
                    )
                )
        return findings


class MedicationCompletenessRule(DataQualityRule):
    """Detect medication entries missing dosage, frequency, or status."""

    rule_name = "MedicationCompletenessRule"
    rule_version = "1.0.0"
    category = "COMPLETENESS"

    async def evaluate(self, context: RuleContext) -> List[DataQualityFindingRecord]:
        findings: List[DataQualityFindingRecord] = []
        for med in context.medications:
            med_id = getattr(med, "id", "unknown")
            name = getattr(med, "name", getattr(med, "medication_name", None))
            dosage = getattr(med, "dosage", getattr(med, "dose", None))
            status = getattr(med, "status", None)

            missing = []
            if not name:
                missing.append("medication_name")
            if not dosage:
                missing.append("dosage")
            if not status:
                missing.append("status")

            if missing:
                findings.append(
                    DataQualityFindingRecord(
                        patient_id=context.patient_id,
                        resource_type="medication",
                        resource_id=med_id,
                        finding_type=DataQualityFindingType.INCOMPLETE_RECORD,
                        severity=FindingSeverity.MEDIUM,
                        description=f"Medication entry '{med_id}' lacks essential fields: {', '.join(missing)}.",
                        rule_name=self.rule_name,
                        rule_version=self.rule_version,
                    )
                )
        return findings

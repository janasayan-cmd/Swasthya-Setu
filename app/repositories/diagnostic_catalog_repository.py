"""Diagnostic Catalog Repository (Phase 34).

Thread-safe catalog repository seeded with standard clinical laboratory and diagnostic
services aligned with LOINC terminology codes.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.schemas.diagnostic_test import (
    DiagnosticTest,
    DiagnosticTestCategory,
    DiagnosticTestSearchFilter,
    DiagnosticTestSearchResult,
    TerminologySystem,
)


class DiagnosticCatalogRepository:
    """Thread-safe catalog repository with standard seed tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tests: Dict[str, DiagnosticTest] = {}
        self._seed_default_catalog()

    def _seed_default_catalog(self) -> None:
        """Seed representative clinical tests."""
        seed_data = [
            DiagnosticTest(
                test_id="TEST-CBC-001",
                code="58410-2",
                system=TerminologySystem.LOINC,
                name="Complete Blood Count with Differential Panel",
                raw_name="Complete Blood Count (CBC)",
                category=DiagnosticTestCategory.HEMATOLOGY,
                specimen_type="BLOOD",
                default_unit="k/uL",
                description="Routine evaluation of red blood cells, white blood cells, and platelets",
                turn_around_hours=12,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-HB-002",
                code="718-7",
                system=TerminologySystem.LOINC,
                name="Hemoglobin [Mass/volume] in Blood",
                raw_name="Hemoglobin (Hb)",
                category=DiagnosticTestCategory.HEMATOLOGY,
                specimen_type="BLOOD",
                default_unit="g/dL",
                description="Measurement of total hemoglobin concentration in blood",
                turn_around_hours=6,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-LIPID-003",
                code="24331-1",
                system=TerminologySystem.LOINC,
                name="Lipid 1996 Panel - Serum or Plasma",
                raw_name="Lipid Profile",
                category=DiagnosticTestCategory.BIOCHEMISTRY,
                specimen_type="SERUM",
                default_unit="mg/dL",
                description="Evaluation of total cholesterol, triglycerides, HDL, and LDL",
                turn_around_hours=24,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-CREAT-004",
                code="2160-0",
                system=TerminologySystem.LOINC,
                name="Creatinine [Mass/volume] in Serum or Plasma",
                raw_name="Serum Creatinine",
                category=DiagnosticTestCategory.BIOCHEMISTRY,
                specimen_type="SERUM",
                default_unit="mg/dL",
                description="Assessment of kidney excretory filtration function",
                turn_around_hours=12,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-HBA1C-005",
                code="4548-4",
                system=TerminologySystem.LOINC,
                name="Hemoglobin A1c/Hemoglobin.total in Blood",
                raw_name="HbA1c (Glycated Hemoglobin)",
                category=DiagnosticTestCategory.BIOCHEMISTRY,
                specimen_type="BLOOD",
                default_unit="%",
                description="Index of average blood glucose levels over the preceding 2 to 3 months",
                turn_around_hours=24,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-GLU-006",
                code="2345-7",
                system=TerminologySystem.LOINC,
                name="Glucose [Mass/volume] in Serum or Plasma",
                raw_name="Blood Glucose (Fasting)",
                category=DiagnosticTestCategory.BIOCHEMISTRY,
                specimen_type="SERUM",
                default_unit="mg/dL",
                description="Assessment of carbohydrate metabolism",
                turn_around_hours=6,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-LFT-007",
                code="24325-3",
                system=TerminologySystem.LOINC,
                name="Hepatic Function 2000 Panel - Serum or Plasma",
                raw_name="Liver Function Test (LFT)",
                category=DiagnosticTestCategory.BIOCHEMISTRY,
                specimen_type="SERUM",
                default_unit="U/L",
                description="Enzymes and proteins assessing hepatobiliary health",
                turn_around_hours=24,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-COVID-008",
                code="94500-6",
                system=TerminologySystem.LOINC,
                name="SARS-CoV-2 (COVID-19) RNA [Presence] in Respiratory Specimen by NAA with Probe",
                raw_name="COVID-19 RT-PCR",
                category=DiagnosticTestCategory.MOLECULAR,
                specimen_type="SWAB",
                default_unit=None,
                description="Qualitative nucleic acid amplification test for SARS-CoV-2",
                turn_around_hours=24,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-CXR-009",
                code="36554-4",
                system=TerminologySystem.LOINC,
                name="XR Chest PA view",
                raw_name="Chest X-Ray PA View",
                category=DiagnosticTestCategory.RADIOLOGY,
                specimen_type=None,
                default_unit=None,
                description="Plain film posteroanterior radiographic examination of chest",
                turn_around_hours=12,
                is_active=True,
            ),
            DiagnosticTest(
                test_id="TEST-URINE-010",
                code="24356-8",
                system=TerminologySystem.LOINC,
                name="Urinalysis Complete Panel",
                raw_name="Urinalysis Routine",
                category=DiagnosticTestCategory.URINALYSIS,
                specimen_type="URINE",
                default_unit=None,
                description="Macroscopic and chemical evaluation of urine",
                turn_around_hours=6,
                is_active=True,
            ),
        ]
        for t in seed_data:
            self._tests[t.test_id] = t

    def get_by_id(self, test_id: str) -> Optional[DiagnosticTest]:
        with self._lock:
            return self._tests.get(test_id)

    def get_by_code(self, code: str, system: TerminologySystem = TerminologySystem.LOINC) -> Optional[DiagnosticTest]:
        with self._lock:
            for t in self._tests.values():
                if t.code == code and t.system == system:
                    return t
            return None

    def search(self, filter_params: DiagnosticTestSearchFilter) -> DiagnosticTestSearchResult:
        with self._lock:
            results = list(self._tests.values())

            if filter_params.is_active is not None:
                results = [t for t in results if t.is_active == filter_params.is_active]

            if filter_params.category:
                results = [t for t in results if t.category == filter_params.category]

            if filter_params.system:
                results = [t for t in results if t.system == filter_params.system]

            if filter_params.specimen_type:
                st = filter_params.specimen_type.upper()
                results = [t for t in results if t.specimen_type and t.specimen_type.upper() == st]

            if filter_params.query:
                q = filter_params.query.lower().strip()
                results = [
                    t for t in results
                    if q in t.name.lower() or q in t.raw_name.lower() or q in t.code.lower()
                ]

            total = len(results)
            start = (filter_params.page - 1) * filter_params.limit
            end = start + filter_params.limit
            paginated = results[start:end]

            return DiagnosticTestSearchResult(
                items=paginated,
                total=total,
                page=filter_params.page,
                limit=filter_params.limit,
            )

    def list_all(self) -> List[DiagnosticTest]:
        with self._lock:
            return list(self._tests.values())

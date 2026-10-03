"""Diagnostic Catalog & Test Normalization Service (Phase 34).

Responsibilities:
- Retrieve supported diagnostic tests and panels.
- Search catalog references by code, discipline, and terminology.
- Normalize raw clinical test strings to standardized concepts.
- Detect ambiguous matches without guessing.

CRITICAL INVARIANTS:
- DIAGNOSTIC CATALOG IS A TERMINOLOGY/SERVICE REFERENCE ONLY
- IT MUST NEVER BECOME A CLINICAL RECOMMENDATION ENGINE
- TEST NORMALIZATION != CLINICAL INTERPRETATION
- AMBIGUOUS MATCHES MUST REMAIN AMBIGUOUS
"""

from __future__ import annotations

import difflib
from typing import List, Optional

from app.core.exceptions import (
    DiagnosticCatalogDisabledException,
    DiagnosticTestNotFoundException,
)
from app.repositories.diagnostic_catalog_repository import DiagnosticCatalogRepository
from app.schemas.diagnostic_test import (
    CandidateMatch,
    DiagnosticTest,
    DiagnosticTestSearchFilter,
    DiagnosticTestSearchResult,
    TerminologySystem,
    TestNormalizationRequest,
    TestNormalizationResponse,
)


class DiagnosticCatalogService:
    """Service managing diagnostic catalog and test concept normalization."""

    def __init__(
        self,
        catalog_repository: Optional[DiagnosticCatalogRepository] = None,
        enabled: bool = True,
    ) -> None:
        self.catalog_repository = catalog_repository or DiagnosticCatalogRepository()
        self.enabled = enabled

    def _check_enabled(self) -> None:
        if not self.enabled:
            raise DiagnosticCatalogDisabledException("Diagnostic catalog capability is disabled")

    def get_test_by_id(self, test_id: str) -> DiagnosticTest:
        self._check_enabled()
        test = self.catalog_repository.get_by_id(test_id)
        if not test:
            raise DiagnosticTestNotFoundException(f"Diagnostic test '{test_id}' not found in catalog")
        return test

    def get_test_by_code(self, code: str, system: TerminologySystem = TerminologySystem.LOINC) -> DiagnosticTest:
        self._check_enabled()
        test = self.catalog_repository.get_by_code(code, system)
        if not test:
            raise DiagnosticTestNotFoundException(f"Diagnostic test code '{code}' in system '{system.value}' not found")
        return test

    def search_tests(self, filter_params: DiagnosticTestSearchFilter) -> DiagnosticTestSearchResult:
        self._check_enabled()
        return self.catalog_repository.search(filter_params)

    def normalize_test(self, request: TestNormalizationRequest) -> TestNormalizationResponse:
        """Map raw test string to catalog concept using fuzzy string matching."""
        self._check_enabled()
        raw_name = request.raw_test_name.strip()
        all_tests = self.catalog_repository.list_all()

        candidates: List[CandidateMatch] = []
        raw_lower = raw_name.lower()

        for t in all_tests:
            # Score against normalized name and raw name
            score_name = difflib.SequenceMatcher(None, raw_lower, t.name.lower()).ratio()
            score_raw = difflib.SequenceMatcher(None, raw_lower, t.raw_name.lower()).ratio()
            score = max(score_name, score_raw)

            # Bonus for specimen match
            if request.specimen_type and t.specimen_type:
                if request.specimen_type.upper() == t.specimen_type.upper():
                    score = min(1.0, score + 0.1)

            # Exact acronym or substring containment boost
            if raw_lower in t.raw_name.lower() or raw_lower in t.name.lower():
                score = max(score, 0.75)

            if score >= 0.5:
                candidates.append(
                    CandidateMatch(
                        test_id=t.test_id,
                        code=t.code,
                        system=t.system,
                        name=t.name,
                        score=round(score, 3),
                    )
                )

        candidates.sort(key=lambda c: c.score, reverse=True)

        if not candidates:
            return TestNormalizationResponse(
                raw_test_name=raw_name,
                confidence=0.0,
                is_ambiguous=False,
                candidate_matches=[],
            )

        top = candidates[0]

        # Check for ambiguity: multiple top candidates within 0.08 score difference
        if len(candidates) > 1 and (top.score - candidates[1].score) < 0.08 and top.score < 0.95:
            return TestNormalizationResponse(
                raw_test_name=raw_name,
                confidence=top.score,
                is_ambiguous=True,
                candidate_matches=candidates[:5],
            )

        # Clear match
        return TestNormalizationResponse(
            raw_test_name=raw_name,
            matched_test_id=top.test_id,
            normalized_name=top.name,
            code=top.code,
            system=top.system,
            confidence=top.score,
            is_ambiguous=False,
            candidate_matches=candidates[:5],
        )

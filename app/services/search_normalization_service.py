"""Search Normalization Service for Phase 30.

CRITICAL PRINCIPLES:
- Whitespace trimming and multi-space collapsing
- Case normalization (lowercase matching canonicalization)
- Safe punctuation normalization
- Unicode normalization (NFKC)
- Identifier preservation and prefix normalization
- NO clinical interpretation:
  - "Paracetamol 500 mg" is normalized purely as text.
  - Does NOT infer diagnoses, symptoms, triage level, or treatment indication.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Tuple
from app.core.exceptions import SearchQueryTooLongError, SearchQueryTooShortError


class SearchNormalizationService:
    """Provides pure syntactic query sanitization and normalization."""

    def __init__(self, min_length: int = 2, max_length: int = 200) -> None:
        self.min_length = min_length
        self.max_length = max_length
        # Harmless punctuation allowed in healthcare queries (hyphens, slashes, periods in dosages)
        self._punctuation_cleanup = re.compile(r"['\"`\x00-\x1f\x7f]")
        self._multi_whitespace = re.compile(r"\s+")

    def normalize_query(self, raw_query: str) -> str:
        """Sanitize and normalize query string.

        Raises SearchQueryTooShortError or SearchQueryTooLongError if bounded constraints are violated.
        """
        if not raw_query:
            raise SearchQueryTooShortError(f"Query must be at least {self.min_length} characters")

        # 1. Unicode normalization (NFKC decomposes compatibility chars and canonicalizes)
        text = unicodedata.normalize("NFKC", raw_query)

        # 2. Strip dangerous control characters and quotes
        text = self._punctuation_cleanup.sub(" ", text)

        # 3. Collapse multiple whitespaces and strip
        text = self._multi_whitespace.sub(" ", text).strip()

        # 4. Length checks on trimmed query
        if len(text) < self.min_length:
            raise SearchQueryTooShortError(f"Query must be at least {self.min_length} characters")

        if len(text) > self.max_length:
            raise SearchQueryTooLongError(f"Query must not exceed {self.max_length} characters")

        return text

    def normalize_for_matching(self, text: str) -> str:
        """Return lowercased canonical token string for search comparison."""
        return text.strip().lower()

    def is_identifier_query(self, query: str) -> bool:
        """Heuristic to detect if query looks like a specific UUID or formatted code."""
        q = query.strip()
        # UUID check or structured code (e.g., MED-123, DOC-456, PAT-789)
        uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        code_pattern = r"^[A-Za-z0-9_-]{3,36}$"
        return bool(re.match(uuid_pattern, q) or (re.match(code_pattern, q) and any(c.isdigit() for c in q)))

"""Synthetic test data loader helper for Phase 24.

Ensures zero production PHI is used in automated test suites (TRD Sec 25).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_SYNTHETIC_DIR = Path(__file__).parent


def load_synthetic_patients() -> List[Dict[str, Any]]:
    """Load synthetic patient records."""
    file_path = _SYNTHETIC_DIR / "patients.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return data.get("patients", [])


def load_synthetic_clinical_data() -> Dict[str, Any]:
    """Load comprehensive synthetic clinical datasets."""
    file_path = _SYNTHETIC_DIR / "clinical_data.json"
    return json.loads(file_path.read_text(encoding="utf-8"))

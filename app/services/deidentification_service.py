"""De-identification Transformation Service for Non-Production Workflows (Phase 24).

ARCHITECTURAL PRINCIPLES:
=========================
- Provides sanitization transformations for analytics, development, testing, and model evaluation.
- IMPORTANT DISCLAIMER: This service does NOT claim legal compliance or certification by itself.
- Applies direct identifier removal, date shifting, location generalization, and free-text redaction.
- Emits structured audit events for every de-identification operation.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.integrations.privacy.base import DeidentificationEngine
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventType, AuditRecord

logger = get_logger("app.deidentification_service")


class DeidentificationService(DeidentificationEngine):
    """Domain service executing redaction, date shifting, and demographic generalization."""

    def __init__(self, audit_repository: AuditRepository) -> None:
        self.audit_repo = audit_repository
        self._phone_regex = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
        self._email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
        self._ssn_regex = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        self._date_regex = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b")

    def deidentify_record(
        self,
        data: Dict[str, Any],
        date_shift_days: int = -7,
        generalize_zip: bool = True,
    ) -> Dict[str, Any]:
        """Strip direct identifiers, redact free-text PHI, shift dates, and add non-legal disclaimer."""
        transformed: Dict[str, Any] = {}

        # Direct identifier removal & replacement
        for k, v in data.items():
            k_lower = k.lower().strip()

            if k_lower in ("first_name", "last_name", "full_name", "patient_name", "name"):
                transformed[k] = "[REDACTED_NAME]"
            elif k_lower in ("email", "user_email"):
                transformed[k] = "[REDACTED_EMAIL]"
            elif k_lower in ("phone", "phone_number", "mobile"):
                transformed[k] = "[REDACTED_PHONE]"
            elif k_lower in ("ssn", "national_id", "passport_number"):
                transformed[k] = "[REDACTED_NATIONAL_ID]"
            elif k_lower in ("address", "street_address"):
                transformed[k] = "[REDACTED_ADDRESS]"
            elif k_lower in ("zip_code", "postal_code") and generalize_zip:
                # Truncate zip to 3 digits (e.g. 90210 -> 902**)
                str_zip = str(v)
                transformed[k] = str_zip[:3] + "**" if len(str_zip) >= 3 else "***"
            elif "date" in k_lower or k_lower in ("dob", "birth_date", "date_of_birth"):
                transformed[k] = self._shift_date_value(v, date_shift_days)
            elif isinstance(v, str):
                transformed[k] = self.redact_text(v)
            elif isinstance(v, dict):
                transformed[k] = self.deidentify_record(v, date_shift_days, generalize_zip)
            elif isinstance(v, list):
                transformed[k] = [
                    self.deidentify_record(item, date_shift_days, generalize_zip)
                    if isinstance(item, dict)
                    else (self.redact_text(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                transformed[k] = v

        # Append mandatory governance disclaimer (TRD Sec 23 & 51)
        transformed["_deidentification_metadata"] = {
            "deidentified": True,
            "legal_certification": False,
            "date_shift_applied_days": date_shift_days,
            "disclaimer": "Processed for non-production use; not a guarantee of legal anonymization.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return transformed

    def redact_text(self, text: str) -> str:
        """Redact direct identifiers from narrative clinical text."""
        if not text:
            return text
        sanitized = self._email_regex.sub("[REDACTED_EMAIL]", text)
        sanitized = self._phone_regex.sub("[REDACTED_PHONE]", sanitized)
        sanitized = self._ssn_regex.sub("[REDACTED_ID]", sanitized)
        sanitized = self._date_regex.sub("[REDACTED_DATE]", sanitized)
        return sanitized

    def _shift_date_value(self, val: Any, shift_days: int) -> str:
        """Apply bounded date shift to preserve relative clinical chronology."""
        if not val:
            return ""
        try:
            if isinstance(val, (datetime, date)):
                shifted = val + timedelta(days=shift_days)
                return str(shifted)
            str_val = str(val)[:10]
            dt = datetime.strptime(str_val, "%Y-%m-%d")
            return (dt + timedelta(days=shift_days)).strftime("%Y-%m-%d")
        except Exception:
            return "[DATE_REDACTED]"

    async def deidentify_patient_dataset(
        self,
        records: List[Dict[str, Any]],
        actor_id: str,
        reason: str,
    ) -> List[Dict[str, Any]]:
        """De-identify a collection of clinical records with audit attribution."""
        await self._audit(
            event_type=AuditEventType.DEIDENTIFICATION_STARTED,
            actor_id=actor_id,
            count=len(records),
            reason=reason,
        )

        transformed = [self.deidentify_record(r) for r in records]

        await self._audit(
            event_type=AuditEventType.DEIDENTIFICATION_COMPLETED,
            actor_id=actor_id,
            count=len(records),
            reason=reason,
        )
        return transformed

    async def _audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        count: int,
        reason: str,
    ) -> None:
        """Record audit event for de-identification operations."""
        try:
            await self.audit_repo.create(
                AuditRecord(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    user_id=actor_id,
                    patient_id=None,
                    resource_type="dataset",
                    resource_id="batch",
                    action="DEIDENTIFY",
                    outcome="SUCCESS",
                    timestamp=datetime.now(timezone.utc),
                    metadata={"record_count": count, "reason": reason},
                )
            )
        except Exception as e:
            logger.warning(f"Failed to record de-identification audit: {e}")

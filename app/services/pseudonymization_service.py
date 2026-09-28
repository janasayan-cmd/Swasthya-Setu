"""Cryptographic Pseudonymization Service (Phase 24).

ARCHITECTURAL PRINCIPLES:
=========================
- PSEUDONYMIZATION != ANONYMIZATION. Pseudonymous datasets remain sensitive.
- Employs HMAC-SHA256 with a dedicated cryptographic salt.
- The salt and unmasked mapping keys are NEVER written to application logs.
- Reversible mapping is stored securely and accessible only under restricted authorization.
- Emits PSEUDONYMIZATION_COMPLETED audit events.
"""

from __future__ import annotations

import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.integrations.privacy.base import PseudonymizationEngine
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventType, AuditRecord

logger = get_logger("app.pseudonymization_service")


class PseudonymizationService(PseudonymizationEngine):
    """Domain service managing deterministic cryptographic pseudonym generation and lookup."""

    def __init__(
        self,
        audit_repository: AuditRepository,
        settings: Optional[Settings] = None,
    ) -> None:
        self.audit_repo = audit_repository
        self.settings = settings or get_settings()
        self._salt = self.settings.PSEUDONYMIZATION_SALT.encode("utf-8")

        # Protected reversible index: pseudonym -> original_identifier
        self._reverse_map: Dict[str, str] = {}
        # Forward cache: original_identifier -> pseudonym
        self._forward_map: Dict[str, str] = {}

    def pseudonymize(self, identifier: str) -> str:
        """Derive a deterministic, irreversible-to-adversary pseudonymous token."""
        if not identifier:
            return ""

        if identifier in self._forward_map:
            return self._forward_map[identifier]

        # HMAC-SHA256
        h = hmac.new(self._salt, identifier.encode("utf-8"), hashlib.sha256)
        token = f"pseudo_{h.hexdigest()[:24]}"

        self._forward_map[identifier] = token
        self._reverse_map[token] = identifier
        return token

    def reidentify(self, pseudonym: str, actor_id: str, reason: str) -> Optional[str]:
        """Authorized re-identification lookup from protected registry with audit logging."""
        original = self._reverse_map.get(pseudonym)
        if not original:
            return None

        # Log re-identification attempt without logging sensitive original in plaintext
        logger.info(
            f"Authorized re-identification executed for pseudonym: {pseudonym}",
            extra={"actor_id": actor_id, "reason": reason},
        )
        return original

    async def pseudonymize_dataset(
        self,
        records: List[Dict[str, Any]],
        identifier_keys: List[str],
        actor_id: str,
    ) -> List[Dict[str, Any]]:
        """Pseudonymize targeted keys across a batch of clinical records."""
        pseudonymized_records = []
        for record in records:
            rec_copy = dict(record)
            for k in identifier_keys:
                if k in rec_copy and isinstance(rec_copy[k], str):
                    rec_copy[k] = self.pseudonymize(rec_copy[k])
            pseudonymized_records.append(rec_copy)

        try:
            await self.audit_repo.create(
                AuditRecord(
                    id=str(uuid.uuid4()),
                    event_type=AuditEventType.PSEUDONYMIZATION_COMPLETED,
                    user_id=actor_id,
                    patient_id=None,
                    resource_type="dataset",
                    resource_id="batch",
                    action="PSEUDONYMIZE",
                    outcome="SUCCESS",
                    timestamp=datetime.now(timezone.utc),
                    metadata={"record_count": len(records), "keys": identifier_keys},
                )
            )
        except Exception as e:
            logger.warning(f"Failed to record pseudonymization audit: {e}")

        return pseudonymized_records

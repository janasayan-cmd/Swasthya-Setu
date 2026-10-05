"""Communication Provider Interface and Base Abstraction (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- PROVIDER ACCEPTANCE != DELIVERED TO RECIPIENT
- PROVIDER ACCEPTANCE != READ BY PATIENT
- UNKNOWN STATUS != SUCCESS
- PROVIDER FAILURE != SUCCESS
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.schemas.communication import ProviderSendResult, ProviderState, WebhookPayload


class CommunicationProvider(ABC):
    """Abstract base class for external communication providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the communication provider."""
        ...

    @abstractmethod
    async def send_message(
        self,
        message_id: str,
        recipient_ids: List[str],
        content: str,
        sender_role: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderSendResult:
        """Dispatch a message through provider channel."""
        ...

    @abstractmethod
    async def get_delivery_status(self, provider_message_id: str) -> str:
        """Poll delivery status from provider."""
        ...

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify HMAC signature of inbound provider webhook."""
        ...

    @abstractmethod
    async def parse_webhook(self, payload: Dict[str, Any]) -> WebhookPayload:
        """Normalize provider webhook payload."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderState:
        """Probe provider availability."""
        ...

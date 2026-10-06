"""Abstract Sharing Provider Interface (Phase 44).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- PROVIDER TIMEOUT != SUCCESS
- PROVIDER UNAVAILABLE != SHARED
- UNKNOWN != DELIVERED
- HTTP 200 FROM INTERMEDIATE PROVIDER != CLINICAL ACCEPTANCE
- PROVIDER IMPLEMENTATION MUST NOT CONTAIN BUSINESS AUTHORIZATION LOGIC
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProviderDeliveryState(str, Enum):
    """Normalized provider delivery states."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class ProviderShareResult(BaseModel):
    """Result returned by external sharing provider dispatch."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    state: ProviderDeliveryState
    provider_reference: str
    message: Optional[str] = None
    retryable: bool = False
    raw_response: Optional[Dict[str, Any]] = None


class SharingProvider(ABC):
    """Abstract base class for external clinical data exchange adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the sharing provider adapter."""
        ...

    @abstractmethod
    async def share(
        self,
        payload: Dict[str, Any],
        destination_url: Optional[str] = None,
        recipient_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderShareResult:
        """Dispatch a clinical data sharing payload to the external destination."""
        ...

    @abstractmethod
    async def get_status(self, provider_reference: str) -> ProviderDeliveryState:
        """Poll the current delivery status from the external provider."""
        ...

    @abstractmethod
    async def cancel(self, provider_reference: str) -> bool:
        """Attempt to cancel an in-flight transmission if supported."""
        ...

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """Check provider connectivity and health status."""
        ...

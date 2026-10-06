"""Abstract Ingestion Provider Interface (Phase 45).

SAFETY INVARIANTS:
- PROVIDER TIMEOUT != SUCCESS
- PROVIDER UNAVAILABLE != INGESTED
- UNKNOWN != DELIVERED
- PROVIDER IMPLEMENTATION MUST NOT CONTAIN BUSINESS AUTHORIZATION LOGIC
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class IngestionFetchResult(BaseModel):
    """Result returned by external pull/polling provider dispatch."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    external_resource_id: str
    resource_type: str
    payload: Dict[str, Any]
    provider_reference: str
    error_message: Optional[str] = None
    retryable: bool = False


class IngestionProvider(ABC):
    """Abstract base class for external clinical data ingestion adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the ingestion provider adapter."""
        ...

    @abstractmethod
    async def fetch_resource(
        self,
        resource_type: str,
        external_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> IngestionFetchResult:
        """Pull an external clinical resource by ID."""
        ...

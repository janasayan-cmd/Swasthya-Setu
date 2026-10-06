"""Ingestion Provider Registry (Phase 45)."""

from __future__ import annotations

from typing import Dict, Optional

from app.core.exceptions import IngestionProviderUnavailableException
from app.integrations.ingestion.base import IngestionProvider
from app.integrations.ingestion.providers.mock_provider import MockIngestionProvider


class IngestionProviderRegistry:
    """Registry maintaining available external ingestion provider adapters."""

    def __init__(self) -> None:
        self._providers: Dict[str, IngestionProvider] = {}
        # Register default mock provider
        self.register_provider("mock", MockIngestionProvider("mock"))

    def register_provider(self, name: str, provider: IngestionProvider) -> None:
        """Register an adapter under a specified name."""
        self._providers[name.lower().strip()] = provider

    def get_provider(self, name: Optional[str] = None) -> IngestionProvider:
        """Retrieve a registered provider by name or return default."""
        target_name = (name or "mock").lower().strip()
        provider = self._providers.get(target_name)
        if not provider:
            raise IngestionProviderUnavailableException(
                f"Ingestion provider '{target_name}' is not registered or unavailable."
            )
        return provider


# Global registry singleton
ingestion_provider_registry = IngestionProviderRegistry()

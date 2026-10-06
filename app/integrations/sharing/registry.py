"""Sharing Provider Registry (Phase 44)."""

from __future__ import annotations

from typing import Dict, Optional

from app.core.exceptions import SharingProviderUnavailableException
from app.integrations.sharing.base import SharingProvider
from app.integrations.sharing.providers.mock import MockSharingProvider


class SharingProviderRegistry:
    """Registry maintaining available external sharing provider adapters."""

    def __init__(self) -> None:
        self._providers: Dict[str, SharingProvider] = {}
        # Register default mock provider
        self.register_provider("mock", MockSharingProvider("mock"))

    def register_provider(self, name: str, provider: SharingProvider) -> None:
        """Register an adapter under a specified name."""
        self._providers[name.lower().strip()] = provider

    def get_provider(self, name: Optional[str] = None) -> SharingProvider:
        """Retrieve a registered provider by name or return default."""
        target_name = (name or "mock").lower().strip()
        provider = self._providers.get(target_name)
        if not provider:
            raise SharingProviderUnavailableException(
                f"Sharing provider '{target_name}' is not registered or unavailable."
            )
        return provider


# Global registry singleton
sharing_provider_registry = SharingProviderRegistry()

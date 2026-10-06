"""External Clinical Data Ingestion Integration Module (Phase 45)."""

from app.integrations.ingestion.base import IngestionFetchResult, IngestionProvider
from app.integrations.ingestion.registry import IngestionProviderRegistry, ingestion_provider_registry

__all__ = [
    "IngestionProvider",
    "IngestionFetchResult",
    "IngestionProviderRegistry",
    "ingestion_provider_registry",
]

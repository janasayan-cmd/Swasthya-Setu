"""Search Integrations Package."""

from app.integrations.search.base import SearchProvider
from app.integrations.search.postgres import PostgresSearchProvider

__all__ = ["SearchProvider", "PostgresSearchProvider"]

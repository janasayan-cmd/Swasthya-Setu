"""Search Provider Abstraction Interface.

Defines the contract for search retrieval backends (PostgreSQL native, mock, external adapter).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.search import SearchRequest, SearchResourceType
from app.schemas.search_result import SearchIndexStatus, SearchResultItem


class SearchProvider(ABC):
    """Abstract base class for all search provider adapters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""
        pass

    @abstractmethod
    async def search(
        self,
        request: SearchRequest,
        allowed_resource_types: List[SearchResourceType],
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Tuple[List[SearchResultItem], int]:
        """Execute search within authorization scope.

        Returns (items, total_count).
        """
        pass

    @abstractmethod
    async def search_resource(
        self,
        resource_type: SearchResourceType,
        request: SearchRequest,
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
        actor_facility_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Tuple[List[SearchResultItem], int]:
        """Execute single-resource-type search within authorization scope."""
        pass

    @abstractmethod
    async def get_suggestions(
        self,
        query: str,
        resource_type: Optional[SearchResourceType],
        allowed_resource_types: List[SearchResourceType],
        limit: int = 10,
        actor_patient_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve authorized prefix autocomplete suggestions."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verify provider availability and latency."""
        pass

    @abstractmethod
    async def get_index_status(self) -> SearchIndexStatus:
        """Retrieve operational index metrics and synchronization state."""
        pass

    @abstractmethod
    async def rebuild_index(self, resource_type: Optional[SearchResourceType] = None) -> Dict[str, Any]:
        """Trigger index synchronization / re-indexing."""
        pass

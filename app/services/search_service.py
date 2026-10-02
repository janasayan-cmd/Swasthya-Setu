"""Centralized Unified Search Service (Phase 30).

CRITICAL PRINCIPLES:
- SEARCH ≠ CLINICAL DECISION
- SEARCH RELEVANCE ≠ CLINICAL PRIORITY
- SEARCH FAILURE ≠ NO RESULTS (explicit exceptions raised on provider issues)
- PHI-Safe Logging: Never log patient names, full DOBs, diagnoses, or notes.
- Centralized Audit & Metrics integration.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    SearchDisabledError,
    SearchProviderUnavailableError,
)
from app.integrations.search.base import SearchProvider
from app.schemas.audit import AuditEventType
from app.schemas.user import AuthenticatedUserContext
from app.schemas.search import (
    AutocompleteRequest,
    SearchRequest,
    SearchResourceType,
)
from app.schemas.search_result import (
    SearchIndexStatus,
    SearchResponse,
    SearchResponseData,
    SuggestionItem,
    SuggestionResponse,
    SuggestionResponseData,
)
from app.services.audit_service import AuditService
from app.services.search_authorization_service import SearchAuthorizationService
from app.services.search_normalization_service import SearchNormalizationService
from app.services.search_result_service import SearchResultService

logger = logging.getLogger(__name__)


class SearchService:
    """Core search coordinator handling validation, authorization, execution, and audit."""

    def __init__(
        self,
        provider: SearchProvider,
        normalization_service: SearchNormalizationService,
        authorization_service: SearchAuthorizationService,
        result_service: SearchResultService,
        audit_service: AuditService,
    ) -> None:
        self.provider = provider
        self.normalization_service = normalization_service
        self.authorization_service = authorization_service
        self.result_service = result_service
        self.audit_service = audit_service

    async def execute_search(
        self,
        request: SearchRequest,
        user: AuthenticatedUserContext,
    ) -> SearchResponse:
        """Execute validated and authorization-scoped search query."""
        if not getattr(settings, "SEARCH_ENABLED", True):
            raise SearchDisabledError("Search subsystem is currently disabled")

        start_time = time.time()

        # 1. Normalize query
        normalized_q = self.normalization_service.normalize_query(request.query)
        # Update request with normalized query text
        request.query = normalized_q

        # 2. Pre-search authorization scope determination
        p_filter = request.filters.patient_id if request.filters else None
        o_filter = request.filters.organization_id if request.filters else None
        f_filter = request.filters.facility_id if request.filters else None

        allowed_types, effective_patient_id, effective_org_id, effective_facility_id, is_admin = (
            self.authorization_service.evaluate_search_scope(
                user=user,
                requested_resource=request.resource_type,
                patient_id_filter=p_filter,
                org_id_filter=o_filter,
                facility_id_filter=f_filter,
            )
        )

        try:
            # 3. Provider search retrieval
            raw_items, _ = await self.provider.search(
                request=request,
                allowed_resource_types=allowed_types,
                actor_patient_id=effective_patient_id,
                actor_org_id=effective_org_id,
                actor_facility_id=effective_facility_id,
                is_admin=is_admin,
            )
        except Exception as e:
            logger.error(
                "Search provider failure: %s (query_category=%s)",
                str(e),
                "identifier" if self.normalization_service.is_identifier_query(normalized_q) else "text",
            )
            # Record audit event for provider failure
            await self.audit_service.record(
                event_type=AuditEventType.SEARCH_PROVIDER_FAILED,
                outcome="FAILURE",
                actor_id=user.user_id,
                action="search:execute",
                resource_type="search",
                resource_id=None,
                metadata={
                    "provider": self.provider.provider_name,
                    "error_category": "PROVIDER_ERROR",
                },
            )
            raise SearchProviderUnavailableError(f"Search provider unavailable: {str(e)}")

        # 4. Sorting and Pagination
        paged_items, pagination = self.result_service.sort_and_paginate(
            items=raw_items,
            page=request.page,
            page_size=request.page_size,
            sort=request.sort,
            sort_order=request.sort_order,
        )

        duration = time.time() - start_time

        # 5. Centralized Audit Logging (PHI-Safe)
        event_type = AuditEventType.SEARCH_EXECUTED
        if request.resource_type == SearchResourceType.PATIENT:
            event_type = AuditEventType.PATIENT_SEARCH_EXECUTED
        elif request.resource_type == SearchResourceType.DOCUMENT:
            event_type = AuditEventType.DOCUMENT_SEARCH_EXECUTED
        elif request.resource_type == SearchResourceType.CLINICAL_NOTE:
            event_type = AuditEventType.CLINICAL_NOTE_SEARCH_EXECUTED
        elif request.resource_type == SearchResourceType.MEDICATION:
            event_type = AuditEventType.MEDICATION_SEARCH_EXECUTED
        elif request.resource_type == SearchResourceType.FACILITY:
            event_type = AuditEventType.FACILITY_SEARCH_EXECUTED
        elif request.resource_type == SearchResourceType.ORGANIZATION:
            event_type = AuditEventType.ORGANIZATION_SEARCH_EXECUTED

        await self.audit_service.record(
            event_type=event_type,
            outcome="SUCCESS",
            actor_id=user.user_id,
            action="search:execute",
            resource_type=request.resource_type.value if request.resource_type else "all",
            resource_id=None,
            metadata={
                "result_count": pagination.total,
                "duration_ms": round(duration * 1000, 2),
                "is_zero_result": pagination.total == 0,
            },
        )

        # PHI-Safe Operational Log
        logger.info(
            "Search executed successfully [actor_id=%s, resource=%s, count=%d, latency_ms=%.2f]",
            user.user_id,
            request.resource_type.value if request.resource_type else "ALL",
            pagination.total,
            duration * 1000,
        )

        return SearchResponse(
            success=True,
            data=SearchResponseData(
                items=paged_items,
                pagination=pagination,
            ),
        )

    async def get_suggestions(
        self,
        request: AutocompleteRequest,
        user: AuthenticatedUserContext,
    ) -> SuggestionResponse:
        """Authorized suggestions without leaking confidential data."""
        if not getattr(settings, "SEARCH_ENABLED", True):
            raise SearchDisabledError("Search subsystem is currently disabled")

        normalized_q = self.normalization_service.normalize_query(request.query)

        allowed_types, effective_patient_id, effective_org_id, _, _ = (
            self.authorization_service.evaluate_search_scope(
                user=user,
                requested_resource=request.resource_type,
            )
        )

        raw_suggestions = await self.provider.get_suggestions(
            query=normalized_q,
            resource_type=request.resource_type,
            allowed_resource_types=allowed_types,
            limit=request.limit,
            actor_patient_id=effective_patient_id,
            actor_org_id=effective_org_id,
        )

        items = [
            SuggestionItem(
                text=s["text"],
                resource_type=s["resource_type"],
                resource_id=s.get("resource_id"),
            )
            for s in raw_suggestions
        ]

        return SuggestionResponse(
            success=True,
            data=SuggestionResponseData(suggestions=items),
        )

    async def get_admin_status(self) -> SearchIndexStatus:
        """Administrative index status and health check."""
        return await self.provider.get_index_status()

    async def trigger_admin_rebuild(self, resource_type: Optional[SearchResourceType] = None) -> Dict[str, Any]:
        """Trigger administrative index rebuild."""
        res = await self.provider.rebuild_index(resource_type=resource_type)
        await self.audit_service.record(
            event_type=AuditEventType.SEARCH_INDEX_REBUILT,
            outcome="SUCCESS",
            actor_id="admin",
            action="admin:search_rebuild",
            resource_type=resource_type.value if resource_type else "all",
            resource_id=res.get("job_id"),
            metadata={"status": res.get("status")},
        )
        return res

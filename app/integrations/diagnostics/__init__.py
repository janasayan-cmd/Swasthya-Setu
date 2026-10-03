"""Diagnostic & Laboratory Provider Integrations (Phase 34)."""

from app.integrations.diagnostics.base import (
    DiagnosticProvider,
    ProviderHealthResult,
    ProviderOrderCancelResult,
    ProviderOrderResult,
    ProviderOrderStatusResult,
    ProviderOrderSubmissionResult,
    ProviderReportPayload,
    ProviderResultPayload,
    ProviderState,
)

__all__ = [
    "DiagnosticProvider",
    "ProviderHealthResult",
    "ProviderOrderCancelResult",
    "ProviderOrderResult",
    "ProviderOrderStatusResult",
    "ProviderOrderSubmissionResult",
    "ProviderReportPayload",
    "ProviderResultPayload",
    "ProviderState",
]

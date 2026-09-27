"""Operational Metrics and Telemetry Endpoints (Phase 18)."""

from typing import Literal
from fastapi import APIRouter, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import get_settings
from app.core.metrics import metrics

router = APIRouter(tags=["Observability & Telemetry"])


@router.get(
    "/metrics",
    summary="Application operational metrics",
    description="Exposes structured operational metrics in Prometheus text format or JSON for monitoring dashboards.",
)
async def get_metrics(
    format: Literal["prometheus", "json"] = Query(default="prometheus", description="Output format"),
) -> Response:
    """Retrieve operational telemetry metrics."""
    settings = get_settings()

    if format == "json":
        summary = metrics.get_summary()
        summary["service"] = settings.APP_NAME
        summary["environment"] = settings.APP_ENV
        summary["version"] = settings.APP_VERSION
        return JSONResponse(content=summary, status_code=status.HTTP_200_OK)

    # Default to Prometheus exposition text format
    prom_text = metrics.to_prometheus_text()
    return PlainTextResponse(
        content=prom_text,
        status_code=status.HTTP_200_OK,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )

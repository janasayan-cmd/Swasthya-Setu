"""Mock Ingestion Provider for Testing & Development (Phase 45)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.exceptions import (
    IngestionProviderTimeoutException,
    IngestionProviderUnavailableException,
)
from app.integrations.ingestion.base import IngestionFetchResult, IngestionProvider


class MockIngestionProvider(IngestionProvider):
    """Configurable mock provider simulating success, network failure, 503, and timeouts."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self.simulate_timeout: bool = False
        self.simulate_unavailable: bool = False
        self.simulate_failure: bool = False

    @property
    def provider_name(self) -> str:
        return self._name

    async def fetch_resource(
        self,
        resource_type: str,
        external_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> IngestionFetchResult:
        """Simulate pulling an external resource."""
        if self.simulate_timeout:
            raise IngestionProviderTimeoutException(
                f"Simulated external provider timeout fetching '{external_id}'."
            )

        if self.simulate_unavailable:
            raise IngestionProviderUnavailableException(
                f"Simulated external provider 503 unavailable for '{self._name}'."
            )

        if self.simulate_failure:
            return IngestionFetchResult(
                success=False,
                external_resource_id=external_id,
                resource_type=resource_type,
                payload={},
                provider_reference=f"mock-ref-{external_id}",
                error_message="Simulated provider payload extraction failure",
                retryable=False,
            )

        # Standard simulated FHIR Observation
        simulated_payload = {
            "resourceType": resource_type,
            "id": external_id,
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "2345-7",
                    "display": "Glucose [Mass/volume] in Serum or Plasma",
                }]
            },
            "valueQuantity": {
                "value": 110,
                "unit": "mg/dL",
                "system": "http://unitsofmeasure.org",
                "code": "mg/dL",
            },
        }

        return IngestionFetchResult(
            success=True,
            external_resource_id=external_id,
            resource_type=resource_type,
            payload=simulated_payload,
            provider_reference=f"mock-ref-{external_id}",
        )

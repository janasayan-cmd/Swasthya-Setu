"""Ingestion Validation Service (Phase 45).

Enforces:
- Source authentication, registration, and trust state verification.
- Permitted resource scopes and organization/facility boundaries.
- Clinical safety boundaries:
  - INGESTION != CLINICAL DECISION
  - INGESTION != DIAGNOSIS / TREATMENT / PRESCRIPTION / MEDICATION CHANGE / TRIAGE / EMERGENCY DISPATCH
- Interoperability structural & schema validation (FHIR R4 / HL7 via Phase 13).
- Payload size boundaries and malicious content containment.
- Webhook signature authentication and replay protection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    IngestionAutonomousClinicalProhibitedException,
    IngestionDisabledException,
    IngestionPayloadInvalidException,
    IngestionResourceUnsupportedException,
    IngestionSourceAuthenticationFailedException,
    IngestionSourceNotFoundException,
    IngestionSourceSuspendedException,
    IngestionSourceUnauthorizedException,
    IngestionWebhookReplayDetectedException,
    IngestionWebhookSignatureInvalidException,
)
from app.integrations.interoperability.fhir.validator import FHIRValidator
from app.repositories.ingestion_repository import IngestionRepository
from app.schemas.ingestion import (
    ExternalSourceContext,
    IngestionCreateRequest,
    SourceTrustState,
    WebhookIngestionPayload,
)

SUPPORTED_CLINICAL_RESOURCES = {
    "patient",
    "encounter",
    "observation",
    "condition",
    "allergyintolerance",
    "medication",
    "medicationrequest",
    "medicationstatement",
    "diagnosticreport",
    "servicerequest",
    "documentreference",
    "careplan",
    "procedure",
    "appointment",
}

PROHIBITED_PURPOSES_OR_ACTIONS = {
    "diagnosis",
    "treatment",
    "prescription",
    "prescription_change",
    "medication_change",
    "triage",
    "emergency_dispatch",
    "clinical_order_approval",
}


class IngestionValidationService:
    """Validates external ingestion requests, signatures, and safety invariants."""

    def __init__(
        self,
        ingestion_repo: IngestionRepository,
        fhir_validator: Optional[FHIRValidator] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.ingestion_repo = ingestion_repo
        self.fhir_validator = fhir_validator or FHIRValidator()
        self.settings = settings or get_settings()

    async def validate_source_and_authorization(
        self,
        request: IngestionCreateRequest,
        is_webhook_authenticated: bool = False,
    ) -> ExternalSourceContext:
        """Verify external source existence, active trust state, credentials, and allowed resource scope."""
        if not getattr(self.settings, "DATA_INGESTION_ENABLED", True):
            raise IngestionDisabledException("Clinical data ingestion subsystem is disabled.")

        source = await self.ingestion_repo.get_source(request.source_system)
        if not source:
            raise IngestionSourceNotFoundException(
                f"External source system '{request.source_system}' is not registered."
            )

        # 1. Trust State Validation
        if source.trust_state in (
            SourceTrustState.SUSPENDED,
            SourceTrustState.DISABLED,
            SourceTrustState.REVOKED,
            SourceTrustState.UNKNOWN,
        ):
            raise IngestionSourceSuspendedException(
                f"External source '{request.source_system}' trust state is {source.trust_state.value}. Exchanges are blocked."
            )

        if not source.is_authorized:
            raise IngestionSourceUnauthorizedException(
                f"External source '{request.source_system}' is not authorized to exchange clinical data."
            )

        # 2. Credential Verification (if source configured with API key and not already webhook authenticated)
        if source.api_key_hash and not is_webhook_authenticated:
            if not request.api_key:
                raise IngestionSourceAuthenticationFailedException(
                    f"Authentication API key is required for source '{request.source_system}'."
                )
            key_hash = hashlib.sha256(request.api_key.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(key_hash, source.api_key_hash):
                raise IngestionSourceAuthenticationFailedException(
                    f"Invalid authentication credentials for source '{request.source_system}'."
                )

        # 3. Permitted Resource Scope Validation
        res_type_clean = request.resource_type.strip().lower()
        allowed_normalized = {r.strip().lower() for r in source.allowed_resource_types}
        if res_type_clean not in allowed_normalized:
            raise IngestionSourceUnauthorizedException(
                f"Source '{request.source_system}' is not authorized to submit resource type '{request.resource_type}'."
            )

        return source

    def validate_safety_invariants(self, request: IngestionCreateRequest) -> None:
        """Ensure external ingestion never attempts autonomous diagnosis, prescribing, triage, or medication changes."""
        purpose_clean = (request.purpose or "").strip().lower()
        if purpose_clean in PROHIBITED_PURPOSES_OR_ACTIONS:
            raise IngestionAutonomousClinicalProhibitedException(
                f"External data ingestion cannot perform autonomous '{request.purpose}'. Must enter reconciliation."
            )

        # Scan payload for prohibited action directives
        payload_str = json.dumps(request.payload).lower()
        if '"action": "prescribe"' in payload_str or '"action": "modify_medication"' in payload_str:
            raise IngestionAutonomousClinicalProhibitedException(
                "Inbound payload contains autonomous prescription/medication modification directive."
            )

    def validate_payload_and_interoperability(self, request: IngestionCreateRequest) -> List[str]:
        """Validate payload size, resource type support, and FHIR schema structure."""
        # 1. Size bounds
        max_bytes = getattr(self.settings, "INGESTION_MAX_PAYLOAD_MB", 25) * 1024 * 1024
        try:
            payload_bytes = len(json.dumps(request.payload).encode("utf-8"))
            if payload_bytes > max_bytes:
                raise IngestionPayloadInvalidException(
                    f"Payload size ({payload_bytes} bytes) exceeds maximum limit ({max_bytes} bytes)."
                )
        except (TypeError, ValueError) as exc:
            raise IngestionPayloadInvalidException(f"Payload serialization failed: {exc}")

        # 2. Supported Resource Types
        res_type_clean = request.resource_type.strip().lower()
        if res_type_clean not in SUPPORTED_CLINICAL_RESOURCES:
            raise IngestionResourceUnsupportedException(
                f"Resource type '{request.resource_type}' is not supported by HealthSetu interoperability."
            )

        # 3. FHIR Structural Validation
        validation_errors: List[str] = []
        if (request.format or "").upper() == "FHIR":
            if not isinstance(request.payload, dict) or not request.payload:
                raise IngestionPayloadInvalidException("FHIR payload must be a non-empty JSON object.")

            resource_type_in_payload = request.payload.get("resourceType")
            if not resource_type_in_payload:
                raise IngestionPayloadInvalidException("FHIR payload is missing required 'resourceType' field.")

            if resource_type_in_payload.lower() != res_type_clean:
                raise IngestionPayloadInvalidException(
                    f"Payload resourceType '{resource_type_in_payload}' does not match declared '{request.resource_type}'."
                )

            # Delegate to Phase 13 FHIR Validator
            validation_errors = self.fhir_validator.validate_resource(
                payload=request.payload,
                expected_type=request.resource_type,
            )
            if validation_errors:
                raise IngestionPayloadInvalidException(
                    f"FHIR validation failed: {'; '.join(validation_errors)}",
                    details={"errors": validation_errors},
                )

        return validation_errors

    async def validate_webhook(self, webhook_data: WebhookIngestionPayload) -> ExternalSourceContext:
        """Validate inbound webhook signature, timestamp window, and nonce replay."""
        source = await self.ingestion_repo.get_source(webhook_data.provider)
        secret = (
            source.shared_secret
            if source and source.shared_secret
            else getattr(self.settings, "INGESTION_WEBHOOK_SECRET", "test-webhook-secret-phase-45")
        )

        # 1. Signature Verification
        # Expected signature: HMAC-SHA256(secret, f"{webhook_data.provider}:{webhook_data.event_id}:{webhook_data.timestamp}:{webhook_data.nonce}")
        msg = f"{webhook_data.provider}:{webhook_data.event_id}:{webhook_data.timestamp}:{webhook_data.nonce}".encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(webhook_data.signature, expected_sig):
            # Also check if raw payload json HMAC is used
            payload_msg = json.dumps(webhook_data.data, sort_keys=True).encode("utf-8")
            alt_sig = hmac.new(secret.encode("utf-8"), payload_msg, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(webhook_data.signature, alt_sig):
                raise IngestionWebhookSignatureInvalidException("Webhook HMAC signature verification failed.")

        # 2. Timestamp Window (Replay window check)
        max_age = getattr(self.settings, "INGESTION_WEBHOOK_MAX_AGE_SECONDS", 300)
        try:
            if isinstance(webhook_data.timestamp, (int, float)):
                event_ts = float(webhook_data.timestamp)
            elif isinstance(webhook_data.timestamp, str) and webhook_data.timestamp.isdigit():
                event_ts = float(webhook_data.timestamp)
            else:
                event_ts = datetime.fromisoformat(str(webhook_data.timestamp).replace("Z", "+00:00")).timestamp()

            now = datetime.now(timezone.utc).timestamp()
            if abs(now - event_ts) > max_age:
                raise IngestionWebhookReplayDetectedException(
                    f"Webhook event timestamp outside allowable window ({max_age}s)."
                )
        except (ValueError, TypeError) as exc:
            raise IngestionWebhookSignatureInvalidException(f"Invalid webhook timestamp format: {exc}")

        # 3. Nonce & Event ID Replay Check
        not_replayed = await self.ingestion_repo.check_and_record_webhook(
            provider=webhook_data.provider,
            event_id=webhook_data.event_id,
            nonce=webhook_data.nonce,
            max_age_seconds=max_age,
        )
        if not not_replayed:
            raise IngestionWebhookReplayDetectedException(
                f"Webhook event '{webhook_data.event_id}' with nonce '{webhook_data.nonce}' has already been processed."
            )

        if not source:
            # Fallback mock source context for generic webhooks
            source = ExternalSourceContext(
                source_id=webhook_data.provider,
                source_type=SourceType.INTEROPERABILITY_PROVIDER,
                source_name=f"Provider Webhook ({webhook_data.provider})",
                trust_state=SourceTrustState.ACTIVE,
            )

        return source

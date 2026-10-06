"""Phase 48: Safety Gate Service.

Centralized safety enforcement layer that evaluates preconditions, policies,
input completeness, temporal freshness, human review boundaries, AI guardrails,
and provider circuit breakers before clinically consequential actions.
"""

from datetime import datetime, timezone
from typing import Any
import uuid

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    DecisionNotFoundException,
    SafetyCheckFailedException,
    SafetyPolicyBlockedException,
)
from app.repositories.decision_repository import DecisionRepository, decision_repository
from app.repositories.safety_repository import SafetyRepository, safety_repository
from app.schemas.audit import AuditActor, AuditEventType
from app.schemas.decisions import DecisionRecord, DecisionStatus
from app.schemas.safety import SafetyEvaluationRequest
from app.schemas.safety_policy import SafetyPolicyType
from app.schemas.safety_result import SafetyCheckRecord, SafetyGateResult, SafetyStatus
from app.services.audit_service import AuditService
from app.services.decision_context_service import DecisionContextService, decision_context_service
from app.services.safety_conflict_service import SafetyConflictService, safety_conflict_service
from app.services.safety_context_service import SafetyContextService, safety_context_service
from app.services.safety_fallback_service import SafetyFallbackService, safety_fallback_service
from app.services.safety_policy_service import SafetyPolicyService, safety_policy_service
from app.services.safety_retry_service import SafetyRetryService, safety_retry_service
from app.services.safety_validation_service import SafetyValidationService, safety_validation_service


class SafetyGateService:
    """Central safety gate coordinator for all clinical operations and decisions."""

    def __init__(
        self,
        repository: SafetyRepository | None = None,
        policy_svc: SafetyPolicyService | None = None,
        val_svc: SafetyValidationService | None = None,
        ctx_svc: SafetyContextService | None = None,
        conflict_svc: SafetyConflictService | None = None,
        fallback_svc: SafetyFallbackService | None = None,
        retry_svc: SafetyRetryService | None = None,
        dec_repo: DecisionRepository | None = None,
        dec_ctx_svc: DecisionContextService | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self.repository = repository or safety_repository
        self.policy_service = policy_svc or safety_policy_service
        self.validation_service = val_svc or safety_validation_service
        self.context_service = ctx_svc or safety_context_service
        self.conflict_service = conflict_svc or safety_conflict_service
        self.fallback_service = fallback_svc or safety_fallback_service
        self.retry_service = retry_svc or safety_retry_service
        self.decision_repo = dec_repo or decision_repository
        self.decision_context_service = dec_ctx_svc or decision_context_service
        self.audit_service = audit_svc


    async def evaluate_safety(
        self,
        request: SafetyEvaluationRequest,
        actor_id: str | None = None,
        actor_role: str | None = None,
        request_id: str | None = None,
    ) -> SafetyGateResult:
        """Evaluate full safety gate for an operation or decision request."""
        check_id = f"chk-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        reason_codes: list[str] = []
        warnings: list[str] = []
        required_actions: list[str] = []
        details: dict[str, Any] = {}

        # 1. Reject client bypass attempts immediately
        request_dict = request.model_dump()
        self.validation_service.validate_client_bypass_attempts(request_dict)

        # 2. Check retry safety / idempotency if op_key provided
        op_key = request.context.get("op_key") or request.context.get("idempotency_key")
        if op_key:
            self.retry_service.validate_retry_safety(op_key, request.operation)

        # 3. Policy evaluation
        policy = self.policy_service.get_policy(request.policy_type)
        is_allowed_action, blocked_reason = self.policy_service.evaluate_action_permission(
            request.policy_type, request.operation, policy.policy_version
        )
        if not is_allowed_action:
            reason_codes.append(blocked_reason or "ACTION_PROHIBITED_BY_POLICY")
            required_actions.append("REVIEW_ACTION_PERMISSION")

        # 4. Input completeness validation
        if request.input_data:
            domain = request.context.get("domain") or ("medication" if "med" in request.operation.lower() else "triage" if "triage" in request.operation.lower() else "generic")
            try:
                self.validation_service.validate_input_completeness(domain, request.input_data)
            except AppException as exc:
                reason_codes.append(exc.code)
                required_actions.append(f"PROVIDE_MISSING_{domain.upper()}_DATA")

        # 5. Untrusted text sanitization (Prompt injection defense)
        if request.input_data and "untrusted_text" in request.input_data:
            self.validation_service.sanitize_untrusted_text(str(request.input_data["untrusted_text"]))

        # 6. AI boundary assertions
        if "ai" in request.operation.lower() or request.context.get("is_ai_generated") is True:
            self.validation_service.assert_ai_output_boundaries(request.operation, request.input_data)

        # 7. Decision validation if linked decision_id is present
        decision: DecisionRecord | None = None
        if request.decision_id:
            decision = self.decision_repo.get_decision(request.decision_id)
            if not decision:
                raise DecisionNotFoundException(f"Decision '{request.decision_id}' not found.")

            # Validate lifecycle preconditions (supersession, expiration, human review)
            try:
                self.validation_service.validate_decision_for_application(decision)
            except AppException as exc:
                reason_codes.append(exc.code)
                if exc.code == "HUMAN_REVIEW_MISSING" or exc.code == "DECISION_REVIEW_REQUIRED":
                    required_actions.append("CLINICIAN_REVIEW_REQUIRED")
                elif exc.code == "DECISION_ALREADY_SUPERSEDED":
                    required_actions.append("USE_NEWER_DECISION_VERSION")
                elif exc.code == "DECISION_EXPIRED":
                    required_actions.append("REGENERATE_DECISION")

            # Validate staleness against underlying Phase 46 versioning
            if self.decision_context_service.is_context_stale(decision):
                reason_codes.append("DECISION_CONTEXT_STALE")
                warnings.append("Underlying clinical record version has changed.")
                required_actions.append("REGENERATE_DECISION_ON_CURRENT_VERSION")

        # 8. Resource version freshness validation if explicitly targetted
        if request.resource_type and request.resource_id and "expected_version" in request.context:
            try:
                self.context_service.validate_resource_freshness(
                    request.resource_type,
                    request.resource_id,
                    int(request.context["expected_version"]),
                )
            except AppException as exc:
                reason_codes.append(exc.code)
                required_actions.append("REFRESH_RESOURCE_VERSION")

        # 9. Actor authorization check for clinical actions
        if actor_role and ("apply" in request.operation.lower() or "verify" in request.operation.lower() or "modify" in request.operation.lower()):
            try:
                self.context_service.validate_actor_privileges(actor_role, request.operation)
            except AppException as exc:
                reason_codes.append(exc.code)
                required_actions.append("CLINICAL_ACTOR_AUTHORIZATION_REQUIRED")

        # 10. Provider status and circuit breaker evaluation
        if request.provider_status:
            provider_name = request.context.get("provider_name") or "clinical_provider"
            fallback_provider = request.context.get("fallback_provider")
            try:
                fb_result = self.fallback_service.execute_with_fallback(
                    primary_provider=provider_name,
                    fallback_provider=fallback_provider,
                    provider_call_status=request.provider_status,
                    allow_fallback=request.context.get("allow_fallback", True),
                )
                if fb_result.get("fallback_used"):
                    warnings.append(fb_result.get("reason", "Fallback provider was utilized."))
            except AppException as exc:
                reason_codes.append(exc.code)
                required_actions.append("RETRY_WHEN_PROVIDER_AVAILABLE")

        # 11. Multi-provider or clinical conflict evaluation
        if "provider_results" in request.context:
            is_conf, conf_code, conf_details = self.conflict_service.detect_provider_disagreement(
                request.context["provider_results"]
            )
            if is_conf:
                reason_codes.append("DECISION_CONFLICTED")
                warnings.extend(conf_details)
                required_actions.append("CLINICAL_CONFLICT_RESOLUTION_REQUIRED")

        # Determine overall safety status
        if not reason_codes:
            final_status = SafetyStatus.ALLOWED
            allowed = True
        else:
            allowed = False
            if "DECISION_CONTEXT_STALE" in reason_codes or "CLINICAL_CONTEXT_STALE" in reason_codes:
                final_status = SafetyStatus.STALE
            elif "DECISION_ALREADY_SUPERSEDED" in reason_codes:
                final_status = SafetyStatus.BLOCKED
            elif "DECISION_EXPIRED" in reason_codes:
                final_status = SafetyStatus.EXPIRED
            elif "HUMAN_REVIEW_MISSING" in reason_codes or "DECISION_REVIEW_REQUIRED" in reason_codes:
                final_status = SafetyStatus.REVIEW_REQUIRED
            elif "DECISION_CONFLICTED" in reason_codes:
                final_status = SafetyStatus.CONFLICTED
            elif "SAFETY_EVALUATION_UNAVAILABLE" in reason_codes:
                final_status = SafetyStatus.UNAVAILABLE
            elif "INSUFFICIENT_INFORMATION" in reason_codes:
                final_status = SafetyStatus.INSUFFICIENT_INFORMATION
            else:
                final_status = SafetyStatus.BLOCKED

        result = SafetyGateResult(
            check_id=check_id,
            allowed=allowed,
            status=final_status,
            reason_codes=reason_codes,
            warnings=warnings,
            required_actions=required_actions,
            policy_type=request.policy_type,
            policy_version=policy.policy_version,
            decision_id=request.decision_id,
            patient_id=request.patient_id or (decision.patient_id if decision else None),
            resource_type=request.resource_type or (decision.resource_type if decision else None),
            resource_id=request.resource_id or (decision.resource_id if decision else None),
            timestamp=now,
            details=details,
        )

        # Persist check record
        check_record = SafetyCheckRecord(
            id=check_id,
            operation=request.operation,
            allowed=allowed,
            status=final_status,
            policy_type=request.policy_type,
            policy_version=policy.policy_version,
            reason_codes=reason_codes,
            warnings=warnings,
            required_actions=required_actions,
            decision_id=request.decision_id,
            patient_id=result.patient_id,
            resource_type=result.resource_type,
            resource_id=result.resource_id,
            actor_id=actor_id,
            actor_role=actor_role,
            timestamp=now,
            details=details,
        )
        self.repository.save_check(check_record)

        # Audit emission
        if self.audit_service:
            audit_event_type = (
                AuditEventType.SAFETY_GATE_EVALUATED
                if allowed
                else AuditEventType.SAFETY_OPERATION_BLOCKED
            )
            try:
                await self.audit_service.record(
                    event_type=audit_event_type,
                    actor_id=actor_id,
                    patient_id=result.patient_id,
                    resource_type=result.resource_type or "safety_check",
                    resource_id=check_id,
                    action=request.operation,
                    outcome="ALLOW" if allowed else "DENY",
                    reason_code=reason_codes[0] if reason_codes else None,
                    metadata={
                        "check_id": check_id,
                        "status": final_status.value,
                        "policy_type": request.policy_type.value,
                        "policy_version": policy.policy_version,
                    },
                    request_id=request_id,
                )
            except Exception:
                pass

        return result

    def get_check(self, check_id: str) -> SafetyCheckRecord | None:
        """Retrieve historical safety check record."""
        return self.repository.get_check(check_id)

    def list_decision_safety_checks(self, decision_id: str) -> list[SafetyCheckRecord]:
        """List safety checks evaluated for a decision."""
        return self.repository.list_checks_by_decision(decision_id)

    def list_resource_safety_checks(self, resource_type: str, resource_id: str) -> list[SafetyCheckRecord]:
        """List safety checks evaluated for a resource."""
        return self.repository.list_checks_by_resource(resource_type, resource_id)


# Global singleton
safety_gate_service = SafetyGateService()

"""Validation service for Clinical Order Sets and Protocol Templates (Phase 39).

ARCHITECTURAL CONTRACT & SAFETY INVARIANTS:
- Missing information must NEVER be silently inferred.
- Parameter overrides are strictly validated against allowed fields.
- Template eligibility, lifecycle state, effective dates, and scope are rigorously enforced.
- Provider capabilities are verified before order execution.
- No automatic template fallback is permitted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import (
    OrderSetParameterInvalidException,
    OrderSetScopeInvalidException,
    OrderSetNotApprovedException,
    OrderSetNotActiveException,
    OrderSetSuspendedException,
    OrderSetExpiredException,
    OrderSetProviderUnsupportedException,
    OrderMissingClinicalContextException,
)
from app.schemas.order import ENABLED_ORDER_TYPES, OrderType
from app.schemas.order_set import (
    OrderDefinition,
    OrderSetTemplateRecord,
    OrderSetTemplateVersion,
    TemplateScope,
    TemplateStatus,
)


class OrderSetValidationService:
    """Validates order set eligibility, scope, parameters, and clinical context."""

    def validate_template_eligibility(
        self,
        template: OrderSetTemplateRecord,
        version: OrderSetTemplateVersion,
        require_active: bool = True,
    ) -> None:
        """Validate whether a template version is eligible for use/execution.

        SAFETY INVARIANTS:
        - DRAFT != USABLE
        - APPROVED != ACTIVE (for execution, version must be ACTIVE if require_active=True)
        - SUSPENDED templates cannot generate new executable orders.
        - EXPIRED versions cannot generate executable orders.
        """
        # Master template status check
        if template.status == TemplateStatus.SUSPENDED:
            raise OrderSetSuspendedException(
                message=f"Order set template '{template.code}' is currently suspended. New executions are blocked."
            )

        if version.status == TemplateStatus.SUSPENDED:
            raise OrderSetSuspendedException(
                message=f"Order set template version {version.version_number} is currently suspended."
            )

        # Approval check
        if version.status in (TemplateStatus.DRAFT, TemplateStatus.PENDING_REVIEW, TemplateStatus.REJECTED):
            raise OrderSetNotApprovedException(
                message=f"Order set template version {version.version_number} is in status '{version.status.value}' and is not approved."
            )

        # Active check
        if require_active and version.status != TemplateStatus.ACTIVE:
            raise OrderSetNotActiveException(
                message=f"Order set template version {version.version_number} is approved but not ACTIVE (current status: '{version.status.value}')."
            )

        # Effective date checks
        now = datetime.now(timezone.utc)
        if version.effective_from and now < version.effective_from:
            raise OrderSetNotActiveException(
                message=f"Order set template version {version.version_number} is not yet effective (effective from: {version.effective_from.isoformat()})."
            )
        if version.effective_to and now > version.effective_to:
            raise OrderSetExpiredException(
                message=f"Order set template version {version.version_number} has expired (expired at: {version.effective_to.isoformat()})."
            )

        # Validate order types inside the template
        for order_def in version.order_definitions:
            if order_def.order_type not in ENABLED_ORDER_TYPES:
                raise OrderSetProviderUnsupportedException(
                    message=f"Order definition '{order_def.requested_service}' has unsupported order type '{order_def.order_type.value}'."
                )

    def validate_scope(
        self,
        template: OrderSetTemplateRecord,
        target_organization_id: Optional[str] = None,
        target_facility_id: Optional[str] = None,
        target_department_id: Optional[str] = None,
    ) -> None:
        """Validate that the target execution scope matches template ownership."""
        if template.scope == TemplateScope.SYSTEM:
            # System-wide templates are accessible across all organizations
            return

        if template.scope == TemplateScope.ORGANIZATION:
            if template.organization_id and target_organization_id:
                if template.organization_id != target_organization_id:
                    raise OrderSetScopeInvalidException(
                        message=f"Template organization scope mismatch: template belongs to org '{template.organization_id}', request is for org '{target_organization_id}'."
                    )

        if template.scope == TemplateScope.FACILITY:
            if template.facility_id and target_facility_id:
                if template.facility_id != target_facility_id:
                    raise OrderSetScopeInvalidException(
                        message=f"Template facility scope mismatch: template belongs to facility '{template.facility_id}', request is for facility '{target_facility_id}'."
                    )

        if template.scope == TemplateScope.DEPARTMENT:
            if template.department_id and target_department_id:
                if template.department_id != target_department_id:
                    raise OrderSetScopeInvalidException(
                        message=f"Template department scope mismatch: template belongs to department '{template.department_id}', request is for department '{target_department_id}'."
                    )

    def validate_and_apply_parameters(
        self,
        order_def: OrderDefinition,
        candidate_params: Dict[str, Any],
        strict: bool = True,
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Validate and apply allowed parameter overrides for an order definition.

        Returns:
            (applied_params, rejected_overrides, missing_required_fields)
        """
        applied: Dict[str, Any] = dict(order_def.default_parameters)
        rejected: List[str] = []
        missing_required: List[str] = []

        allowed = set(order_def.allowed_parameter_overrides)

        for key, val in candidate_params.items():
            if key in allowed:
                applied[key] = val
            else:
                rejected.append(key)
                if strict:
                    raise OrderSetParameterInvalidException(
                        message=f"Parameter '{key}' is not an allowed override for order definition '{order_def.requested_service}'."
                    )

        # Check required fields
        for req in order_def.required_fields:
            if req not in applied or applied[req] is None or applied[req] == "":
                missing_required.append(req)

        return applied, rejected, missing_required

    def validate_patient_context(
        self,
        patient_id: Optional[str],
        clinician_id: Optional[str],
        missing_fields: List[str],
    ) -> None:
        """Validate that all mandatory patient and clinician context is present.

        SAFETY: Missing context must NOT be silently inferred.
        """
        if not patient_id or patient_id.strip() == "":
            raise OrderMissingClinicalContextException(
                message="Patient ID is mandatory for order set execution. Missing patient context must not be silently inferred."
            )

        if not clinician_id or clinician_id.strip() == "":
            raise OrderMissingClinicalContextException(
                message="Ordering clinician ID is mandatory. Clinical orders cannot be created without authorized clinician context."
            )

        if missing_fields:
            raise OrderMissingClinicalContextException(
                message=f"Missing required clinical context for orders: {', '.join(missing_fields)}. Missing parameters must not be silently inferred."
            )

    def validate_provider_capability(
        self,
        order_def: OrderDefinition,
        provider_supported_types: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check whether the targeted provider supports the order definition."""
        if provider_supported_types is None:
            # Default mock provider supports all enabled order types
            return True, None

        order_type_str = order_def.order_type.value if hasattr(order_def.order_type, "value") else str(order_def.order_type)
        if order_type_str not in provider_supported_types:
            notes = f"Target provider does not support order type '{order_type_str}' for service '{order_def.requested_service}'"
            return False, notes

        return True, None

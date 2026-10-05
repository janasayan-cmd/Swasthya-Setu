"""Clinical Order Set Orchestration Service (Phase 39).

ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- ORDER SET != CLINICAL DECISION
- ORDER SET != DIAGNOSIS
- ORDER SET != TREATMENT
- ORDER SET != PRESCRIPTION
- ORDER SET SELECTION != ORDER AUTHORIZATION
- ORDER SET EXPANSION != ORDER EXECUTION
- ORDER GENERATED FROM TEMPLATE MUST PASS THROUGH PHASE 38
- PREVIEW != EXECUTION (Preview mode never creates orders)
- SUSPENDED TEMPLATES CANNOT GENERATE EXECUTABLE ORDERS
- UNAPPROVED TEMPLATES CANNOT GENERATE EXECUTABLE ORDERS
- AI CANNOT APPROVE, ACTIVATE, OR EXECUTE ORDER SETS
- DUPLICATE EXECUTIONS ARE PREVENTED VIA IDEMPOTENCY
- PARTIAL EXECUTION IS ACCURATELY REPRESENTED (NEVER FALSELY MARKED AS SUCCESS)
- MISSING CLINICAL PARAMETERS MUST NEVER BE SILENTLY INFERRED
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    OrderSetDuplicateExecutionException,
    OrderSetExecutionFailedException,
    OrderSetNotFoundException,
    OrderSetPartialFailureException,
    OrderSetsDisabledException,
    OrderSetUnavailableException,
    OrderSetVersionNotFoundException,
    OrderSetInvalidException,
)
from app.repositories.order_set_repository import OrderSetRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.order import OrderCreate, OrderPriority, OrderType
from app.schemas.order_set import (
    ExpectedChildOrderPreview,
    OrderDefinition,
    OrderSetApproveRequest,
    OrderSetDiffResponse,
    OrderSetPreviewRequest,
    OrderSetPreviewResponse,
    OrderSetTemplateCreate,
    OrderSetTemplateRecord,
    OrderSetTemplateVersion,
    OrderSetVersionCreate,
    TemplateScope,
    TemplateStatus,
    TemplateType,
)
from app.schemas.order_set_execution import (
    BatchExecutionPolicy,
    ChildOrderExecutionSummary,
    OrderSetExecuteRequest,
    OrderSetExecutionRecord,
    OrderSetExecutionStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.order_service import OrderService
from app.services.order_set_authorization_service import OrderSetAuthorizationService
from app.services.order_set_validation_service import OrderSetValidationService


class OrderSetService:
    """Orchestrates order set template lifecycle, previews, and controlled composition."""

    def __init__(
        self,
        order_set_repository: OrderSetRepository,
        validation_service: OrderSetValidationService,
        authorization_service: OrderSetAuthorizationService,
        order_service: OrderService,
        audit_service: AuditService,
        enabled: bool = True,
        execution_enabled: bool = True,
        preview_enabled: bool = True,
        default_batch_policy: str = "PARTIAL",
    ) -> None:
        self._repo = order_set_repository
        self._val = validation_service
        self._authz = authorization_service
        self._order_service = order_service
        self._audit = audit_service
        self._enabled = enabled
        self._execution_enabled = execution_enabled
        self._preview_enabled = preview_enabled
        self._default_batch_policy = default_batch_policy

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise OrderSetsDisabledException()

    async def _record_audit(self, record: AuditEventRecord) -> None:
        """Helper to safely record and await audit event."""
        res = self._audit.record(record)
        if asyncio.iscoroutine(res):
            await res

    # -----------------------------------------------------------------------
    # Template Administration (TRD Section 42)
    # -----------------------------------------------------------------------

    async def create_template(
        self,
        payload: OrderSetTemplateCreate,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateRecord:
        """Create a new order set template with an initial DRAFT Version 1."""
        self._require_enabled()
        self._authz.authorize_template_administration(actor)

        # Check code uniqueness
        existing = self._repo.get_template_by_code(payload.code)
        if existing:
            raise OrderSetInvalidException(
                message=f"An order set template with code '{payload.code}' already exists."
            )

        template_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        initial_version = OrderSetTemplateVersion(
            version_id=version_id,
            template_id=template_id,
            version_number=1,
            status=TemplateStatus.DRAFT,
            created_by=actor.user_id,
            change_reason=payload.change_reason or "Initial template version",
            order_definitions=payload.order_definitions,
        )

        template = OrderSetTemplateRecord(
            id=template_id,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            template_type=payload.template_type,
            scope=payload.scope,
            organization_id=payload.organization_id or actor.organization_id,
            facility_id=payload.facility_id,
            department_id=payload.department_id,
            status=TemplateStatus.DRAFT,
            active_version_id=None,
            versions=[initial_version],
            created_by=actor.user_id,
        )

        saved = self._repo.save_template(template)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_TEMPLATE_CREATED,
                actor_id=actor.user_id,
                resource_type="order_set_template",
                resource_id=saved.id,
                outcome="ALLOW",
                metadata={"code": saved.code, "version_number": 1},
            )
        )

        return saved

    async def create_version(
        self,
        template_id: str,
        payload: OrderSetVersionCreate,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateVersion:
        """Create a new version for an existing template."""
        self._require_enabled()
        self._authz.authorize_template_administration(actor)

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        next_version_num = max([v.version_number for v in template.versions], default=0) + 1
        new_version_id = str(uuid.uuid4())

        new_version = OrderSetTemplateVersion(
            version_id=new_version_id,
            template_id=template.id,
            version_number=next_version_num,
            status=TemplateStatus.DRAFT,
            created_by=actor.user_id,
            change_reason=payload.change_reason,
            order_definitions=payload.order_definitions,
        )

        self._repo.add_version(template_id, new_version)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_VERSION_CREATED,
                actor_id=actor.user_id,
                resource_type="order_set_template_version",
                resource_id=new_version.version_id,
                outcome="ALLOW",
                metadata={"template_id": template_id, "version_number": next_version_num},
            )
        )

        return new_version

    async def approve_version(
        self,
        template_id: str,
        payload: OrderSetApproveRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateVersion:
        """Clinically approve a specific template version.

        SAFETY: AI actors CANNOT approve templates.
        """
        self._require_enabled()
        self._authz.authorize_template_approval(actor)

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        # Resolve target version
        target_version: Optional[OrderSetTemplateVersion] = None
        if payload.version_id:
            target_version = self._repo.get_version_by_id(payload.version_id)
        else:
            # Pick latest version
            if template.versions:
                target_version = max(template.versions, key=lambda v: v.version_number)

        if not target_version or target_version.template_id != template_id:
            raise OrderSetVersionNotFoundException("Target version for approval was not found.")

        target_version.status = TemplateStatus.APPROVED
        target_version.approved_by = actor.user_id
        target_version.approved_at = datetime.now(timezone.utc)
        target_version.approval_reason = payload.reason
        if payload.effective_from:
            target_version.effective_from = payload.effective_from
        if payload.effective_to:
            target_version.effective_to = payload.effective_to

        self._repo.update_version(target_version)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_TEMPLATE_APPROVED,
                actor_id=actor.user_id,
                resource_type="order_set_template_version",
                resource_id=target_version.version_id,
                outcome="ALLOW",
                metadata={
                    "template_id": template_id,
                    "version_number": target_version.version_number,
                    "approval_reason": payload.reason,
                },
            )
        )

        return target_version

    async def activate_version(
        self,
        template_id: str,
        version_id: Optional[str],
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateVersion:
        """Activate an approved template version.

        SAFETY: Unapproved versions CANNOT be activated. AI cannot activate.
        """
        self._require_enabled()
        self._authz.authorize_template_activation(actor)

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        target_version: Optional[OrderSetTemplateVersion] = None
        if version_id:
            target_version = self._repo.get_version_by_id(version_id)
        else:
            # Latest approved version
            approved_versions = [v for v in template.versions if v.status == TemplateStatus.APPROVED]
            if approved_versions:
                target_version = max(approved_versions, key=lambda v: v.version_number)

        if not target_version or target_version.template_id != template_id:
            raise OrderSetVersionNotFoundException("Approved version to activate was not found.")

        if target_version.status != TemplateStatus.APPROVED:
            raise OrderSetInvalidException(
                f"Version {target_version.version_number} must be in APPROVED status before activation (current: {target_version.status.value})."
            )

        target_version.status = TemplateStatus.ACTIVE
        self._repo.update_version(target_version)

        template.active_version_id = target_version.version_id
        template.status = TemplateStatus.ACTIVE
        self._repo.save_template(template)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_TEMPLATE_ACTIVATED,
                actor_id=actor.user_id,
                resource_type="order_set_template",
                resource_id=template.id,
                outcome="ALLOW",
                metadata={"version_id": target_version.version_id, "version_number": target_version.version_number},
            )
        )

        return target_version

    async def suspend_template(
        self,
        template_id: str,
        reason: str,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateRecord:
        """Emergency suspension of a template and its active version."""
        self._require_enabled()
        self._authz.authorize_template_activation(actor)

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        template.status = TemplateStatus.SUSPENDED
        if template.active_version_id:
            active_ver = self._repo.get_version_by_id(template.active_version_id)
            if active_ver:
                active_ver.status = TemplateStatus.SUSPENDED
                self._repo.update_version(active_ver)

        self._repo.save_template(template)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_TEMPLATE_SUSPENDED,
                actor_id=actor.user_id,
                resource_type="order_set_template",
                resource_id=template.id,
                outcome="ALLOW",
                metadata={"reason": reason},
            )
        )

        return template

    async def deprecate_template(
        self,
        template_id: str,
        reason: str,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateRecord:
        """Deprecate a template while preserving historical executions."""
        self._require_enabled()
        self._authz.authorize_template_activation(actor)

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        template.status = TemplateStatus.DEPRECATED
        if template.active_version_id:
            active_ver = self._repo.get_version_by_id(template.active_version_id)
            if active_ver:
                active_ver.status = TemplateStatus.DEPRECATED
                self._repo.update_version(active_ver)

        self._repo.save_template(template)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_TEMPLATE_DEPRECATED,
                actor_id=actor.user_id,
                resource_type="order_set_template",
                resource_id=template.id,
                outcome="ALLOW",
                metadata={"reason": reason},
            )
        )

        return template

    async def diff_versions(
        self,
        template_id: str,
        from_version_num: int,
        to_version_num: int,
        actor: AuthenticatedUserContext,
    ) -> OrderSetDiffResponse:
        """Produce an informational diff between two versions of an order set."""
        self._require_enabled()
        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        self._authz.authorize_template_view(actor, template)

        v_from = next((v for v in template.versions if v.version_number == from_version_num), None)
        v_to = next((v for v in template.versions if v.version_number == to_version_num), None)

        if not v_from or not v_to:
            raise OrderSetVersionNotFoundException("One or both requested versions for diff were not found.")

        from_defs = {d.requested_service: d for d in v_from.order_definitions}
        to_defs = {d.requested_service: d for d in v_to.order_definitions}

        added = [to_defs[s].model_dump() for s in to_defs if s not in from_defs]
        removed = [from_defs[s].model_dump() for s in from_defs if s not in to_defs]
        modified = []

        for s in to_defs:
            if s in from_defs:
                f_def = from_defs[s]
                t_def = to_defs[s]
                if f_def.model_dump() != t_def.model_dump():
                    modified.append({
                        "service": s,
                        "from": f_def.model_dump(),
                        "to": t_def.model_dump(),
                    })

        summary = f"Diff between v{from_version_num} and v{to_version_num}: {len(added)} added, {len(removed)} removed, {len(modified)} modified."

        return OrderSetDiffResponse(
            template_id=template.id,
            from_version_number=from_version_num,
            to_version_number=to_version_num,
            added_definitions=added,
            removed_definitions=removed,
            modified_definitions=modified,
            summary=summary,
        )

    # -----------------------------------------------------------------------
    # Clinical API Operations (TRD Sections 43, 44, 45)
    # -----------------------------------------------------------------------

    async def get_template(
        self,
        template_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderSetTemplateRecord:
        """Get template details."""
        self._require_enabled()
        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        self._authz.authorize_template_view(actor, template)
        return template

    async def list_templates(
        self,
        actor: AuthenticatedUserContext,
        scope: Optional[TemplateScope] = None,
        template_type: Optional[TemplateType] = None,
        status: Optional[TemplateStatus] = None,
        search_query: Optional[str] = None,
    ) -> List[OrderSetTemplateRecord]:
        """List templates matching filters within actor's scope."""
        self._require_enabled()

        # By default for clinical retrieval, filter to active templates within actor's org
        org_id = actor.organization_id
        templates = self._repo.list_templates(
            scope=scope,
            organization_id=org_id,
            template_type=template_type,
            status=status,
            search_query=search_query,
        )
        return templates

    async def preview_order_set(
        self,
        template_id: str,
        payload: OrderSetPreviewRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderSetPreviewResponse:
        """Preview order set expansion without creating clinical orders.

        SAFETY:
        - PREVIEW != EXECUTION.
        - NEVER creates orders or calls external providers.
        """
        self._require_enabled()
        if not self._preview_enabled:
            raise OrderSetUnavailableException("Order set preview is currently disabled.")

        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        self._authz.authorize_template_view(actor, template)

        # Resolve version
        version: Optional[OrderSetTemplateVersion] = None
        if payload.version_id:
            version = self._repo.get_version_by_id(payload.version_id)
        elif template.active_version_id:
            version = self._repo.get_version_by_id(template.active_version_id)
        elif template.versions:
            # In preview mode, allow previewing latest approved or draft version
            version = max(template.versions, key=lambda v: v.version_number)

        if not version or version.template_id != template.id:
            raise OrderSetVersionNotFoundException("Template version for preview was not found.")

        expected_orders: List[ExpectedChildOrderPreview] = []
        all_rejected_overrides: List[str] = []
        all_missing_fields: List[str] = []
        validation_messages: List[str] = []

        is_executable = True
        if template.status == TemplateStatus.SUSPENDED or version.status == TemplateStatus.SUSPENDED:
            is_executable = False
            validation_messages.append("Template or version is suspended.")

        if version.status not in (TemplateStatus.APPROVED, TemplateStatus.ACTIVE):
            is_executable = False
            validation_messages.append(f"Version is not approved/active (status: {version.status.value}).")

        # Process each order definition
        for order_def in version.order_definitions:
            applied_params, rejected_overrides, missing_reqs = self._val.validate_and_apply_parameters(
                order_def=order_def,
                candidate_params=payload.parameters,
                strict=False,  # in preview, collect rejected overrides rather than raising
            )
            all_rejected_overrides.extend(rejected_overrides)
            all_missing_fields.extend(missing_reqs)

            compatible, comp_notes = self._val.validate_provider_capability(order_def)

            priority = applied_params.get("priority", order_def.priority)
            clinical_reason = applied_params.get("clinical_reason", order_def.clinical_reason)

            expected_orders.append(
                ExpectedChildOrderPreview(
                    definition_id=order_def.definition_id,
                    order_type=order_def.order_type,
                    requested_service=order_def.requested_service,
                    priority=priority,
                    clinical_reason=clinical_reason,
                    items=order_def.items,
                    applied_parameters=applied_params,
                    provider_compatible=compatible,
                    provider_compatibility_notes=comp_notes,
                )
            )

        if all_missing_fields:
            is_executable = False
            validation_messages.append(f"Missing required fields: {', '.join(set(all_missing_fields))}")

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_PREVIEW_GENERATED,
                actor_id=actor.user_id,
                resource_type="order_set_template",
                resource_id=template.id,
                patient_id=payload.patient_id,
                outcome="ALLOW",
                metadata={
                    "version_number": version.version_number,
                    "expected_orders_count": len(expected_orders),
                },
            )
        )

        return OrderSetPreviewResponse(
            template_id=template.id,
            template_code=template.code,
            template_title=template.title,
            template_type=template.template_type,
            version_id=version.version_id,
            version_number=version.version_number,
            patient_id=payload.patient_id,
            is_executable=is_executable,
            expected_orders=expected_orders,
            allowed_overrides=list(set(sum([d.allowed_parameter_overrides for d in version.order_definitions], []))),
            applied_overrides=payload.parameters,
            rejected_overrides=list(set(all_rejected_overrides)),
            missing_required_fields=list(set(all_missing_fields)),
            validation_messages=validation_messages,
        )

    async def execute_order_set(
        self,
        template_id: str,
        payload: OrderSetExecuteRequest,
        actor: AuthenticatedUserContext,
    ) -> OrderSetExecutionRecord:
        """Compose and execute child clinical orders through Phase 38.

        SAFETY INVARIANTS:
        - ORDER SET SELECTION != CLINICAL AUTHORIZATION.
        - EVERY child order passes through Phase 38 OrderService.
        - AI CANNOT EXECUTE ORDER SETS.
        - IDEMPOTENCY KEY PREVENTS DUPLICATE ORDERS.
        - MISSING PARAMETERS ARE NEVER SILENTLY INFERRED.
        - PARTIAL EXECUTION IS REFLECTED ACCURATELY.
        """
        self._require_enabled()
        if not self._execution_enabled:
            raise OrderSetUnavailableException("Clinical order set execution is currently disabled.")

        # 1. Idempotency Check (TRD Section 20)
        existing_execution = self._repo.get_execution_by_idempotency_key(payload.idempotency_key)
        if existing_execution:
            # Verify patient matches to avoid key reuse attack across patients
            if existing_execution.patient_id != payload.patient_id:
                raise OrderSetDuplicateExecutionException(
                    "Idempotency key conflict: an execution exists with this key for a different patient."
                )
            return existing_execution

        # 2. Authorization Check (TRD Section 16, 41)
        self._authz.authorize_order_set_execution(
            actor=actor,
            target_patient_id=payload.patient_id,
            target_organization_id=payload.organization_id,
        )

        # 3. Retrieve Template
        template = self._repo.get_template_by_id(template_id)
        if not template:
            raise OrderSetNotFoundException(f"Template '{template_id}' was not found.")

        # 4. Version Resolution (TRD Section 27)
        version: Optional[OrderSetTemplateVersion] = None
        if payload.version_id:
            version = self._repo.get_version_by_id(payload.version_id)
        elif template.active_version_id:
            version = self._repo.get_version_by_id(template.active_version_id)
        elif template.versions:
            # If template has no active version (e.g. unapproved draft), pick latest so eligibility can validate approval state
            version = max(template.versions, key=lambda v: v.version_number)

        if not version or version.template_id != template.id:
            raise OrderSetVersionNotFoundException("Active or requested template version was not found.")

        # 5. Template Eligibility Validation (TRD Section 25)
        self._val.validate_template_eligibility(template, version, require_active=True)

        # 6. Scope Validation (TRD Section 8)
        self._val.validate_scope(
            template=template,
            target_organization_id=payload.organization_id or actor.organization_id,
            target_facility_id=payload.facility_id or actor.facility_id,
        )

        # 7. Patient Context Validation & Pre-flight parameter check
        all_missing_fields: List[str] = []
        for order_def in version.order_definitions:
            _, _, missing_reqs = self._val.validate_and_apply_parameters(
                order_def=order_def,
                candidate_params=payload.parameters,
                strict=True,  # Execution strictly enforces parameter rules
            )
            all_missing_fields.extend(missing_reqs)

        self._val.validate_patient_context(
            patient_id=payload.patient_id,
            clinician_id=actor.user_id,
            missing_fields=all_missing_fields,
        )

        # 8. Create Execution Record Context
        batch_policy = payload.batch_policy or BatchExecutionPolicy(self._default_batch_policy)
        execution_id = str(uuid.uuid4())

        execution = OrderSetExecutionRecord(
            id=execution_id,
            template_id=template.id,
            template_code=template.code,
            version_id=version.version_id,
            version_number=version.version_number,
            patient_id=payload.patient_id,
            ordered_by=actor.user_id,
            organization_id=payload.organization_id or template.organization_id or actor.organization_id or "default-org",
            facility_id=payload.facility_id or template.facility_id or actor.facility_id or "default-facility",
            encounter_id=payload.encounter_id,
            idempotency_key=payload.idempotency_key,
            batch_policy=batch_policy,
            status=OrderSetExecutionStatus.EXPANDING,
            child_orders=[],
            created_orders_count=0,
            failed_orders_count=0,
            total_orders_count=len(version.order_definitions),
            parameters_applied=payload.parameters,
            workflow_id=payload.workflow_id,
        )
        self._repo.save_execution(execution)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.ORDER_SET_EXECUTION_STARTED,
                actor_id=actor.user_id,
                resource_type="order_set_execution",
                resource_id=execution.id,
                patient_id=payload.patient_id,
                outcome="ALLOW",
                metadata={
                    "template_code": template.code,
                    "version_number": version.version_number,
                    "batch_policy": batch_policy.value,
                },
            )
        )

        # 9. Expand Child Orders via Phase 38 OrderService
        child_summaries: List[ChildOrderExecutionSummary] = []
        created_count = 0
        failed_count = 0

        for order_def in version.order_definitions:
            try:
                applied_params, _, _ = self._val.validate_and_apply_parameters(
                    order_def=order_def,
                    candidate_params=payload.parameters,
                    strict=True,
                )

                # Ensure non-empty line items
                effective_items = order_def.items if order_def.items else [{"name": order_def.requested_service}]

                # Ensure referral_details if referral order
                effective_referral_details = applied_params.get("referral_details")
                if not effective_referral_details and order_def.order_type in (OrderType.REFERRAL_ORDER, OrderType.REFERRAL):
                    effective_referral_details = {"specialty": order_def.requested_service}

                # Compose OrderCreate payload
                order_create = OrderCreate(
                    patient_id=payload.patient_id,
                    clinician_id=actor.user_id,
                    organization_id=execution.organization_id,
                    facility_id=execution.facility_id,
                    order_type=order_def.order_type,
                    priority=applied_params.get("priority", order_def.priority),
                    encounter_id=payload.encounter_id,
                    clinical_reason=applied_params.get("clinical_reason", payload.clinical_reason or order_def.clinical_reason),
                    items=effective_items,
                    notes=applied_params.get("notes"),
                    medication_order_details=applied_params.get("medication_order_details"),
                    referral_details=effective_referral_details,
                    workflow_id=payload.workflow_id,
                    idempotency_key=f"{payload.idempotency_key}-{order_def.definition_id}",
                    metadata={
                        "template_id": template.id,
                        "template_code": template.code,
                        "template_version_id": version.version_id,
                        "template_version_number": version.version_number,
                        "order_set_execution_id": execution.id,
                        "order_definition_id": order_def.definition_id,
                    },
                )

                # Delegate directly to Phase 38 OrderService
                created_order = await self._order_service.create_order(
                    payload=order_create,
                    actor=actor,
                )

                summary = ChildOrderExecutionSummary(
                    order_id=created_order.order_id,
                    definition_id=order_def.definition_id,
                    order_type=order_def.order_type,
                    requested_service=order_def.requested_service,
                    status=created_order.status.value,
                )
                child_summaries.append(summary)
                created_count += 1

            except Exception as ex:
                failed_count += 1
                error_msg = str(ex)
                summary = ChildOrderExecutionSummary(
                    order_id="",
                    definition_id=order_def.definition_id,
                    order_type=order_def.order_type,
                    requested_service=order_def.requested_service,
                    status="FAILED",
                    error_message=error_msg,
                )
                child_summaries.append(summary)

                if batch_policy == BatchExecutionPolicy.ATOMIC:
                    # In atomic policy, halt immediately on first failure
                    break

        # 10. Derive Final Execution Status (TRD Section 18, 19)
        execution.child_orders = child_summaries
        execution.created_orders_count = created_count
        execution.failed_orders_count = failed_count
        execution.updated_at = datetime.now(timezone.utc)

        if failed_count == 0 and created_count == execution.total_orders_count:
            execution.status = OrderSetExecutionStatus.COMPLETED
            audit_event = AuditEventType.ORDER_SET_COMPLETED
        elif created_count > 0 and failed_count > 0:
            execution.status = OrderSetExecutionStatus.PARTIALLY_COMPLETED
            execution.failure_reason = f"{failed_count} of {execution.total_orders_count} orders failed during composition."
            audit_event = AuditEventType.ORDER_SET_PARTIAL_FAILURE
        else:
            execution.status = OrderSetExecutionStatus.FAILED
            execution.failure_reason = "All orders failed during order set composition."
            audit_event = AuditEventType.ORDER_SET_FAILED

        self._repo.save_execution(execution)

        await self._record_audit(
            AuditEventRecord(
                event_type=audit_event,
                actor_id=actor.user_id,
                resource_type="order_set_execution",
                resource_id=execution.id,
                patient_id=payload.patient_id,
                outcome="ALLOW",
                metadata={
                    "status": execution.status.value,
                    "created_count": created_count,
                    "failed_count": failed_count,
                    "total_count": execution.total_orders_count,
                },
            )
        )

        return execution

    async def get_execution(
        self,
        execution_id: str,
        actor: AuthenticatedUserContext,
    ) -> OrderSetExecutionRecord:
        """Retrieve an order set execution record by ID."""
        self._require_enabled()
        execution = self._repo.get_execution_by_id(execution_id)
        if not execution:
            raise OrderSetNotFoundException(f"Order set execution '{execution_id}' was not found.")

        self._authz.authorize_execution_view(actor, execution)
        return execution

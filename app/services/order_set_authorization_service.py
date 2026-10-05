"""Clinical Order Set Authorization Service (Phase 39).

Enforces role-based access control, tenant isolation, and strict AI safety boundaries
for clinical order sets and protocol templates.

CRITICAL SAFETY INVARIANTS:
- AI CANNOT APPROVE A TEMPLATE.
- AI CANNOT ACTIVATE A TEMPLATE.
- AI CANNOT INDEPENDENTLY EXECUTE AN ORDER SET.
- AI CANNOT PRESCRIBE THROUGH AN ORDER SET.
- AI CANNOT MODIFY MEDICATION TREATMENT.
- CROSS-PATIENT ACCESS IS REJECTED.
- CROSS-ORGANIZATION ACCESS IS REJECTED.
"""

from __future__ import annotations

from typing import Optional

from app.core.exceptions import (
    OrderSetAuthorizationRequiredException,
    OrderSetForbiddenException,
    OrderSetUnauthorizedException,
)
from app.schemas.auth import UserRole
from app.schemas.order_set import OrderSetTemplateRecord, TemplateScope
from app.schemas.order_set_execution import OrderSetExecutionRecord
from app.schemas.user import AuthenticatedUserContext

# Roles permitted to administer templates (create, edit, add version)
TEMPLATE_ADMIN_ROLES = frozenset({
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
    UserRole.DOCTOR,
})

# Roles permitted to clinically approve and activate templates
TEMPLATE_APPROVAL_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
})

# Roles permitted to execute order sets (human clinicians)
ORDER_SET_EXECUTION_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
})

# Roles permitted to view or preview templates
TEMPLATE_VIEW_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
    UserRole.SUPPORT_OPERATOR,
    UserRole.AUDIT_OPERATOR,
})


class OrderSetAuthorizationService:
    """Enforces authorization boundaries and AI safety restrictions for Order Sets."""

    def _check_ai_actor(self, actor: AuthenticatedUserContext) -> None:
        """Reject any autonomous AI actor attempting clinical authorization or execution."""
        # Check explicit is_ai flag or role representation
        if getattr(actor, "is_ai", False):
            raise OrderSetAuthorizationRequiredException(
                message="Autonomous AI actor cannot approve, activate, or execute clinical order sets. Human clinician authorization is required."
            )
        role_str = str(actor.role).upper()
        if "AI" in role_str or role_str == "BOT" or role_str == "ASSISTANT":
            raise OrderSetAuthorizationRequiredException(
                message="AI actor cannot approve, activate, or execute clinical order sets. Human clinician authorization is required."
            )

    def authorize_template_administration(self, actor: AuthenticatedUserContext) -> None:
        """Authorize template creation, modification, or version addition."""
        self._check_ai_actor(actor)
        if actor.role not in TEMPLATE_ADMIN_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to administer order set templates."
            )

    def authorize_template_approval(self, actor: AuthenticatedUserContext) -> None:
        """Authorize clinical approval of a template version."""
        self._check_ai_actor(actor)
        if actor.role not in TEMPLATE_APPROVAL_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to approve clinical order set templates."
            )

    def authorize_template_activation(self, actor: AuthenticatedUserContext) -> None:
        """Authorize activation or suspension of a template version."""
        self._check_ai_actor(actor)
        if actor.role not in TEMPLATE_APPROVAL_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to activate or suspend clinical order set templates."
            )

    def authorize_order_set_execution(
        self,
        actor: AuthenticatedUserContext,
        target_patient_id: str,
        target_organization_id: Optional[str] = None,
    ) -> None:
        """Authorize human clinician execution of an order set for a patient.

        SAFETY:
        - AI cannot execute order sets.
        - Actor must possess clinical role.
        - Cross-organization barriers enforced.
        """
        self._check_ai_actor(actor)

        if actor.role not in ORDER_SET_EXECUTION_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to execute clinical order sets. Only authorized clinicians may execute order sets."
            )

        # Organization isolation
        if actor.organization_id and target_organization_id:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                if actor.organization_id != target_organization_id:
                    raise OrderSetForbiddenException(
                        message=f"Cross-organization execution denied: actor belongs to '{actor.organization_id}', target is '{target_organization_id}'."
                    )

    def authorize_template_view(
        self,
        actor: AuthenticatedUserContext,
        template: OrderSetTemplateRecord,
    ) -> None:
        """Authorize viewing of a template or its versions."""
        if actor.role not in TEMPLATE_VIEW_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to view order set templates."
            )

        # If template is organization-scoped, check tenant matching
        if template.scope == TemplateScope.ORGANIZATION and template.organization_id:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                if actor.organization_id and actor.organization_id != template.organization_id:
                    raise OrderSetForbiddenException(
                        message="Access denied to order set template belonging to another organization."
                    )

    def authorize_execution_view(
        self,
        actor: AuthenticatedUserContext,
        execution: OrderSetExecutionRecord,
    ) -> None:
        """Authorize viewing an order set execution record."""
        # Patient can only view their own execution
        if actor.role == UserRole.PATIENT:
            if actor.patient_id and actor.patient_id != execution.patient_id:
                raise OrderSetForbiddenException(
                    message="Patients may only view their own order set executions."
                )
            return

        if actor.role not in TEMPLATE_VIEW_ROLES and actor.role not in ORDER_SET_EXECUTION_ROLES:
            raise OrderSetForbiddenException(
                message=f"Role '{actor.role}' is not authorized to view order set executions."
            )

        # Cross-organization view isolation
        if actor.organization_id and execution.organization_id:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                if actor.organization_id != execution.organization_id:
                    raise OrderSetForbiddenException(
                        message="Cross-organization access to order set execution denied."
                    )

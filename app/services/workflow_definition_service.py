"""Catalog and validation service for versioned Workflow Definitions (Phase 37).

Enforces:
- Workflow definitions are backend-controlled, versioned configuration.
- Ordinary API clients cannot inject arbitrary executable workflow code.
- Clinical workflow definitions default to disabled unless explicitly enabled.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.core.exceptions import (
    WorkflowDefinitionDisabledException,
    WorkflowDefinitionNotFoundException,
    WorkflowVersionInvalidException,
)
from app.schemas.workflow import (
    WorkflowCategory,
    WorkflowDefinition,
    WorkflowTriggerType,
)
from app.schemas.workflow_step import (
    WorkflowStepActionType,
    WorkflowStepDefinition,
    WorkflowStepDependency,
)


class WorkflowDefinitionService:
    """Service managing approved, versioned workflow templates."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Key: (definition_id, version) -> WorkflowDefinition
        self._definitions: Dict[tuple[str, str], WorkflowDefinition] = {}
        # Key: definition_id -> latest version string
        self._latest_versions: Dict[str, str] = {}
        self._load_standard_templates()

    def _load_standard_templates(self) -> None:
        """Initialize standard HealthSetu clinical & operational workflow templates."""

        # 1. DIAGNOSTIC_REVIEW_WORKFLOW
        diag_def = WorkflowDefinition(
            definition_id="diagnostic_review",
            version="1.0",
            name="Critical Diagnostic Result Review Workflow",
            description="Coordinates clinician review and verification for critical diagnostic results.",
            category=WorkflowCategory.DIAGNOSTIC,
            enabled=True,
            trigger_type=WorkflowTriggerType.DIAGNOSTIC_RESULT,
            timeout_minutes=1440,
            escalation_enabled=True,
            steps=[
                WorkflowStepDefinition(
                    step_id="step_create_review_task",
                    name="Create Diagnostic Review Task",
                    description="Generates an authoritative Phase 36 task for assigned clinician.",
                    order=1,
                    action_type=WorkflowStepActionType.CREATE_TASK,
                    action_config={
                        "task_title": "Review Critical Diagnostic Result",
                        "task_category": "DIAGNOSTIC_REVIEW_TASK",
                        "priority": "URGENT",
                    },
                    approval_required=False,
                ),
                WorkflowStepDefinition(
                    step_id="step_clinician_approval",
                    name="Authorized Clinician Review Gate",
                    description="Clinician explicitly reviews and approves the diagnostic findings.",
                    order=2,
                    action_type=WorkflowStepActionType.HUMAN_APPROVAL,
                    action_config={"gate": "CLINICAL_VERIFICATION"},
                    approval_required=True,
                    required_approval_role="DOCTOR",
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_create_review_task")
                    ],
                ),
                WorkflowStepDefinition(
                    step_id="step_close_verification",
                    name="Workflow Verification & Completion",
                    description="Finalizes workflow records after clinician verification.",
                    order=3,
                    action_type=WorkflowStepActionType.DOMAIN_ACTION,
                    action_config={"action": "VERIFY_REVIEW_AUDIT"},
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_clinician_approval")
                    ],
                ),
            ],
        )
        self.register_definition(diag_def)

        # 2. MEDICATION_SAFETY_REVIEW_WORKFLOW
        med_def = WorkflowDefinition(
            definition_id="medication_safety_review",
            version="1.0",
            name="Medication Safety & Reconciliation Review",
            description="Coordinates document extraction, safety evaluation, and clinician review.",
            category=WorkflowCategory.MEDICATION,
            enabled=True,
            trigger_type=WorkflowTriggerType.MEDICATION_SAFETY,
            timeout_minutes=2880,
            escalation_enabled=True,
            steps=[
                WorkflowStepDefinition(
                    step_id="step_document_extraction",
                    name="Prescription Document Processing",
                    description="Deterministic structured text extraction from prescription document.",
                    order=1,
                    action_type=WorkflowStepActionType.REQUEST_DOCUMENT_PROCESSING,
                    action_config={"pipeline": "PRESCRIPTION_PARSER"},
                ),
                WorkflowStepDefinition(
                    step_id="step_medication_normalization",
                    name="Medication Concept Normalization",
                    description="Normalizes candidate medications against national formulary / RxNorm.",
                    order=2,
                    action_type=WorkflowStepActionType.REQUEST_NORMALIZATION,
                    action_config={"target": "RXNORM"},
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_document_extraction")
                    ],
                ),
                WorkflowStepDefinition(
                    step_id="step_medication_review_task",
                    name="Create Pharmacist/Doctor Review Task",
                    description="Generates Phase 36 medication review task for verification.",
                    order=3,
                    action_type=WorkflowStepActionType.CREATE_TASK,
                    action_config={
                        "task_title": "Medication Safety Review",
                        "task_category": "MEDICATION_REVIEW_TASK",
                        "priority": "HIGH",
                    },
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_medication_normalization")
                    ],
                ),
                WorkflowStepDefinition(
                    step_id="step_clinical_approval",
                    name="Clinician Verification Gate",
                    description="Authorized clinician verifies normalized medication order.",
                    order=4,
                    action_type=WorkflowStepActionType.HUMAN_APPROVAL,
                    action_config={"gate": "MEDICATION_ORDER_REVIEW"},
                    approval_required=True,
                    required_approval_role="DOCTOR",
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_medication_review_task")
                    ],
                ),
            ],
        )
        self.register_definition(med_def)

        # 3. DISCHARGE_FOLLOW_UP_WORKFLOW
        dis_def = WorkflowDefinition(
            definition_id="discharge_follow_up",
            version="1.0",
            name="Patient Discharge & Follow-up Coordination",
            description="Coordinates discharge documentation validation, follow-up task, and notification.",
            category=WorkflowCategory.DISCHARGE,
            enabled=True,
            trigger_type=WorkflowTriggerType.DISCHARGE_EVENT,
            timeout_minutes=4320,
            escalation_enabled=False,
            steps=[
                WorkflowStepDefinition(
                    step_id="step_validate_discharge_summary",
                    name="Validate Discharge Summary",
                    description="Validates structured discharge summary existence.",
                    order=1,
                    action_type=WorkflowStepActionType.REQUEST_DOCUMENT_PROCESSING,
                    action_config={"validation_type": "DISCHARGE_SUMMARY_CHECK"},
                ),
                WorkflowStepDefinition(
                    step_id="step_create_followup_task",
                    name="Create Discharge Follow-up Task",
                    description="Generates Phase 36 task for outpatient follow-up call.",
                    order=2,
                    action_type=WorkflowStepActionType.CREATE_TASK,
                    action_config={
                        "task_title": "Discharge Follow-Up Contact",
                        "task_category": "DISCHARGE_FOLLOW_UP_TASK",
                        "priority": "NORMAL",
                    },
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_validate_discharge_summary")
                    ],
                ),
                WorkflowStepDefinition(
                    step_id="step_send_patient_instructions",
                    name="Send Discharge Care Notification",
                    description="Delivers post-discharge instructions to patient via Notification Service.",
                    order=3,
                    action_type=WorkflowStepActionType.SEND_NOTIFICATION,
                    action_config={"channel": "SMS_EMAIL", "template": "DISCHARGE_CARE_PLAN"},
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_create_followup_task")
                    ],
                ),
            ],
        )
        self.register_definition(dis_def)

        # 4. TRANSFER_COORDINATION_WORKFLOW
        trans_def = WorkflowDefinition(
            definition_id="transfer_coordination",
            version="1.0",
            name="Inter-Facility Transfer Coordination",
            description="Coordinates transfer request, receiving facility acceptance event, and task closure.",
            category=WorkflowCategory.TRANSFER,
            enabled=True,
            trigger_type=WorkflowTriggerType.TRANSFER_EVENT,
            timeout_minutes=2880,
            escalation_enabled=True,
            steps=[
                WorkflowStepDefinition(
                    step_id="step_create_transfer_task",
                    name="Create Facility Transfer Task",
                    description="Generates coordination task for transfer desk.",
                    order=1,
                    action_type=WorkflowStepActionType.CREATE_TASK,
                    action_config={
                        "task_title": "Coordinate Inter-Facility Transfer",
                        "task_category": "TRANSFER_TASK",
                        "priority": "HIGH",
                    },
                ),
                WorkflowStepDefinition(
                    step_id="step_wait_transfer_acceptance",
                    name="Wait for Receiving Facility Acceptance",
                    description="Pauses progression until authoritative TRANSFER_ACCEPTED domain event is emitted.",
                    order=2,
                    action_type=WorkflowStepActionType.WAIT_FOR_EVENT,
                    action_config={"event_name": "TRANSFER_ACCEPTED"},
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_create_transfer_task")
                    ],
                ),
                WorkflowStepDefinition(
                    step_id="step_notify_transfer_confirmed",
                    name="Notify Transfer Acceptance",
                    description="Dispatches notification to clinical teams that transfer was accepted.",
                    order=3,
                    action_type=WorkflowStepActionType.SEND_NOTIFICATION,
                    action_config={"channel": "IN_APP", "template": "TRANSFER_ACCEPTED"},
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_wait_transfer_acceptance")
                    ],
                ),
            ],
        )
        self.register_definition(trans_def)

        # 5. DOCUMENT_PROCESSING_WORKFLOW
        doc_def = WorkflowDefinition(
            definition_id="document_processing",
            version="1.0",
            name="Clinical Document Ingestion & Verification",
            description="Coordinates OCR ingestion, extraction, and verification task.",
            category=WorkflowCategory.DOCUMENT_PROCESSING,
            enabled=True,
            trigger_type=WorkflowTriggerType.DOMAIN_EVENT,
            timeout_minutes=1440,
            steps=[
                WorkflowStepDefinition(
                    step_id="step_ocr_extraction",
                    name="Document OCR Processing",
                    description="Performs OCR and document structure analysis.",
                    order=1,
                    action_type=WorkflowStepActionType.REQUEST_DOCUMENT_PROCESSING,
                    action_config={"operation": "OCR_PARSE"},
                ),
                WorkflowStepDefinition(
                    step_id="step_create_doc_review_task",
                    name="Create Document Verification Task",
                    description="Generates Phase 36 task for review.",
                    order=2,
                    action_type=WorkflowStepActionType.CREATE_TASK,
                    action_config={
                        "task_title": "Verify Ingested Document",
                        "task_category": "DOCUMENT_REVIEW_TASK",
                        "priority": "NORMAL",
                    },
                    dependencies=[
                        WorkflowStepDependency(depends_on_step_id="step_ocr_extraction")
                    ],
                ),
            ],
        )
        self.register_definition(doc_def)

    def register_definition(self, definition: WorkflowDefinition) -> None:
        """Register or update an approved workflow definition."""
        with self._lock:
            key = (definition.definition_id, definition.version)
            self._definitions[key] = definition
            # Track latest version
            self._latest_versions[definition.definition_id] = definition.version

    def get_definition(
        self, definition_id: str, version: Optional[str] = None
    ) -> WorkflowDefinition:
        """Retrieve approved workflow definition, verifying existence and enabled status."""
        with self._lock:
            if not version:
                version = self._latest_versions.get(definition_id)
                if not version:
                    raise WorkflowDefinitionNotFoundException(
                        f"Workflow definition '{definition_id}' not found."
                    )

            key = (definition_id, version)
            definition = self._definitions.get(key)
            if not definition:
                raise WorkflowDefinitionNotFoundException(
                    f"Workflow definition '{definition_id}' version '{version}' not found."
                )

            if not definition.enabled:
                raise WorkflowDefinitionDisabledException(
                    f"Workflow definition '{definition_id}' is disabled."
                )

            return definition

    def list_definitions(self) -> List[WorkflowDefinition]:
        """List all active workflow definitions."""
        with self._lock:
            return list(self._definitions.values())

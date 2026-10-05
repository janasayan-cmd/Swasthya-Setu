"""HealthSetu Phase 42 - Patient Action Repository.

Thread-safe storage and indexing for action definitions, action instances,
submissions, document links, idempotency keys, and state transition histories.

DATABASE TEAMMATE BOUNDARY:
- The database teammate owns tables, constraints, foreign keys, and indexes.
- This repository interfaces in-memory or with database contracts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.patient_action import (
    ActionDefinitionRecord,
    ActionPriority,
    ActionStatus,
    ActionType,
    PatientActionHistoryRecord,
    PatientActionRecord,
)
from app.schemas.patient_submission import (
    DocumentSubmissionRecord,
    PatientSubmissionRecord,
)


class PatientActionRepository:
    """Thread-safe repository for patient self-service actions and submissions."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._definitions: Dict[str, ActionDefinitionRecord] = {}
        self._actions: Dict[str, PatientActionRecord] = {}
        self._patient_actions: Dict[str, List[str]] = {}  # patient_id -> [action_id]
        self._submissions: Dict[str, PatientSubmissionRecord] = {}
        self._action_submissions: Dict[str, List[str]] = {}  # action_id -> [submission_id]
        self._document_submissions: Dict[str, List[DocumentSubmissionRecord]] = {}  # action_id -> [doc]
        self._history: Dict[str, List[PatientActionHistoryRecord]] = {}  # action_id -> [history]
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> submission_id
        self._seed_default_definitions()

    def _seed_default_definitions(self) -> None:
        """Seed standard operational action definitions."""
        d1 = ActionDefinitionRecord(
            id="def_appt_confirm",
            code="APPOINTMENT_CONFIRMATION",
            title="Confirm Upcoming Clinical Appointment",
            description="Operational confirmation that patient plans to attend scheduled appointment.",
            action_type=ActionType.APPOINTMENT_CONFIRMATION,
            default_expiration_hours=48,
            requires_consent=False,
        )
        self._definitions[d1.id] = d1

        d2 = ActionDefinitionRecord(
            id="def_general_intake",
            code="GENERAL_INTAKE",
            title="Complete Pre-Visit Intake Questionnaire",
            description="Non-clinical administrative check-in prior to your consultation.",
            action_type=ActionType.QUESTIONNAIRE,
            default_expiration_hours=72,
            questionnaire_id="qst_general_intake",
        )
        self._definitions[d2.id] = d2

        d3 = ActionDefinitionRecord(
            id="def_doc_upload",
            code="REQUESTED_DOCUMENT_UPLOAD",
            title="Upload Requested Health Document or ID",
            description="Submit document requested by your care coordinator or clinic.",
            action_type=ActionType.DOCUMENT_SUBMISSION,
            default_expiration_hours=120,
        )
        self._definitions[d3.id] = d3

        d4 = ActionDefinitionRecord(
            id="def_care_plan_ack",
            code="CARE_PLAN_RECEIPT_ACKNOWLEDGEMENT",
            title="Acknowledge Receipt of Discharge / Care Plan",
            description="Confirm you have received and accessed your written care instructions.",
            action_type=ActionType.CARE_PLAN_ACKNOWLEDGEMENT,
            default_expiration_hours=168,
        )
        self._definitions[d4.id] = d4

    # Action Definition Methods
    async def get_definition_by_id(self, definition_id: str) -> Optional[ActionDefinitionRecord]:
        """Retrieve action definition by ID."""
        async with self._lock:
            return self._definitions.get(definition_id)

    async def get_definition_by_code(self, code: str) -> Optional[ActionDefinitionRecord]:
        """Retrieve action definition by code."""
        async with self._lock:
            for d in self._definitions.values():
                if d.code == code and d.is_active:
                    return d
            return None

    async def save_definition(self, definition: ActionDefinitionRecord) -> ActionDefinitionRecord:
        """Save an action definition."""
        async with self._lock:
            self._definitions[definition.id] = definition
            return definition

    # Action Instance Methods
    async def get_action_by_id(self, action_id: str) -> Optional[PatientActionRecord]:
        """Retrieve patient action by ID."""
        async with self._lock:
            return self._actions.get(action_id)

    async def save_action(self, action: PatientActionRecord) -> PatientActionRecord:
        """Create or update a patient action instance."""
        async with self._lock:
            self._actions[action.id] = action
            if action.patient_id not in self._patient_actions:
                self._patient_actions[action.patient_id] = []
            if action.id not in self._patient_actions[action.patient_id]:
                self._patient_actions[action.patient_id].append(action.id)
            return action

    async def list_actions_by_patient(
        self,
        patient_id: str,
        status: Optional[ActionStatus] = None,
        action_type: Optional[ActionType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PatientActionRecord], int]:
        """List paginated actions for a specific patient."""
        async with self._lock:
            action_ids = self._patient_actions.get(patient_id, [])
            items = [self._actions[aid] for aid in action_ids if aid in self._actions]

            if status:
                items = [a for a in items if a.status == status]
            if action_type:
                items = [a for a in items if a.action_type == action_type]

            # Sort descending by created_at
            items.sort(key=lambda x: x.created_at, reverse=True)

            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            return items[start:end], total

    async def list_actions_admin(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        status: Optional[ActionStatus] = None,
        action_type: Optional[ActionType] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PatientActionRecord], int]:
        """List paginated actions with administrative/clinician filtering."""
        async with self._lock:
            items = list(self._actions.values())

            if organization_id:
                items = [a for a in items if a.organization_id == organization_id]
            if facility_id:
                items = [a for a in items if a.facility_id == facility_id]
            if status:
                items = [a for a in items if a.status == status]
            if action_type:
                items = [a for a in items if a.action_type == action_type]

            items.sort(key=lambda x: x.created_at, reverse=True)
            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            return items[start:end], total

    # Submission & Correction Methods
    async def save_submission(self, submission: PatientSubmissionRecord) -> PatientSubmissionRecord:
        """Persist a patient submission or correction."""
        async with self._lock:
            self._submissions[submission.id] = submission
            if submission.action_id not in self._action_submissions:
                self._action_submissions[submission.action_id] = []
            self._action_submissions[submission.action_id].append(submission.id)

            if submission.idempotency_key:
                self._idempotency_index[submission.idempotency_key] = submission.id
            return submission

    async def get_submission_by_idempotency_key(self, idempotency_key: str) -> Optional[PatientSubmissionRecord]:
        """Look up existing submission by idempotency key."""
        async with self._lock:
            sub_id = self._idempotency_index.get(idempotency_key)
            if sub_id:
                return self._submissions.get(sub_id)
            return None

    async def get_submissions_by_action(self, action_id: str) -> List[PatientSubmissionRecord]:
        """Retrieve all submissions/corrections for an action in chronological order."""
        async with self._lock:
            sub_ids = self._action_submissions.get(action_id, [])
            subs = [self._submissions[sid] for sid in sub_ids if sid in self._submissions]
            subs.sort(key=lambda x: x.submission_version)
            return subs

    async def get_latest_submission(self, action_id: str) -> Optional[PatientSubmissionRecord]:
        """Retrieve the most recent submission/correction for an action."""
        subs = await self.get_submissions_by_action(action_id)
        return subs[-1] if subs else None

    # Document Links Methods
    async def save_document_submission(self, doc_record: DocumentSubmissionRecord) -> DocumentSubmissionRecord:
        """Link a document to a patient action."""
        async with self._lock:
            if doc_record.action_id not in self._document_submissions:
                self._document_submissions[doc_record.action_id] = []
            self._document_submissions[doc_record.action_id].append(doc_record)
            return doc_record

    async def get_documents_by_action(self, action_id: str) -> List[DocumentSubmissionRecord]:
        """Get all documents submitted/linked for an action."""
        async with self._lock:
            return list(self._document_submissions.get(action_id, []))

    # History Methods
    async def add_history_entry(self, entry: PatientActionHistoryRecord) -> PatientActionHistoryRecord:
        """Append a state transition history entry."""
        async with self._lock:
            if entry.action_id not in self._history:
                self._history[entry.action_id] = []
            self._history[entry.action_id].append(entry)
            return entry

    async def get_history_by_action(self, action_id: str) -> List[PatientActionHistoryRecord]:
        """Retrieve complete transition history for an action."""
        async with self._lock:
            return list(self._history.get(action_id, []))

    # Operational Sweep
    async def sweep_expired_actions(self) -> List[PatientActionRecord]:
        """Find actions that have passed expiration and transition them to EXPIRED."""
        now = datetime.now(timezone.utc)
        expired_actions: List[PatientActionRecord] = []
        async with self._lock:
            for action in self._actions.values():
                if (
                    action.status in (ActionStatus.CREATED, ActionStatus.AVAILABLE, ActionStatus.STARTED)
                    and action.expires_at is not None
                    and action.expires_at < now
                ):
                    action.status = ActionStatus.EXPIRED
                    expired_actions.append(action)
                    # Add history
                    entry = PatientActionHistoryRecord(
                        action_id=action.id,
                        from_status=ActionStatus.AVAILABLE,
                        to_status=ActionStatus.EXPIRED,
                        actor_id="system:expiration_worker",
                        actor_role="SYSTEM",
                        reason="Action passed configured expiration horizon without submission.",
                    )
                    if action.id not in self._history:
                        self._history[action.id] = []
                    self._history[action.id].append(entry)
        return expired_actions

    async def clear(self) -> None:
        """Clear action instances (for tests). Preserves definitions."""
        async with self._lock:
            self._actions.clear()
            self._patient_actions.clear()
            self._submissions.clear()
            self._action_submissions.clear()
            self._document_submissions.clear()
            self._history.clear()
            self._idempotency_index.clear()

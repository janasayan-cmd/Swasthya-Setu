"""HealthSetu Phase 42 - Questionnaire Repository.

Thread-safe storage and indexing for non-clinical questionnaire templates
and patient responses.

DATABASE TEAMMATE BOUNDARY:
- The database teammate owns database tables, foreign keys, and indexes.
- This repository interfaces in-memory or with SQLAlchemy session when available.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.questionnaire import (
    QuestionItem,
    QuestionType,
    QuestionnaireDefinition,
    QuestionnaireResponseRecord,
)


class QuestionnaireRepository:
    """Thread-safe repository for questionnaires and patient answers."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._questionnaires: Dict[str, QuestionnaireDefinition] = {}
        self._responses: Dict[str, QuestionnaireResponseRecord] = {}
        self._action_responses: Dict[str, List[str]] = {}  # action_id -> [response_id]
        self._seed_default_questionnaires()

    def _seed_default_questionnaires(self) -> None:
        """Seed standard default non-clinical questionnaires."""
        # Standard General Intake Questionnaire
        q1 = QuestionnaireDefinition(
            id="qst_general_intake",
            code="GENERAL_INTAKE_V1",
            title="General Pre-Visit Intake Questionnaire",
            description="Non-clinical administrative check-in questions prior to consultation.",
            version="1.0.0",
            is_active=True,
            questions=[
                QuestionItem(
                    id="q_visit_reason",
                    text="What is the primary reason for your visit?",
                    question_type=QuestionType.TEXT,
                    required=True,
                    help_text="Please describe in your own words.",
                ),
                QuestionItem(
                    id="q_preferred_language",
                    text="Preferred language for communication",
                    question_type=QuestionType.SINGLE_CHOICE,
                    required=True,
                    options=["English", "Hindi", "Bengali", "Spanish", "Other"],
                ),
                QuestionItem(
                    id="q_assistance_needed",
                    text="Do you need wheelchair assistance upon arrival?",
                    question_type=QuestionType.BOOLEAN,
                    required=False,
                ),
            ],
        )
        self._questionnaires[q1.id] = q1

        # Post-Discharge Comfort & Operational Follow-Up
        q2 = QuestionnaireDefinition(
            id="qst_post_discharge",
            code="POST_DISCHARGE_CHECK_V1",
            title="Post-Discharge Administrative Check",
            description="Operational follow-up confirming receipt of discharge documents and comfort.",
            version="1.0.0",
            is_active=True,
            questions=[
                QuestionItem(
                    id="q_received_instructions",
                    text="Did you receive your printed discharge summary and medication instructions?",
                    question_type=QuestionType.BOOLEAN,
                    required=True,
                ),
                QuestionItem(
                    id="q_transportation_home",
                    text="Did you experience any transportation difficulty returning home?",
                    question_type=QuestionType.BOOLEAN,
                    required=False,
                ),
                QuestionItem(
                    id="q_feedback_comments",
                    text="Any additional non-clinical comments or questions?",
                    question_type=QuestionType.TEXT,
                    required=False,
                ),
            ],
        )
        self._questionnaires[q2.id] = q2

    async def get_questionnaire_by_id(self, questionnaire_id: str) -> Optional[QuestionnaireDefinition]:
        """Retrieve questionnaire template by ID."""
        async with self._lock:
            return self._questionnaires.get(questionnaire_id)

    async def get_questionnaire_by_code(self, code: str, version: Optional[str] = None) -> Optional[QuestionnaireDefinition]:
        """Retrieve questionnaire template by code and optional version."""
        async with self._lock:
            for q in self._questionnaires.values():
                if q.code == code and (version is None or q.version == version):
                    return q
            return None

    async def save_questionnaire(self, questionnaire: QuestionnaireDefinition) -> QuestionnaireDefinition:
        """Create or update a questionnaire template."""
        async with self._lock:
            self._questionnaires[questionnaire.id] = questionnaire
            return questionnaire

    async def save_response(self, response: QuestionnaireResponseRecord) -> QuestionnaireResponseRecord:
        """Persist a patient questionnaire response."""
        async with self._lock:
            self._responses[response.id] = response
            if response.action_id not in self._action_responses:
                self._action_responses[response.action_id] = []
            self._action_responses[response.action_id].append(response.id)
            return response

    async def get_responses_by_action_id(self, action_id: str) -> List[QuestionnaireResponseRecord]:
        """Retrieve all questionnaire responses linked to an action."""
        async with self._lock:
            response_ids = self._action_responses.get(action_id, [])
            return [self._responses[rid] for rid in response_ids if rid in self._responses]

    async def clear(self) -> None:
        """Clear responses (for testing). Preserves seeded templates."""
        async with self._lock:
            self._responses.clear()
            self._action_responses.clear()

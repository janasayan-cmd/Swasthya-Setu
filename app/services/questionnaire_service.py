"""HealthSetu Phase 42 - Questionnaire Service.

Handles retrieval, validation, and storage of structured questionnaires.

CLINICAL BOUNDARIES:
- PATIENT QUESTIONNAIRE != DIAGNOSIS
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- Missing required answers fail explicitly; backend NEVER infers missing values.
"""

from __future__ import annotations

from typing import List, Optional

from app.core.exceptions import (
    QuestionnaireNotFoundException,
    QuestionnaireResponseInvalidException,
)
from app.repositories.questionnaire_repository import QuestionnaireRepository
from app.schemas.questionnaire import (
    QuestionItem,
    QuestionType,
    QuestionnaireAnswer,
    QuestionnaireDefinition,
    QuestionnaireResponseRecord,
)


class QuestionnaireService:
    """Orchestrates questionnaire templates and response validation."""

    def __init__(self, questionnaire_repo: QuestionnaireRepository) -> None:
        self.repo = questionnaire_repo

    async def get_questionnaire(self, questionnaire_id: str) -> QuestionnaireDefinition:
        """Fetch questionnaire definition by ID."""
        q = await self.repo.get_questionnaire_by_id(questionnaire_id)
        if not q:
            raise QuestionnaireNotFoundException(
                message=f"Questionnaire with ID '{questionnaire_id}' not found."
            )
        return q

    async def validate_and_save_response(
        self,
        questionnaire_id: str,
        action_id: str,
        patient_id: str,
        answers: List[QuestionnaireAnswer],
        submitted_by: Optional[str] = None,
    ) -> QuestionnaireResponseRecord:
        """Validate patient answers against questionnaire schema and persist response snapshot."""
        q = await self.get_questionnaire(questionnaire_id)

        # Build answer map
        answer_map = {a.question_id: a for a in answers}

        # Validate each question
        for item in q.questions:
            answer = answer_map.get(item.id)
            if item.required:
                if answer is None or answer.value is None or (isinstance(answer.value, str) and not answer.value.strip()):
                    raise QuestionnaireResponseInvalidException(
                        message=f"Missing required answer for question: '{item.text}' (ID: {item.id})."
                    )

            if answer is not None and answer.value is not None:
                self._validate_answer_type(item, answer.value)
                # Store question text snapshot for historical immutability
                answer.question_text = item.text

        record = QuestionnaireResponseRecord(
            questionnaire_id=q.id,
            questionnaire_version=q.version,
            action_id=action_id,
            patient_id=patient_id,
            answers=answers,
            submitted_by=submitted_by,
        )
        return await self.repo.save_response(record)

    def _validate_answer_type(self, item: QuestionItem, val: any) -> None:
        """Ensure answer value matches the QuestionType and bounds."""
        if item.question_type == QuestionType.BOOLEAN:
            if not isinstance(val, bool):
                raise QuestionnaireResponseInvalidException(
                    message=f"Answer for '{item.id}' must be a boolean (True/False)."
                )

        elif item.question_type == QuestionType.SINGLE_CHOICE:
            if str(val) not in item.options:
                raise QuestionnaireResponseInvalidException(
                    message=f"Answer '{val}' for '{item.id}' is not in allowed choices: {item.options}."
                )

        elif item.question_type == QuestionType.MULTIPLE_CHOICE:
            if not isinstance(val, list):
                raise QuestionnaireResponseInvalidException(
                    message=f"Answer for '{item.id}' must be a list of selected options."
                )
            for v in val:
                if str(v) not in item.options:
                    raise QuestionnaireResponseInvalidException(
                        message=f"Option '{v}' is not an allowed choice for question '{item.id}'."
                    )

        elif item.question_type in (QuestionType.NUMBER, QuestionType.SCALE):
            if not isinstance(val, (int, float)):
                raise QuestionnaireResponseInvalidException(
                    message=f"Answer for '{item.id}' must be numeric."
                )
            if item.min_value is not None and val < item.min_value:
                raise QuestionnaireResponseInvalidException(
                    message=f"Value {val} is below minimum allowed value {item.min_value} for '{item.id}'."
                )
            if item.max_value is not None and val > item.max_value:
                raise QuestionnaireResponseInvalidException(
                    message=f"Value {val} exceeds maximum allowed value {item.max_value} for '{item.id}'."
                )

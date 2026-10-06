"""Decision Replay & Investigation Service (Phase 47).

Provides read-only inspection, historical decision reconstruction,
trace relationships, and comparative analysis without patient record mutation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import DecisionNotFoundException
from app.repositories.decision_repository import (
    DecisionRepository,
    decision_repository,
)
from app.schemas.decision_trace import (
    DecisionComparisonResponse,
    DecisionTraceResponse,
    DownstreamActionReference,
)
from app.schemas.decisions import DecisionRecord
from app.services.decision_context_service import (
    DecisionContextService,
    decision_context_service,
)

logger = logging.getLogger(__name__)


class DecisionReplayService:
    """Read-only replay and analytical investigation service for decision traces."""

    def __init__(
        self,
        repository: Optional[DecisionRepository] = None,
        context_service: Optional[DecisionContextService] = None,
    ) -> None:
        self.repository = repository or decision_repository
        self.context_service = context_service or decision_context_service

    def get_decision_trace(self, decision_id: str) -> DecisionTraceResponse:
        """Construct full decision trace including reviews, staleness, and downstream links."""
        decision = self.repository.get_decision(decision_id)
        if not decision:
            raise DecisionNotFoundException(f"Decision {decision_id} not found.")

        reviews = self.repository.get_reviews(decision_id)
        is_stale = self.context_service.is_context_stale(decision)
        is_expired = bool(decision.expires_at and datetime.now(timezone.utc) > decision.expires_at)

        actions: List[DownstreamActionReference] = []
        if decision.downstream_action_id and decision.downstream_action_type:
            actions.append(
                DownstreamActionReference(
                    action_type=decision.downstream_action_type,
                    action_id=decision.downstream_action_id,
                    triggered_at=decision.applied_at or decision.updated_at,
                    status="COMPLETED" if decision.applied_at else "PENDING",
                )
            )

        summary = (
            f"Decision {decision.id} ({decision.decision_type.value}) by {decision.source_service}. "
            f"Status: {decision.status.value}. Reviews: {len(reviews)}. Stale: {is_stale}."
        )

        return DecisionTraceResponse(
            decision=decision,
            reviews=reviews,
            downstream_actions=actions,
            is_stale=is_stale,
            is_expired=is_expired,
            superseded_by_id=decision.superseded_by_id,
            trace_summary=summary,
        )

    def compare_decisions(self, base_id: str, compared_id: str) -> DecisionComparisonResponse:
        """Analyze differences between two decision revisions."""
        base = self.repository.get_decision(base_id)
        if not base:
            raise DecisionNotFoundException(f"Base decision {base_id} not found.")

        comp = self.repository.get_decision(compared_id)
        if not comp:
            raise DecisionNotFoundException(f"Compared decision {compared_id} not found.")

        # Compare inputs
        base_inputs = {f"{r.resource_type}:{r.resource_id}:v{r.version_number}" for r in base.inputs}
        comp_inputs = {f"{r.resource_type}:{r.resource_id}:v{r.version_number}" for r in comp.inputs}
        changed_inputs = sorted(base_inputs ^ comp_inputs)

        # Output payload diff
        output_diff: Dict[str, Any] = {}
        all_keys = set(base.output_payload.keys()) | set(comp.output_payload.keys())
        for k in all_keys:
            v_base = base.output_payload.get(k)
            v_comp = comp.output_payload.get(k)
            if v_base != v_comp:
                output_diff[k] = {"base": v_base, "compared": v_comp}

        # Rules diff
        rule_diffs: List[str] = []
        if (base.rule_metadata and base.rule_metadata.rule_set_version) != (
            comp.rule_metadata and comp.rule_metadata.rule_set_version
        ):
            rule_diffs.append("Rule set version changed")
        if (base.model_metadata and base.model_metadata.model_version) != (
            comp.model_metadata and comp.model_metadata.model_version
        ):
            rule_diffs.append("Model version changed")

        summary = (
            f"Comparison between {base.id} and {comp.id}: "
            f"Status {base.status.value} -> {comp.status.value}. "
            f"{len(output_diff)} output field differences."
        )

        return DecisionComparisonResponse(
            base_decision_id=base.id,
            compared_decision_id=comp.id,
            changed_inputs=changed_inputs,
            changed_rules_or_models=rule_diffs,
            status_transition={"from": base.status.value, "to": comp.status.value},
            output_differences=output_diff,
            summary=summary,
        )


decision_replay_service = DecisionReplayService()

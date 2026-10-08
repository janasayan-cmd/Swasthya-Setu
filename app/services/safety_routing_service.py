"""Phase 60: Safety Routing & Escalation Decision Service.

Calculates explicit, governed routing destinations without making
unsupported causal claims or taking autonomous clinical actions.
"""

from datetime import datetime, timezone
from typing import List, Tuple

from app.schemas.safety_triage import (
    GovernedSignalSeverity,
    RoutingDecisionRecord,
    RoutingDestination,
    SafetyTriageRecord,
    SignalClassification,
    TriageLifecycleState,
    UncertaintyState,
)


class SafetyRoutingService:
    """Calculates governed routing decisions targeting authoritative phases."""

    def determine_routing(
        self,
        record: SafetyTriageRecord,
    ) -> List[RoutingDecisionRecord]:
        """Calculate governed routes and update triage state."""
        now = datetime.now(timezone.utc)
        decisions: List[RoutingDecisionRecord] = []

        cls = record.classification
        sev = record.governed_severity
        unc = record.uncertainty_state

        # 1. Critical Safety Breaches & Safety Control Failures (TRD Section 20 Multi-Route)
        if sev == GovernedSignalSeverity.CRITICAL or cls == SignalClassification.SAFETY_CONTROL:
            record.is_escalated = True
            record.reopen_triggered = True
            record.requires_human_review = True
            record.lifecycle_state = TriageLifecycleState.REOPEN_REQUIRED

            # Route to Phase 58 for Controlled Reopen Evaluation
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_58_REOPEN_REVIEW,
                    target_phase="Phase 58",
                    reason="Critical post-closure safety control failure requires Phase 58 reopen evaluation",
                    applicable_rule="GOV-P60-P58-CRIT-REOPEN",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

            # Route to Phase 49 for Incident Authority Investigation
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_49_INCIDENT_ROUTING,
                    target_phase="Phase 49",
                    reason="Critical surveillance signal escalated to Phase 49 clinical safety incident authority",
                    applicable_rule="GOV-P60-P49-CRIT-INCIDENT",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

            # Route to Phase 51 Governance
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_51_GOVERNANCE_REVIEW,
                    target_phase="Phase 51",
                    reason="Critical safety control regression requires Phase 51 governance risk review",
                    applicable_rule="GOV-P60-P51-GOV-REVIEW",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 2. Assurance Regressions (Phase 52)
        elif cls == SignalClassification.ASSURANCE:
            record.lifecycle_state = TriageLifecycleState.ASSURANCE_ROUTING_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_52_ASSURANCE_REVIEW,
                    target_phase="Phase 52",
                    reason="Assurance signal detected; routing to Phase 52 control assurance authority",
                    applicable_rule="GOV-P60-P52-ASSURANCE",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 3. Effectiveness Regressions (Phase 55)
        elif cls == SignalClassification.EFFECTIVENESS:
            record.lifecycle_state = TriageLifecycleState.EFFECTIVENESS_ROUTING_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW,
                    target_phase="Phase 55",
                    reason="Effectiveness regression signal detected; routing to Phase 55 outcome authority",
                    applicable_rule="GOV-P60-P55-EFFECTIVENESS",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 4. Version or Configuration Drift (Phase 51)
        elif cls in {SignalClassification.VERSION, SignalClassification.CONFIGURATION}:
            record.lifecycle_state = TriageLifecycleState.GOVERNANCE_ROUTING_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.PHASE_51_GOVERNANCE_REVIEW,
                    target_phase="Phase 51",
                    reason="Monitored version/configuration drift requires Phase 51 governance review",
                    applicable_rule="GOV-P60-P51-DRIFT",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 5. High Uncertainty / Conflicted Evidence -> Mandatory Human Review
        elif unc in {UncertaintyState.CONFLICTED_EVIDENCE, UncertaintyState.INSUFFICIENT_DATA, UncertaintyState.HIGH_UNCERTAINTY}:
            record.lifecycle_state = TriageLifecycleState.REVIEW_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.HUMAN_REVIEW,
                    target_phase="Phase 60",
                    reason=f"Evidence uncertainty ({unc.value}) mandates human surveillance supervisor triage",
                    applicable_rule="GOV-P60-HUMAN-UNCERTAINTY",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 6. Moderate System Signals
        elif sev == GovernedSignalSeverity.MODERATE:
            record.lifecycle_state = TriageLifecycleState.REVIEW_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.HUMAN_REVIEW,
                    target_phase="Phase 60",
                    reason="Moderate surveillance anomaly requires human supervisor verification",
                    applicable_rule="GOV-P60-MODERATE-REVIEW",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # 7. Nominal / Routine Surveillance
        elif sev == GovernedSignalSeverity.LOW:
            record.lifecycle_state = TriageLifecycleState.ROUTED
            record.requires_human_review = False
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.CONTINUE_MONITORING,
                    target_phase="Phase 59",
                    reason="Signal evaluated within normal operational variance; continuing surveillance",
                    applicable_rule="GOV-P60-NOMINAL-CONTINUE",
                    requires_human_review=False,
                    routed_at=now,
                )
            )

        else:
            record.lifecycle_state = TriageLifecycleState.REVIEW_REQUIRED
            record.requires_human_review = True
            decisions.append(
                RoutingDecisionRecord(
                    destination=RoutingDestination.HUMAN_REVIEW,
                    target_phase="Phase 60",
                    reason="Unclassified or ambiguous signal state mandates human supervisor review",
                    applicable_rule="GOV-P60-FALLBACK-REVIEW",
                    requires_human_review=True,
                    routed_at=now,
                )
            )

        # Add newly computed decisions to record
        record.routing_decisions.extend(decisions)
        return decisions

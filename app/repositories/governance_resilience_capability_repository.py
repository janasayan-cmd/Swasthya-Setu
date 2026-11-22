"""Phase 84: Clinical Safety Governance Resilience Capability Repository.

Provides thread-safe in-memory persistence and query capabilities for:
- Version-controlled resilience capability frameworks
- Role-based competency requirement definitions
- Capability assessment lifecycles and historical audits
- Practical capability demonstration records
- Collective team readiness assessments
- Delegated-authority readiness assessments
- Evidence-based capability gaps and referrals
- Operational readiness verification records
- Continuous capability development proposals
- Event-triggered and scheduled reassessments
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_resilience_capability_framework import (
    FrameworkLifecycleState,
    ResilienceCapabilityFrameworkRecord,
)
from app.schemas.governance_resilience_role_competency import (
    RoleCapabilityRequirementRecord,
    RoleRequirementStatus,
)
from app.schemas.governance_resilience_capability_assessment import (
    AssessmentLifecycleState,
    AssessmentOutcome,
    CapabilityAssessmentRecord,
)
from app.schemas.governance_resilience_capability_demonstration import (
    CapabilityDemonstrationRecord,
    DemonstrationOutcome,
    DemonstrationReviewStatus,
)
from app.schemas.governance_resilience_team_readiness import (
    TeamReadinessOutcome,
    TeamReadinessRecord,
)
from app.schemas.governance_resilience_delegated_authority_readiness import (
    DelegatedAuthorityReadinessRecord,
    DelegatedAuthorityStatus,
)
from app.schemas.governance_resilience_capability_gap import (
    CapabilityGapCategory,
    CapabilityGapRecord,
    CapabilityGapSeverity,
    CapabilityGapStatus,
)
from app.schemas.governance_resilience_operational_readiness import (
    OperationalReadinessOutcome,
    OperationalReadinessRecord,
    OperationalReadinessScope,
)
from app.schemas.governance_resilience_capability_development import (
    CapabilityDevelopmentProposalRecord,
    ProposalStatus,
)
from app.schemas.governance_resilience_capability_reassessment import (
    CapabilityReassessmentRecord,
    ReassessmentStatus,
)


class GovernanceResilienceCapabilityRepository:
    """Thread-safe in-memory repository for Phase 84 capability assessment data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._frameworks: Dict[str, ResilienceCapabilityFrameworkRecord] = {}
        self._framework_versions: Dict[str, List[ResilienceCapabilityFrameworkRecord]] = {}
        self._role_requirements: Dict[str, RoleCapabilityRequirementRecord] = {}
        self._assessments: Dict[str, CapabilityAssessmentRecord] = {}
        self._assessment_history: Dict[str, List[CapabilityAssessmentRecord]] = {}
        self._demonstrations: Dict[str, CapabilityDemonstrationRecord] = {}
        self._team_readiness: Dict[str, TeamReadinessRecord] = {}
        self._delegated_readiness: Dict[str, DelegatedAuthorityReadinessRecord] = {}
        self._capability_gaps: Dict[str, CapabilityGapRecord] = {}
        self._operational_readiness: Dict[str, OperationalReadinessRecord] = {}
        self._operational_readiness_history: Dict[str, List[OperationalReadinessRecord]] = {}
        self._development_proposals: Dict[str, CapabilityDevelopmentProposalRecord] = {}
        self._reassessments: Dict[str, CapabilityReassessmentRecord] = {}

    def clear(self) -> None:
        """Clear all stored collections for test isolation."""
        with self._lock:
            self._frameworks.clear()
            self._framework_versions.clear()
            self._role_requirements.clear()
            self._assessments.clear()
            self._assessment_history.clear()
            self._demonstrations.clear()
            self._team_readiness.clear()
            self._delegated_readiness.clear()
            self._capability_gaps.clear()
            self._operational_readiness.clear()
            self._operational_readiness_history.clear()
            self._development_proposals.clear()
            self._reassessments.clear()

    # -------------------------------------------------------------------------
    # Capability Frameworks & Versioning
    # -------------------------------------------------------------------------

    def save_framework(self, record: ResilienceCapabilityFrameworkRecord) -> ResilienceCapabilityFrameworkRecord:
        with self._lock:
            self._frameworks[record.framework_id] = record
            if record.framework_id not in self._framework_versions:
                self._framework_versions[record.framework_id] = []
            self._framework_versions[record.framework_id].append(record.model_copy(deep=True))
            return record

    def get_framework(self, framework_id: str, tenant_id: str) -> Optional[ResilienceCapabilityFrameworkRecord]:
        with self._lock:
            rec = self._frameworks.get(framework_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_frameworks(
        self,
        tenant_id: str,
        state: Optional[FrameworkLifecycleState] = None,
    ) -> List[ResilienceCapabilityFrameworkRecord]:
        with self._lock:
            results = [f for f in self._frameworks.values() if f.tenant_id == tenant_id]
            if state:
                results = [f for f in results if f.lifecycle_state == state]
            results.sort(key=lambda f: f.updated_at, reverse=True)
            return results

    def get_framework_versions(
        self, framework_id: str, tenant_id: str
    ) -> List[ResilienceCapabilityFrameworkRecord]:
        with self._lock:
            versions = self._framework_versions.get(framework_id, [])
            return [v for v in versions if v.tenant_id == tenant_id]

    # -------------------------------------------------------------------------
    # Role Competency Requirements
    # -------------------------------------------------------------------------

    def save_role_requirement(self, record: RoleCapabilityRequirementRecord) -> RoleCapabilityRequirementRecord:
        with self._lock:
            self._role_requirements[record.requirement_id] = record
            return record

    def get_role_requirement(
        self, requirement_id: str, tenant_id: str
    ) -> Optional[RoleCapabilityRequirementRecord]:
        with self._lock:
            rec = self._role_requirements.get(requirement_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_role_requirements(
        self,
        tenant_id: str,
        role_name: Optional[str] = None,
        framework_id: Optional[str] = None,
        status: Optional[RoleRequirementStatus] = None,
    ) -> List[RoleCapabilityRequirementRecord]:
        with self._lock:
            results = [r for r in self._role_requirements.values() if r.tenant_id == tenant_id]
            if role_name:
                results = [r for r in results if r.role_name.lower() == role_name.lower()]
            if framework_id:
                results = [r for r in results if r.framework_id == framework_id]
            if status:
                results = [r for r in results if r.status == status]
            return results

    # -------------------------------------------------------------------------
    # Capability Assessments
    # -------------------------------------------------------------------------

    def save_assessment(self, record: CapabilityAssessmentRecord) -> CapabilityAssessmentRecord:
        with self._lock:
            self._assessments[record.assessment_id] = record
            if record.assessment_id not in self._assessment_history:
                self._assessment_history[record.assessment_id] = []
            self._assessment_history[record.assessment_id].append(record.model_copy(deep=True))
            return record

    def get_assessment(self, assessment_id: str, tenant_id: str) -> Optional[CapabilityAssessmentRecord]:
        with self._lock:
            rec = self._assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_assessments(
        self,
        tenant_id: str,
        subject_user_id: Optional[str] = None,
        applicable_role: Optional[str] = None,
        lifecycle_state: Optional[AssessmentLifecycleState] = None,
        outcome: Optional[AssessmentOutcome] = None,
    ) -> List[CapabilityAssessmentRecord]:
        with self._lock:
            results = [a for a in self._assessments.values() if a.tenant_id == tenant_id]
            if subject_user_id:
                results = [a for a in results if a.subject_user_id == subject_user_id]
            if applicable_role:
                results = [a for a in results if a.applicable_role.lower() == applicable_role.lower()]
            if lifecycle_state:
                results = [a for a in results if a.lifecycle_state == lifecycle_state]
            if outcome:
                results = [a for a in results if a.assessment_outcome == outcome]
            results.sort(key=lambda a: a.updated_at, reverse=True)
            return results

    def get_assessment_history(
        self, assessment_id: str, tenant_id: str
    ) -> List[CapabilityAssessmentRecord]:
        with self._lock:
            history = self._assessment_history.get(assessment_id, [])
            return [h for h in history if h.tenant_id == tenant_id]

    # -------------------------------------------------------------------------
    # Practical Capability Demonstrations
    # -------------------------------------------------------------------------

    def save_demonstration(self, record: CapabilityDemonstrationRecord) -> CapabilityDemonstrationRecord:
        with self._lock:
            self._demonstrations[record.demonstration_id] = record
            return record

    def get_demonstration(
        self, demonstration_id: str, tenant_id: str
    ) -> Optional[CapabilityDemonstrationRecord]:
        with self._lock:
            rec = self._demonstrations.get(demonstration_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_demonstrations(
        self,
        tenant_id: str,
        capability_id: Optional[str] = None,
        participant_user_id: Optional[str] = None,
        outcome: Optional[DemonstrationOutcome] = None,
    ) -> List[CapabilityDemonstrationRecord]:
        with self._lock:
            results = [d for d in self._demonstrations.values() if d.tenant_id == tenant_id]
            if capability_id:
                results = [d for d in results if d.capability_id == capability_id]
            if participant_user_id:
                results = [d for d in results if d.participant_user_id == participant_user_id]
            if outcome:
                results = [d for d in results if d.outcome == outcome]
            results.sort(key=lambda d: d.demonstrated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Team Readiness
    # -------------------------------------------------------------------------

    def save_team_readiness(self, record: TeamReadinessRecord) -> TeamReadinessRecord:
        with self._lock:
            self._team_readiness[record.team_assessment_id] = record
            return record

    def get_team_readiness(
        self, team_assessment_id: str, tenant_id: str
    ) -> Optional[TeamReadinessRecord]:
        with self._lock:
            rec = self._team_readiness.get(team_assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_team_readiness(
        self,
        tenant_id: str,
        department_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        outcome: Optional[TeamReadinessOutcome] = None,
    ) -> List[TeamReadinessRecord]:
        with self._lock:
            results = [t for t in self._team_readiness.values() if t.tenant_id == tenant_id]
            if department_id:
                results = [t for t in results if t.department_id == department_id]
            if facility_id:
                results = [t for t in results if t.facility_id == facility_id]
            if outcome:
                results = [t for t in results if t.readiness_outcome == outcome]
            results.sort(key=lambda t: t.assessed_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Delegated-Authority Readiness
    # -------------------------------------------------------------------------

    def save_delegated_readiness(
        self, record: DelegatedAuthorityReadinessRecord
    ) -> DelegatedAuthorityReadinessRecord:
        with self._lock:
            self._delegated_readiness[record.delegation_readiness_id] = record
            return record

    def get_delegated_readiness(
        self, delegation_readiness_id: str, tenant_id: str
    ) -> Optional[DelegatedAuthorityReadinessRecord]:
        with self._lock:
            rec = self._delegated_readiness.get(delegation_readiness_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_delegated_readiness(
        self,
        tenant_id: str,
        delegate_user_id: Optional[str] = None,
        status: Optional[DelegatedAuthorityStatus] = None,
    ) -> List[DelegatedAuthorityReadinessRecord]:
        with self._lock:
            results = [d for d in self._delegated_readiness.values() if d.tenant_id == tenant_id]
            if delegate_user_id:
                results = [d for d in results if d.delegate_user_id == delegate_user_id]
            if status:
                results = [d for d in results if d.status == status]
            results.sort(key=lambda d: d.assessed_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Capability Gaps
    # -------------------------------------------------------------------------

    def save_capability_gap(self, record: CapabilityGapRecord) -> CapabilityGapRecord:
        with self._lock:
            self._capability_gaps[record.gap_id] = record
            return record

    def get_capability_gap(self, gap_id: str, tenant_id: str) -> Optional[CapabilityGapRecord]:
        with self._lock:
            rec = self._capability_gaps.get(gap_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_capability_gaps(
        self,
        tenant_id: str,
        category: Optional[CapabilityGapCategory] = None,
        severity: Optional[CapabilityGapSeverity] = None,
        status: Optional[CapabilityGapStatus] = None,
    ) -> List[CapabilityGapRecord]:
        with self._lock:
            results = [g for g in self._capability_gaps.values() if g.tenant_id == tenant_id]
            if category:
                results = [g for g in results if g.category == category]
            if severity:
                results = [g for g in results if g.severity == severity]
            if status:
                results = [g for g in results if g.status == status]
            results.sort(key=lambda g: g.detected_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Operational Readiness Verification
    # -------------------------------------------------------------------------

    def save_operational_readiness(
        self, record: OperationalReadinessRecord
    ) -> OperationalReadinessRecord:
        with self._lock:
            self._operational_readiness[record.readiness_id] = record
            if record.readiness_id not in self._operational_readiness_history:
                self._operational_readiness_history[record.readiness_id] = []
            self._operational_readiness_history[record.readiness_id].append(record.model_copy(deep=True))
            return record

    def get_operational_readiness(
        self, readiness_id: str, tenant_id: str
    ) -> Optional[OperationalReadinessRecord]:
        with self._lock:
            rec = self._operational_readiness.get(readiness_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_operational_readiness(
        self,
        tenant_id: str,
        scope_type: Optional[OperationalReadinessScope] = None,
        outcome: Optional[OperationalReadinessOutcome] = None,
    ) -> List[OperationalReadinessRecord]:
        with self._lock:
            results = [o for o in self._operational_readiness.values() if o.tenant_id == tenant_id]
            if scope_type:
                results = [o for o in results if o.scope_type == scope_type]
            if outcome:
                results = [o for o in results if o.outcome == outcome]
            results.sort(key=lambda o: o.assessed_at, reverse=True)
            return results

    def get_operational_readiness_history(
        self, readiness_id: str, tenant_id: str
    ) -> List[OperationalReadinessRecord]:
        with self._lock:
            history = self._operational_readiness_history.get(readiness_id, [])
            return [h for h in history if h.tenant_id == tenant_id]

    # -------------------------------------------------------------------------
    # Capability Development Proposals
    # -------------------------------------------------------------------------

    def save_development_proposal(
        self, record: CapabilityDevelopmentProposalRecord
    ) -> CapabilityDevelopmentProposalRecord:
        with self._lock:
            self._development_proposals[record.proposal_id] = record
            return record

    def get_development_proposal(
        self, proposal_id: str, tenant_id: str
    ) -> Optional[CapabilityDevelopmentProposalRecord]:
        with self._lock:
            rec = self._development_proposals.get(proposal_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_development_proposals(
        self,
        tenant_id: str,
        status: Optional[ProposalStatus] = None,
    ) -> List[CapabilityDevelopmentProposalRecord]:
        with self._lock:
            results = [p for p in self._development_proposals.values() if p.tenant_id == tenant_id]
            if status:
                results = [p for p in results if p.status == status]
            results.sort(key=lambda p: p.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Reassessments
    # -------------------------------------------------------------------------

    def save_reassessment(
        self, record: CapabilityReassessmentRecord
    ) -> CapabilityReassessmentRecord:
        with self._lock:
            self._reassessments[record.reassessment_id] = record
            return record

    def get_reassessment(
        self, reassessment_id: str, tenant_id: str
    ) -> Optional[CapabilityReassessmentRecord]:
        with self._lock:
            rec = self._reassessments.get(reassessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_reassessments(
        self,
        tenant_id: str,
        status: Optional[ReassessmentStatus] = None,
    ) -> List[CapabilityReassessmentRecord]:
        with self._lock:
            results = [r for r in self._reassessments.values() if r.tenant_id == tenant_id]
            if status:
                results = [r for r in results if r.status == status]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results


_governance_resilience_capability_repo = GovernanceResilienceCapabilityRepository()
governance_resilience_capability_repository = _governance_resilience_capability_repo


def get_governance_resilience_capability_repository() -> GovernanceResilienceCapabilityRepository:
    """Dependency injector for Phase 84 repository singleton."""
    return _governance_resilience_capability_repo

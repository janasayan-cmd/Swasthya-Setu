"""Phase 83: Clinical Safety Governance Resilience Knowledge Repository.

Provides thread-safe in-memory persistence and query capabilities for:
- Resilience knowledge records and material versions
- Knowledge distribution campaigns
- Delivery and user acknowledgements
- Practical application evidence
- Organizational learning gaps and CAPA referrals
- Continuous capability development recommendations
- Knowledge succession and ownership transfers
- Guidance conflict detection and resolution records
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_resilience_knowledge import (
    KnowledgeCategory,
    KnowledgeLifecycleState,
    ResilienceKnowledgeRecord,
)
from app.schemas.governance_resilience_knowledge_distribution import (
    CampaignStatus,
    KnowledgeDistributionCampaignRecord,
)
from app.schemas.governance_resilience_knowledge_tracking import (
    AcknowledgementStatus,
    ApplicationEvidenceStatus,
    KnowledgeAcknowledgementRecord,
    KnowledgeApplicationEvidenceRecord,
)
from app.schemas.governance_resilience_knowledge_learning_gaps import (
    LearningGapSeverity,
    LearningGapStatus,
    LearningGapType,
    OrganizationalLearningGapRecord,
)
from app.schemas.governance_resilience_knowledge_recommendations import (
    CapabilityActivityType,
    RecommendationPriority,
    RecommendationStatus,
    ResilienceCapabilityRecommendationRecord,
)
from app.schemas.governance_resilience_knowledge_transfer import (
    KnowledgeTransferRecord,
    TransferStatus,
)
from app.schemas.governance_resilience_knowledge_conflicts import (
    ConflictStatus,
    KnowledgeConflictRecord,
    KnowledgeConflictType,
)


class GovernanceResilienceKnowledgeRepository:
    """Thread-safe in-memory repository for Phase 83 resilience knowledge management."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._knowledge_records: Dict[str, ResilienceKnowledgeRecord] = {}
        self._campaigns: Dict[str, KnowledgeDistributionCampaignRecord] = {}
        self._acknowledgements: Dict[str, KnowledgeAcknowledgementRecord] = {}
        self._application_evidence: Dict[str, KnowledgeApplicationEvidenceRecord] = {}
        self._learning_gaps: Dict[str, OrganizationalLearningGapRecord] = {}
        self._recommendations: Dict[str, ResilienceCapabilityRecommendationRecord] = {}
        self._transfers: Dict[str, KnowledgeTransferRecord] = {}
        self._conflicts: Dict[str, KnowledgeConflictRecord] = {}

    def clear(self) -> None:
        """Clear all stored state across collections. Used for test isolation."""
        with self._lock:
            self._knowledge_records.clear()
            self._campaigns.clear()
            self._acknowledgements.clear()
            self._application_evidence.clear()
            self._learning_gaps.clear()
            self._recommendations.clear()
            self._transfers.clear()
            self._conflicts.clear()

    # -------------------------------------------------------------------------
    # Resilience Knowledge Records
    # -------------------------------------------------------------------------

    def save_knowledge(self, record: ResilienceKnowledgeRecord) -> ResilienceKnowledgeRecord:
        with self._lock:
            self._knowledge_records[record.knowledge_id] = record
            return record

    def get_knowledge(self, knowledge_id: str, tenant_id: str) -> Optional[ResilienceKnowledgeRecord]:
        with self._lock:
            rec = self._knowledge_records.get(knowledge_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_knowledge(
        self,
        tenant_id: str,
        category: Optional[KnowledgeCategory] = None,
        state: Optional[KnowledgeLifecycleState] = None,
        owner_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ResilienceKnowledgeRecord]:
        with self._lock:
            results = [
                rec for rec in self._knowledge_records.values()
                if rec.tenant_id == tenant_id
            ]
            if category:
                results = [r for r in results if r.category == category]
            if state:
                results = [r for r in results if r.current_state == state]
            if owner_id:
                results = [r for r in results if r.owner_id == owner_id or r.author_id == owner_id]
            if query:
                q = query.lower()
                results = [
                    r for r in results
                    if q in r.title.lower() or q in r.summary.lower() or any(q in t.lower() for t in r.tags)
                ]
            results.sort(key=lambda r: r.updated_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Distribution Campaigns
    # -------------------------------------------------------------------------

    def save_campaign(self, record: KnowledgeDistributionCampaignRecord) -> KnowledgeDistributionCampaignRecord:
        with self._lock:
            self._campaigns[record.campaign_id] = record
            return record

    def get_campaign(self, campaign_id: str, tenant_id: str) -> Optional[KnowledgeDistributionCampaignRecord]:
        with self._lock:
            rec = self._campaigns.get(campaign_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_campaigns(
        self,
        tenant_id: str,
        knowledge_id: Optional[str] = None,
        status: Optional[CampaignStatus] = None,
    ) -> List[KnowledgeDistributionCampaignRecord]:
        with self._lock:
            results = [
                c for c in self._campaigns.values()
                if c.tenant_id == tenant_id
            ]
            if knowledge_id:
                results = [c for c in results if c.knowledge_id == knowledge_id]
            if status:
                results = [c for c in results if c.status == status]
            results.sort(key=lambda c: c.updated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Acknowledgements
    # -------------------------------------------------------------------------

    def save_acknowledgement(self, record: KnowledgeAcknowledgementRecord) -> KnowledgeAcknowledgementRecord:
        with self._lock:
            self._acknowledgements[record.acknowledgement_id] = record
            return record

    def get_acknowledgement(self, acknowledgement_id: str, tenant_id: str) -> Optional[KnowledgeAcknowledgementRecord]:
        with self._lock:
            rec = self._acknowledgements.get(acknowledgement_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_acknowledgements(
        self,
        tenant_id: str,
        campaign_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[AcknowledgementStatus] = None,
    ) -> List[KnowledgeAcknowledgementRecord]:
        with self._lock:
            results = [
                a for a in self._acknowledgements.values()
                if a.tenant_id == tenant_id
            ]
            if campaign_id:
                results = [a for a in results if a.campaign_id == campaign_id]
            if user_id:
                results = [a for a in results if a.user_id == user_id]
            if status:
                results = [a for a in results if a.status == status]
            return results

    # -------------------------------------------------------------------------
    # Practical Application Evidence
    # -------------------------------------------------------------------------

    def save_evidence(self, record: KnowledgeApplicationEvidenceRecord) -> KnowledgeApplicationEvidenceRecord:
        with self._lock:
            self._application_evidence[record.evidence_id] = record
            return record

    def get_evidence(self, evidence_id: str, tenant_id: str) -> Optional[KnowledgeApplicationEvidenceRecord]:
        with self._lock:
            rec = self._application_evidence.get(evidence_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_evidence(
        self,
        tenant_id: str,
        knowledge_id: Optional[str] = None,
        status: Optional[ApplicationEvidenceStatus] = None,
    ) -> List[KnowledgeApplicationEvidenceRecord]:
        with self._lock:
            results = [
                e for e in self._application_evidence.values()
                if e.tenant_id == tenant_id
            ]
            if knowledge_id:
                results = [e for e in results if e.knowledge_id == knowledge_id]
            if status:
                results = [e for e in results if e.status == status]
            results.sort(key=lambda e: e.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Organizational Learning Gaps
    # -------------------------------------------------------------------------

    def save_learning_gap(self, record: OrganizationalLearningGapRecord) -> OrganizationalLearningGapRecord:
        with self._lock:
            self._learning_gaps[record.gap_id] = record
            return record

    def get_learning_gap(self, gap_id: str, tenant_id: str) -> Optional[OrganizationalLearningGapRecord]:
        with self._lock:
            rec = self._learning_gaps.get(gap_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_learning_gaps(
        self,
        tenant_id: str,
        status: Optional[LearningGapStatus] = None,
        severity: Optional[LearningGapSeverity] = None,
        gap_type: Optional[LearningGapType] = None,
    ) -> List[OrganizationalLearningGapRecord]:
        with self._lock:
            results = [
                g for g in self._learning_gaps.values()
                if g.tenant_id == tenant_id
            ]
            if status:
                results = [g for g in results if g.status == status]
            if severity:
                results = [g for g in results if g.severity == severity]
            if gap_type:
                results = [g for g in results if g.gap_type == gap_type]
            results.sort(key=lambda g: g.identified_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Capability Development Recommendations
    # -------------------------------------------------------------------------

    def save_recommendation(
        self, record: ResilienceCapabilityRecommendationRecord
    ) -> ResilienceCapabilityRecommendationRecord:
        with self._lock:
            self._recommendations[record.recommendation_id] = record
            return record

    def get_recommendation(
        self, recommendation_id: str, tenant_id: str
    ) -> Optional[ResilienceCapabilityRecommendationRecord]:
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_recommendations(
        self,
        tenant_id: str,
        status: Optional[RecommendationStatus] = None,
        activity_type: Optional[CapabilityActivityType] = None,
        priority: Optional[RecommendationPriority] = None,
    ) -> List[ResilienceCapabilityRecommendationRecord]:
        with self._lock:
            results = [
                r for r in self._recommendations.values()
                if r.tenant_id == tenant_id
            ]
            if status:
                results = [r for r in results if r.status == status]
            if activity_type:
                results = [r for r in results if r.activity_type == activity_type]
            if priority:
                results = [r for r in results if r.priority == priority]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Knowledge Succession & Transfers
    # -------------------------------------------------------------------------

    def save_transfer(self, record: KnowledgeTransferRecord) -> KnowledgeTransferRecord:
        with self._lock:
            self._transfers[record.transfer_id] = record
            return record

    def get_transfer(self, transfer_id: str, tenant_id: str) -> Optional[KnowledgeTransferRecord]:
        with self._lock:
            rec = self._transfers.get(transfer_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_transfers(
        self,
        tenant_id: str,
        owner_id: Optional[str] = None,
        status: Optional[TransferStatus] = None,
    ) -> List[KnowledgeTransferRecord]:
        with self._lock:
            results = [
                t for t in self._transfers.values()
                if t.tenant_id == tenant_id
            ]
            if owner_id:
                results = [
                    t for t in results
                    if t.transferring_owner_id == owner_id or t.successor_owner_id == owner_id
                ]
            if status:
                results = [t for t in results if t.status == status]
            results.sort(key=lambda t: t.initiated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Knowledge Conflicts
    # -------------------------------------------------------------------------

    def save_conflict(self, record: KnowledgeConflictRecord) -> KnowledgeConflictRecord:
        with self._lock:
            self._conflicts[record.conflict_id] = record
            return record

    def get_conflict(self, conflict_id: str, tenant_id: str) -> Optional[KnowledgeConflictRecord]:
        with self._lock:
            rec = self._conflicts.get(conflict_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_conflicts(
        self,
        tenant_id: str,
        status: Optional[ConflictStatus] = None,
        conflict_type: Optional[KnowledgeConflictType] = None,
    ) -> List[KnowledgeConflictRecord]:
        with self._lock:
            results = [
                c for c in self._conflicts.values()
                if c.tenant_id == tenant_id
            ]
            if status:
                results = [c for c in results if c.status == status]
            if conflict_type:
                results = [c for c in results if c.conflict_type == conflict_type]
            results.sort(key=lambda c: c.detected_at, reverse=True)
            return results


_governance_resilience_knowledge_repo = GovernanceResilienceKnowledgeRepository()
governance_resilience_knowledge_repository = _governance_resilience_knowledge_repo


def get_governance_resilience_knowledge_repository() -> GovernanceResilienceKnowledgeRepository:
    """Dependency injector for Phase 83 knowledge repository singleton."""
    return _governance_resilience_knowledge_repo

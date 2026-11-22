"""Phase 83: Knowledge Reporting and Maintenance Domain Service.

Generates 7 executive and management reports, performs routine maintenance scans
to identify outdated guidance, low acknowledgement compliance, and unresolved gaps.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge import (
    KnowledgeLifecycleState,
    ResilienceKnowledgeRecord,
)
from app.schemas.governance_resilience_knowledge_distribution import CampaignStatus
from app.schemas.governance_resilience_knowledge_tracking import (
    AcknowledgementStatus,
    ApplicationEvidenceStatus,
)
from app.schemas.governance_resilience_knowledge_learning_gaps import (
    LearningGapStatus,
)
from app.schemas.governance_resilience_knowledge_recommendations import (
    RecommendationStatus,
)
from app.schemas.governance_resilience_knowledge_transfer import TransferStatus
from app.schemas.governance_resilience_knowledge_conflicts import ConflictStatus
from app.schemas.governance_resilience_knowledge_reporting import (
    ApplicationEvidenceReport,
    CapabilityDevelopmentReport,
    DistributionComplianceReport,
    KnowledgeInventoryReport,
    KnowledgeSuccessionReport,
    LearningGapsReport,
    ResilienceKnowledgeSearchRequest,
    ResiliencePreparednessMaturityReport,
    RoutineMaintenanceScanResult,
)


class GovernanceResilienceKnowledgeReportingService:
    """Service compiling executive reporting and routine preparedness maintenance scans."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def search_knowledge(
        self, tenant_id: str, request: ResilienceKnowledgeSearchRequest
    ) -> List[ResilienceKnowledgeRecord]:
        all_records = self.repository.list_knowledge(tenant_id=tenant_id, query=request.query, limit=500)
        if request.categories:
            all_records = [r for r in all_records if r.category in request.categories]
        if request.states:
            all_records = [r for r in all_records if r.current_state in request.states]
        if request.tags:
            all_records = [r for r in all_records if any(t in r.tags for t in request.tags)]
        if request.owner_id:
            all_records = [r for r in all_records if r.owner_id == request.owner_id]

        return all_records[request.offset : request.offset + request.limit]

    def get_inventory_report(self, tenant_id: str) -> KnowledgeInventoryReport:
        records = self.repository.list_knowledge(tenant_id=tenant_id, limit=1000)
        by_cat: Dict[str, int] = {}
        by_state: Dict[str, int] = {}
        by_conf: Dict[str, int] = {}

        for r in records:
            by_cat[r.category.value] = by_cat.get(r.category.value, 0) + 1
            by_state[r.current_state.value] = by_state.get(r.current_state.value, 0) + 1
            by_conf[r.confidentiality_level.value] = by_conf.get(r.confidentiality_level.value, 0) + 1

        return KnowledgeInventoryReport(
            total_knowledge_records=len(records),
            by_category=by_cat,
            by_state=by_state,
            by_confidentiality=by_conf,
        )

    def get_distribution_compliance_report(self, tenant_id: str) -> DistributionComplianceReport:
        campaigns = self.repository.list_campaigns(tenant_id=tenant_id)
        active_campaigns = [c for c in campaigns if c.status == CampaignStatus.DISPATCHED]
        acks = self.repository.list_acknowledgements(tenant_id=tenant_id)

        total_req = len(acks)
        total_acked = len([a for a in acks if a.status == AcknowledgementStatus.ACKNOWLEDGED])
        rate = (total_acked / total_req * 100.0) if total_req > 0 else 0.0

        return DistributionComplianceReport(
            total_campaigns=len(campaigns),
            active_campaigns=len(active_campaigns),
            total_acknowledgements_required=total_req,
            total_acknowledged=total_acked,
            acknowledgement_rate_percent=round(rate, 2),
            overdue_acknowledgements=0,
        )

    def get_application_evidence_report(self, tenant_id: str) -> ApplicationEvidenceReport:
        evidence_list = self.repository.list_evidence(tenant_id=tenant_id)
        verified = [e for e in evidence_list if e.status == ApplicationEvidenceStatus.VERIFIED]
        rejected = [e for e in evidence_list if e.status == ApplicationEvidenceStatus.REJECTED]

        by_ctx: Dict[str, int] = {}
        rating_sum = 0
        phase55_count = 0

        for e in evidence_list:
            by_ctx[e.operational_context.value] = by_ctx.get(e.operational_context.value, 0) + 1
            rating_sum += e.observed_effectiveness_rating
            if e.phase55_assessment_id:
                phase55_count += 1

        avg_rating = (rating_sum / len(evidence_list)) if evidence_list else 0.0

        return ApplicationEvidenceReport(
            total_evidence_records=len(evidence_list),
            verified_evidence_records=len(verified),
            rejected_evidence_records=len(rejected),
            by_operational_context=by_ctx,
            average_effectiveness_rating=round(avg_rating, 2),
            linked_phase55_assessments=phase55_count,
        )

    def get_learning_gaps_report(self, tenant_id: str) -> LearningGapsReport:
        gaps = self.repository.list_learning_gaps(tenant_id=tenant_id)
        open_gaps = [
            g for g in gaps
            if g.status in [LearningGapStatus.IDENTIFIED, LearningGapStatus.VALIDATED, LearningGapStatus.CAPA_REFERRED]
        ]
        capa_gaps = [g for g in gaps if g.status == LearningGapStatus.CAPA_REFERRED]
        resolved = [g for g in gaps if g.status in [LearningGapStatus.RESOLVED, LearningGapStatus.CLOSED]]

        by_type: Dict[str, int] = {}
        by_sev: Dict[str, int] = {}

        for g in gaps:
            by_type[g.gap_type.value] = by_type.get(g.gap_type.value, 0) + 1
            by_sev[g.severity.value] = by_sev.get(g.severity.value, 0) + 1

        return LearningGapsReport(
            total_gaps_identified=len(gaps),
            open_gaps=len(open_gaps),
            by_gap_type=by_type,
            by_severity=by_sev,
            capa_referred_gaps=len(capa_gaps),
            resolved_gaps=len(resolved),
        )

    def get_capability_development_report(self, tenant_id: str) -> CapabilityDevelopmentReport:
        recs = self.repository.list_recommendations(tenant_id=tenant_id)
        by_act: Dict[str, int] = {}
        by_stat: Dict[str, int] = {}

        completed = 0
        scheduled = 0

        for r in recs:
            by_act[r.activity_type.value] = by_act.get(r.activity_type.value, 0) + 1
            by_stat[r.status.value] = by_stat.get(r.status.value, 0) + 1
            if r.status == RecommendationStatus.COMPLETED:
                completed += 1
            elif r.status == RecommendationStatus.SCHEDULED:
                scheduled += 1

        return CapabilityDevelopmentReport(
            total_recommendations=len(recs),
            by_activity_type=by_act,
            by_status=by_stat,
            completed_activities=completed,
            scheduled_activities=scheduled,
        )

    def get_succession_report(self, tenant_id: str) -> KnowledgeSuccessionReport:
        transfers = self.repository.list_transfers(tenant_id=tenant_id)
        verified = [t for t in transfers if t.status == TransferStatus.VERIFIED]
        pending = [t for t in transfers if t.status in [TransferStatus.INITIATED, TransferStatus.IN_PROGRESS, TransferStatus.COMPLETED]]
        rejected = [t for t in transfers if t.status == TransferStatus.REJECTED]

        return KnowledgeSuccessionReport(
            total_transfers=len(transfers),
            verified_transfers=len(verified),
            pending_transfers=len(pending),
            rejected_transfers=len(rejected),
        )

    def get_maturity_report(self, tenant_id: str) -> ResiliencePreparednessMaturityReport:
        knowledge_list = self.repository.list_knowledge(tenant_id=tenant_id, limit=500)
        published = [k for k in knowledge_list if k.current_state == KnowledgeLifecycleState.PUBLISHED]
        conflicts = self.repository.list_conflicts(tenant_id=tenant_id, status=ConflictStatus.DETECTED)
        gaps = self.repository.list_learning_gaps(tenant_id=tenant_id)
        resolved_gaps = [g for g in gaps if g.status in [LearningGapStatus.RESOLVED, LearningGapStatus.CLOSED]]

        gap_rate = (len(resolved_gaps) / len(gaps) * 100.0) if gaps else 100.0
        score = min(100.0, (len(published) * 10.0) + (gap_rate * 0.5) - (len(conflicts) * 15.0))
        posture = "ADVANCED" if score >= 75.0 else ("DEVELOPING" if score >= 40.0 else "INITIAL")

        return ResiliencePreparednessMaturityReport(
            knowledge_base_maturity_score=round(max(0.0, score), 1),
            published_guidance_count=len(published),
            compliance_score_percent=round(gap_rate, 1),
            gap_resolution_rate_percent=round(gap_rate, 1),
            active_conflicts_count=len(conflicts),
            overall_resilience_posture=posture,
        )

    def run_maintenance_scan(self, tenant_id: str) -> RoutineMaintenanceScanResult:
        knowledge_list = self.repository.list_knowledge(tenant_id=tenant_id, limit=500)
        now = datetime.utcnow()
        outdated: List[str] = []
        pending_review: List[str] = []

        for k in knowledge_list:
            if k.current_state == KnowledgeLifecycleState.PUBLISHED:
                if k.review_due_date and k.review_due_date < now:
                    pending_review.append(k.knowledge_id)
                elif (now - k.updated_at).days > 365:
                    outdated.append(k.knowledge_id)

        conflicts = self.repository.list_conflicts(tenant_id=tenant_id, status=ConflictStatus.DETECTED)
        open_conflicts = [c.conflict_id for c in conflicts]

        gaps = self.repository.list_learning_gaps(tenant_id=tenant_id, status=LearningGapStatus.IDENTIFIED)
        unaddressed_gaps = [g.gap_id for g in gaps]

        total_anomalies = len(outdated) + len(pending_review) + len(open_conflicts) + len(unaddressed_gaps)

        return RoutineMaintenanceScanResult(
            outdated_knowledge_ids=outdated,
            pending_review_knowledge_ids=pending_review,
            unresolved_conflict_ids=open_conflicts,
            unaddressed_gap_ids=unaddressed_gaps,
            total_anomalies_detected=total_anomalies,
        )


_reporting_service = GovernanceResilienceKnowledgeReportingService()


def get_governance_resilience_knowledge_reporting_service() -> GovernanceResilienceKnowledgeReportingService:
    return _reporting_service

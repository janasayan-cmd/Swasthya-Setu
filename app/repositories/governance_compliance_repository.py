"""Phase 69: Governance Compliance & Regulatory Evidence Repository.

Provides a thread-safe repository layer for:
- Frameworks and versioned requirements
- Requirement-to-control mappings
- Compliance assessments and historical evaluation runs
- Compliance evidence index
- Identified compliance findings (gaps)
- Corrective action requests
- Generated evidence packages
- Specialized queues and idempotency cache
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.compliance_assessment import (
    ComplianceAssessmentRecord,
    ComplianceStatus,
)
from app.schemas.compliance_evidence import (
    ComplianceEvidenceRecord,
)
from app.schemas.compliance_finding import (
    ComplianceFindingRecord,
    CompliancePriority,
)
from app.schemas.compliance_framework import (
    ComplianceFrameworkRecord,
    ComplianceRequirementRecord,
    RequirementControlMappingRecord,
)
from app.schemas.compliance_package_report import (
    ComplianceCorrectiveActionRequestRecord,
    EvidencePackageRecord,
)


class GovernanceComplianceRepository:
    """Thread-safe in-memory repository for Phase 69 compliance monitoring entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._frameworks: Dict[str, ComplianceFrameworkRecord] = {}
        self._requirements: Dict[str, ComplianceRequirementRecord] = {}
        self._control_mappings: Dict[str, RequirementControlMappingRecord] = {}
        self._assessments: Dict[str, ComplianceAssessmentRecord] = {}
        self._evidence: Dict[str, ComplianceEvidenceRecord] = {}
        self._findings: Dict[str, ComplianceFindingRecord] = {}
        self._corrective_actions: Dict[str, ComplianceCorrectiveActionRequestRecord] = {}
        self._evidence_packages: Dict[str, EvidencePackageRecord] = {}
        self._requirement_assessment_map: Dict[str, List[str]] = {}
        self._idempotency_store: Dict[str, Tuple[str, datetime]] = {}

    # -------------------------------------------------------------------------
    # Frameworks
    # -------------------------------------------------------------------------

    def save_framework(self, record: ComplianceFrameworkRecord) -> ComplianceFrameworkRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._frameworks[record.framework_id] = record
            return record

    def get_framework(self, framework_id: str) -> Optional[ComplianceFrameworkRecord]:
        with self._lock:
            return self._frameworks.get(framework_id)

    def list_frameworks(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        framework_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceFrameworkRecord]:
        with self._lock:
            results = [
                fw for fw in self._frameworks.values()
                if fw.organization_id == organization_id
                and (facility_id is None or fw.facility_id == facility_id or fw.facility_id is None)
                and (framework_type is None or fw.framework_type.value == framework_type)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Requirements
    # -------------------------------------------------------------------------

    def save_requirement(self, record: ComplianceRequirementRecord) -> ComplianceRequirementRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._requirements[record.requirement_id] = record
            return record

    def get_requirement(self, requirement_id: str) -> Optional[ComplianceRequirementRecord]:
        with self._lock:
            return self._requirements.get(requirement_id)

    def list_requirements(
        self,
        organization_id: str,
        framework_id: Optional[str] = None,
        category: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceRequirementRecord]:
        with self._lock:
            results = [
                req for req in self._requirements.values()
                if req.organization_id == organization_id
                and (framework_id is None or req.framework_id == framework_id)
                and (category is None or req.category.value == category)
                and (lifecycle_status is None or req.lifecycle_status.value == lifecycle_status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Control Mappings
    # -------------------------------------------------------------------------

    def save_control_mapping(
        self, record: RequirementControlMappingRecord
    ) -> RequirementControlMappingRecord:
        with self._lock:
            self._control_mappings[record.mapping_id] = record
            return record

    def get_control_mapping(self, mapping_id: str) -> Optional[RequirementControlMappingRecord]:
        with self._lock:
            return self._control_mappings.get(mapping_id)

    def list_control_mappings(self, requirement_id: str) -> List[RequirementControlMappingRecord]:
        with self._lock:
            results = [m for m in self._control_mappings.values() if m.requirement_id == requirement_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Assessments
    # -------------------------------------------------------------------------

    def save_assessment(self, record: ComplianceAssessmentRecord) -> ComplianceAssessmentRecord:
        with self._lock:
            self._assessments[record.assessment_id] = record
            if record.requirement_id not in self._requirement_assessment_map:
                self._requirement_assessment_map[record.requirement_id] = []
            if record.assessment_id not in self._requirement_assessment_map[record.requirement_id]:
                self._requirement_assessment_map[record.requirement_id].append(record.assessment_id)
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.assessment_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get_assessment(self, assessment_id: str) -> Optional[ComplianceAssessmentRecord]:
        with self._lock:
            return self._assessments.get(assessment_id)

    def get_latest_assessment_for_requirement(
        self, requirement_id: str
    ) -> Optional[ComplianceAssessmentRecord]:
        with self._lock:
            a_ids = self._requirement_assessment_map.get(requirement_id, [])
            if not a_ids:
                return None
            records = [self._assessments[aid] for aid in a_ids if aid in self._assessments]
            if not records:
                return None
            records.sort(key=lambda x: x.assessed_at, reverse=True)
            return records[0]

    def list_assessments_for_requirement(
        self, requirement_id: str
    ) -> List[ComplianceAssessmentRecord]:
        with self._lock:
            a_ids = self._requirement_assessment_map.get(requirement_id, [])
            records = [self._assessments[aid] for aid in a_ids if aid in self._assessments]
            records.sort(key=lambda x: x.assessed_at, reverse=True)
            return records

    def list_assessments(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceAssessmentRecord]:
        with self._lock:
            results = [
                a for a in self._assessments.values()
                if a.organization_id == organization_id
                and (facility_id is None or a.facility_id == facility_id or a.facility_id is None)
                and (status is None or a.status.value == status)
            ]
            results.sort(key=lambda x: x.assessed_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------

    def save_evidence(self, record: ComplianceEvidenceRecord) -> ComplianceEvidenceRecord:
        with self._lock:
            self._evidence[record.evidence_id] = record
            return record

    def get_evidence(self, evidence_id: str) -> Optional[ComplianceEvidenceRecord]:
        with self._lock:
            return self._evidence.get(evidence_id)

    def list_evidence_for_requirement(
        self, requirement_id: str
    ) -> List[ComplianceEvidenceRecord]:
        with self._lock:
            results = [ev for ev in self._evidence.values() if ev.requirement_id == requirement_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    def list_evidence(
        self,
        requirement_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceEvidenceRecord]:
        with self._lock:
            results = [
                ev for ev in self._evidence.values()
                if requirement_id is None or ev.requirement_id == requirement_id
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Findings
    # -------------------------------------------------------------------------

    def save_finding(self, record: ComplianceFindingRecord) -> ComplianceFindingRecord:
        with self._lock:
            self._findings[record.finding_id] = record
            return record

    def get_finding(self, finding_id: str) -> Optional[ComplianceFindingRecord]:
        with self._lock:
            return self._findings.get(finding_id)

    def list_findings(
        self,
        assessment_id: Optional[str] = None,
        requirement_id: Optional[str] = None,
        gap_category: Optional[str] = None,
        priority: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceFindingRecord]:
        with self._lock:
            results = [
                f for f in self._findings.values()
                if (assessment_id is None or f.assessment_id == assessment_id)
                and (requirement_id is None or f.requirement_id == requirement_id)
                and (gap_category is None or f.gap_category.value == gap_category)
                and (priority is None or f.priority.value == priority)
                and (is_resolved is None or f.is_resolved == is_resolved)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Corrective Actions
    # -------------------------------------------------------------------------

    def save_corrective_action(
        self, record: ComplianceCorrectiveActionRequestRecord
    ) -> ComplianceCorrectiveActionRequestRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._corrective_actions[record.action_request_id] = record
            return record

    def get_corrective_action(
        self, action_request_id: str
    ) -> Optional[ComplianceCorrectiveActionRequestRecord]:
        with self._lock:
            return self._corrective_actions.get(action_request_id)

    def list_corrective_actions_for_finding(
        self, finding_id: str
    ) -> List[ComplianceCorrectiveActionRequestRecord]:
        with self._lock:
            results = [ca for ca in self._corrective_actions.values() if ca.finding_id == finding_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Evidence Packages
    # -------------------------------------------------------------------------

    def save_evidence_package(self, record: EvidencePackageRecord) -> EvidencePackageRecord:
        with self._lock:
            self._evidence_packages[record.package_id] = record
            return record

    def get_evidence_package(self, package_id: str) -> Optional[EvidencePackageRecord]:
        with self._lock:
            return self._evidence_packages.get(package_id)

    def list_evidence_packages(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EvidencePackageRecord]:
        with self._lock:
            results = [
                pkg for pkg in self._evidence_packages.values()
                if pkg.organization_id == organization_id
                and (facility_id is None or pkg.facility_id == facility_id or pkg.facility_id is None)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Queues
    # -------------------------------------------------------------------------

    def list_review_required_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ComplianceAssessmentRecord]:
        """Assessments flagged REVIEW_REQUIRED or having unresolved critical/high findings."""
        with self._lock:
            results: List[ComplianceAssessmentRecord] = []
            for req_id in self._requirements.keys():
                latest = self.get_latest_assessment_for_requirement(req_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id or latest.facility_id is None)
                    and (
                        latest.status == ComplianceStatus.REVIEW_REQUIRED
                        or latest.critical_findings_count > 0
                    )
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.assessed_at, reverse=True)
            return results

    def list_evidence_required_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ComplianceAssessmentRecord]:
        """Assessments pending due to EVIDENCE_INSUFFICIENT, EVIDENCE_UNAVAILABLE, or EVIDENCE_CONFLICTED."""
        with self._lock:
            results: List[ComplianceAssessmentRecord] = []
            for req_id in self._requirements.keys():
                latest = self.get_latest_assessment_for_requirement(req_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id or latest.facility_id is None)
                    and latest.status in {
                        ComplianceStatus.EVIDENCE_INSUFFICIENT,
                        ComplianceStatus.EVIDENCE_UNAVAILABLE,
                        ComplianceStatus.EVIDENCE_CONFLICTED,
                    }
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.assessed_at, reverse=True)
            return results

    def list_reassessment_required_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ComplianceAssessmentRecord]:
        """Assessments marked REASSESSMENT_REQUIRED."""
        with self._lock:
            results: List[ComplianceAssessmentRecord] = []
            for req_id in self._requirements.keys():
                latest = self.get_latest_assessment_for_requirement(req_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id or latest.facility_id is None)
                    and latest.status == ComplianceStatus.REASSESSMENT_REQUIRED
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.assessed_at, reverse=True)
            return results

    def list_overdue_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ComplianceRequirementRecord]:
        """Active requirements that have never been assessed or exceeded assessment interval."""
        with self._lock:
            results: List[ComplianceRequirementRecord] = []
            for req in self._requirements.values():
                if req.organization_id == organization_id and req.lifecycle_status.value == "ACTIVE":
                    latest = self.get_latest_assessment_for_requirement(req.requirement_id)
                    if not latest:
                        results.append(req)
            return results

    # -------------------------------------------------------------------------
    # Idempotency
    # -------------------------------------------------------------------------

    def get_idempotent_id(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._idempotency_store.get(key)
            return entry[0] if entry else None

    # -------------------------------------------------------------------------
    # Clear / Test Utility
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        with self._lock:
            self._frameworks.clear()
            self._requirements.clear()
            self._control_mappings.clear()
            self._assessments.clear()
            self._evidence.clear()
            self._findings.clear()
            self._corrective_actions.clear()
            self._evidence_packages.clear()
            self._requirement_assessment_map.clear()
            self._idempotency_store.clear()


# Global singleton instance
_global_compliance_repo = GovernanceComplianceRepository()


def get_governance_compliance_repository() -> GovernanceComplianceRepository:
    """Dependency provider for Phase 69 compliance repository."""
    return _global_compliance_repo

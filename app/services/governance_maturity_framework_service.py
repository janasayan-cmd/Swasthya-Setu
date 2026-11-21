"""Phase 77: Governance Maturity Framework Service.

Manages the lifecycle, versioning, dimensions, and criteria of clinical safety
governance maturity frameworks.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    AddCriterionRequest,
    AddDimensionRequest,
    CreateFrameworkRequest,
    FrameworkStatus,
    GovernanceMaturityFrameworkRecord,
    MaturityCriterion,
    MaturityDimensionDefinition,
    MaturityDimensionEnum,
    MaturityLevelEnum,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_default_framework_dimensions() -> List[MaturityDimensionDefinition]:
    """Generates standard baseline dimensions and criteria for clinical safety governance."""
    dimensions: List[MaturityDimensionDefinition] = []

    standard_dimensions = [
        (MaturityDimensionEnum.LEADERSHIP_ACCOUNTABILITY, "Leadership & Accountability", "Executive oversight, role clarity, and safety culture commitment."),
        (MaturityDimensionEnum.CLINICAL_RISK_MANAGEMENT, "Clinical Risk Management", "Identification, evaluation, mitigation, and control of clinical safety risks."),
        (MaturityDimensionEnum.INCIDENT_LEARNING, "Incident Learning & Response", "Incident capture, investigation, root cause learning, and systemic prevention."),
        (MaturityDimensionEnum.DECISION_ASSURANCE, "Decision Assurance", "Governance review, decision tracking, and authoritative approval rigor."),
        (MaturityDimensionEnum.IMPLEMENTATION_CHANGE_GOVERNANCE, "Implementation & Change Governance", "Managed rollout, verification, and adoption oversight of governance decisions."),
        (MaturityDimensionEnum.EFFECTIVENESS_BENEFITS_ASSURANCE, "Effectiveness & Benefits Assurance", "Post-closure verification, realization tracking, and outcome validation."),
        (MaturityDimensionEnum.AUDIT_COMPLIANCE_ASSURANCE, "Audit & Compliance Assurance", "Independent auditing, regulatory adherence, and finding remediation."),
        (MaturityDimensionEnum.ORGANIZATIONAL_LEARNING_IMPROVEMENT, "Organizational Learning & Improvement", "Continuous governance evolution, capability maturity, and systemic refinement."),
    ]

    for dim_enum, title, desc in standard_dimensions:
        criteria: List[MaturityCriterion] = [
            MaturityCriterion(
                criterion_id=f"{dim_enum.value[:4].lower()}_c1",
                dimension=dim_enum,
                target_level=MaturityLevelEnum.LEVEL_1_INITIAL,
                title=f"{title} - Initial Awareness",
                description=f"Initial or ad hoc practices observed for {title}.",
                required_evidence_types=["DIRECT_OBSERVATION", "ORGANIZATIONAL_POLICY"],
                verification_requirements="Documented evidence of ad-hoc activity or initial recognition.",
                mandatory=True,
                threshold_percentage=100.0,
            ),
            MaturityCriterion(
                criterion_id=f"{dim_enum.value[:4].lower()}_c2",
                dimension=dim_enum,
                target_level=MaturityLevelEnum.LEVEL_2_DEVELOPING,
                title=f"{title} - Developing Standard",
                description=f"Emergent repeatable processes for {title} in key operational pockets.",
                required_evidence_types=["PHASE_49_INCIDENT", "PHASE_63_RISK", "PHASE_73_IMPLEMENTATION"],
                verification_requirements="Documented repeatable workflows and localized records.",
                mandatory=True,
                threshold_percentage=100.0,
            ),
            MaturityCriterion(
                criterion_id=f"{dim_enum.value[:4].lower()}_c3",
                dimension=dim_enum,
                target_level=MaturityLevelEnum.LEVEL_3_DEFINED,
                title=f"{title} - Defined Organization-Wide Process",
                description=f"Standardized and systematically followed governance process for {title}.",
                required_evidence_types=["PHASE_54_CAPA", "PHASE_70_AUDIT", "PHASE_72_MANAGEMENT_REVIEW"],
                verification_requirements="Authoritative institutional policies and execution records.",
                mandatory=True,
                threshold_percentage=100.0,
            ),
            MaturityCriterion(
                criterion_id=f"{dim_enum.value[:4].lower()}_c4",
                dimension=dim_enum,
                target_level=MaturityLevelEnum.LEVEL_4_MANAGED,
                title=f"{title} - Quantitatively Managed Governance",
                description=f"Quantitatively measured, monitored, and controlled governance performance for {title}.",
                required_evidence_types=["PHASE_71_AUDIT_INTEL", "PHASE_74_ADOPTION", "PHASE_76_BENEFIT"],
                verification_requirements="Quantitative metrics, verified trend records, and metric-based oversight.",
                mandatory=True,
                threshold_percentage=100.0,
            ),
            MaturityCriterion(
                criterion_id=f"{dim_enum.value[:4].lower()}_c5",
                dimension=dim_enum,
                target_level=MaturityLevelEnum.LEVEL_5_CONTINUOUSLY_IMPROVING,
                title=f"{title} - Continuous Governance Improvement",
                description=f"Proactive systemic optimization, feedback loops, and continuous innovation for {title}.",
                required_evidence_types=["PHASE_75_PORTFOLIO", "PHASE_76_BENEFIT", "ORGANIZATIONAL_POLICY"],
                verification_requirements="Demonstrated feedback loop closures and systemic capability evolution.",
                mandatory=True,
                threshold_percentage=100.0,
            ),
        ]

        dimensions.append(
            MaturityDimensionDefinition(
                dimension=dim_enum,
                title=title,
                description=desc,
                weight=1.0,
                criteria=criteria,
            )
        )

    return dimensions


class GovernanceMaturityFrameworkService:
    """Manages clinical safety governance maturity frameworks."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def create_framework(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateFrameworkRequest,
    ) -> GovernanceMaturityFrameworkRecord:
        existing = self.repository.get_framework_by_code_and_version(
            tenant_id=tenant_id,
            framework_code=request.framework_code,
            version=request.version,
        )
        if existing:
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework with code '{request.framework_code}' and version '{request.version}' already exists.",
                status_code=409,
            )

        now = _get_utc_now_str()
        dimensions = request.dimensions if request.dimensions is not None else _get_default_framework_dimensions()

        framework = GovernanceMaturityFrameworkRecord(
            framework_id=f"fw-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            framework_code=request.framework_code,
            name=request.name,
            version=request.version,
            status=FrameworkStatus.DRAFT,
            description=request.description,
            dimensions=dimensions,
            author_id=author_id,
            approved_by=None,
            approval_date=None,
            activated_at=None,
            superseded_by_framework_id=None,
            metadata=request.metadata or {},
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_framework(framework)

    def add_dimension(
        self,
        tenant_id: str,
        framework_id: str,
        request: AddDimensionRequest,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )

        if framework.status not in (FrameworkStatus.DRAFT, FrameworkStatus.SUBMITTED):
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Cannot modify dimensions in status '{framework.status.value}'.",
                status_code=400,
            )

        updated_dimensions = [d for d in framework.dimensions if d.dimension != request.dimension]
        new_dim = MaturityDimensionDefinition(
            dimension=request.dimension,
            title=request.title,
            description=request.description,
            weight=request.weight,
            criteria=request.criteria or [],
        )
        updated_dimensions.append(new_dim)

        now = _get_utc_now_str()
        framework = framework.model_copy(
            update={"dimensions": updated_dimensions, "updated_at": now}
        )
        return self.repository.save_framework(framework)

    def add_criterion(
        self,
        tenant_id: str,
        framework_id: str,
        request: AddCriterionRequest,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )

        if framework.status not in (FrameworkStatus.DRAFT, FrameworkStatus.SUBMITTED):
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Cannot modify criteria in status '{framework.status.value}'.",
                status_code=400,
            )

        dim_found = False
        updated_dimensions = []
        for dim in framework.dimensions:
            if dim.dimension == request.dimension:
                dim_found = True
                criteria = [c for c in dim.criteria if c.criterion_id != request.criterion_id]
                new_crit = MaturityCriterion(
                    criterion_id=request.criterion_id,
                    dimension=request.dimension,
                    target_level=request.target_level,
                    title=request.title,
                    description=request.description,
                    required_evidence_types=request.required_evidence_types,
                    verification_requirements=request.verification_requirements,
                    mandatory=request.mandatory,
                    threshold_percentage=request.threshold_percentage,
                )
                criteria.append(new_crit)
                updated_dimensions.append(dim.model_copy(update={"criteria": criteria}))
            else:
                updated_dimensions.append(dim)

        if not dim_found:
            raise AppException(
                code=ErrorCode.MATURITY_DIMENSION_NOT_FOUND,
                message=f"Dimension '{request.dimension.value}' not found in framework '{framework_id}'.",
                status_code=404,
            )

        now = _get_utc_now_str()
        framework = framework.model_copy(
            update={"dimensions": updated_dimensions, "updated_at": now}
        )
        return self.repository.save_framework(framework)

    def submit_framework(
        self,
        tenant_id: str,
        framework_id: str,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )

        if framework.status != FrameworkStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework in status '{framework.status.value}' cannot be submitted. Only DRAFT frameworks can be submitted.",
                status_code=400,
            )

        now = _get_utc_now_str()
        framework = framework.model_copy(
            update={"status": FrameworkStatus.SUBMITTED, "updated_at": now}
        )
        return self.repository.save_framework(framework)

    def approve_framework(
        self,
        tenant_id: str,
        framework_id: str,
        approver_id: str,
        notes: Optional[str] = None,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )

        if framework.status != FrameworkStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework in status '{framework.status.value}' cannot be approved. Only SUBMITTED frameworks can be approved.",
                status_code=400,
            )

        # Separation of duties: author cannot approve their own framework
        if framework.author_id == approver_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Framework author cannot approve their own framework.",
                status_code=403,
            )

        now = _get_utc_now_str()
        meta = dict(framework.metadata)
        if notes:
            meta["approval_notes"] = notes

        framework = framework.model_copy(
            update={
                "status": FrameworkStatus.APPROVED,
                "approved_by": approver_id,
                "approval_date": now,
                "metadata": meta,
                "updated_at": now,
            }
        )
        return self.repository.save_framework(framework)

    def activate_framework(
        self,
        tenant_id: str,
        framework_id: str,
        notes: Optional[str] = None,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )

        if framework.status != FrameworkStatus.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework in status '{framework.status.value}' cannot be activated. Only APPROVED frameworks can be activated.",
                status_code=400,
            )

        now = _get_utc_now_str()

        # Supersede existing active framework if present
        current_active = self.repository.get_active_framework(tenant_id)
        if current_active and current_active.framework_id != framework_id:
            current_active = current_active.model_copy(
                update={
                    "status": FrameworkStatus.SUPERSEDED,
                    "superseded_by_framework_id": framework_id,
                    "updated_at": now,
                }
            )
            self.repository.save_framework(current_active)

        meta = dict(framework.metadata)
        if notes:
            meta["activation_notes"] = notes

        framework = framework.model_copy(
            update={
                "status": FrameworkStatus.ACTIVE,
                "activated_at": now,
                "metadata": meta,
                "updated_at": now,
            }
        )
        return self.repository.save_framework(framework)

    def get_framework(
        self,
        tenant_id: str,
        framework_id: str,
    ) -> GovernanceMaturityFrameworkRecord:
        framework = self.repository.get_framework(framework_id)
        if not framework or framework.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework '{framework_id}' was not found.",
                status_code=404,
            )
        return framework

    def list_frameworks(
        self,
        tenant_id: str,
        status: Optional[FrameworkStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceMaturityFrameworkRecord]:
        return self.repository.list_frameworks(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )

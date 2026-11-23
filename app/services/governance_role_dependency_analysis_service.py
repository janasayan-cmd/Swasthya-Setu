"""Phase 85: Single-Person Dependency and Concentration Analysis Service.

Analyzes critical governance responsibilities to identify single points of failure,
key-person bottlenecks, and excessive personnel concentration across roles.
"""

import uuid
from typing import Dict, List, Optional, Tuple
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    CriticalityTier,
    DependencyRiskRating,
)
from app.schemas.governance_role_dependency_analysis import (
    PersonnelConcentrationRecord,
    RunDependencyAnalysisRequest,
    SinglePersonDependencyRecord,
)


class GovernanceRoleDependencyAnalysisService:
    """Service for detecting single-person dependencies and bottleneck risks."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def run_dependency_analysis(
        self,
        tenant_id: str,
        request: RunDependencyAnalysisRequest,
    ) -> Tuple[List[SinglePersonDependencyRecord], List[PersonnelConcentrationRecord]]:
        responsibilities = self.repository.list_responsibilities(tenant_id)
        single_person_deps: List[SinglePersonDependencyRecord] = []
        user_role_counts: Dict[str, Dict] = {}

        for resp in responsibilities:
            # Check tier eligibility
            if not request.include_tier2 and resp.criticality_tier == CriticalityTier.TIER_2_CRITICAL:
                continue

            # Track primary user
            p_id = resp.primary_owner_id
            if p_id not in user_role_counts:
                user_role_counts[p_id] = {
                    "name": resp.primary_owner_name,
                    "t1_primary": 0,
                    "t1_backup": 0,
                    "total": 0,
                    "resp_ids": set(),
                }
            user_role_counts[p_id]["total"] += 1
            user_role_counts[p_id]["resp_ids"].add(resp.responsibility_id)
            if resp.criticality_tier == CriticalityTier.TIER_1_ESSENTIAL:
                user_role_counts[p_id]["t1_primary"] += 1

            # Fetch coverage arrangement
            coverage = self.repository.get_coverage_by_responsibility(
                resp.responsibility_id, tenant_id
            )
            verified_backups_count = 0
            vulnerabilities = []

            if not coverage or not coverage.designated_backups:
                vulnerabilities.append("No designated backup arrangement exists.")
            else:
                for b in coverage.designated_backups:
                    # Track backup user
                    b_id = b.backup_user_id
                    if b_id not in user_role_counts:
                        user_role_counts[b_id] = {
                            "name": b.backup_user_name,
                            "t1_primary": 0,
                            "t1_backup": 0,
                            "total": 0,
                            "resp_ids": set(),
                        }
                    user_role_counts[b_id]["total"] += 1
                    user_role_counts[b_id]["resp_ids"].add(resp.responsibility_id)
                    if resp.criticality_tier == CriticalityTier.TIER_1_ESSENTIAL:
                        user_role_counts[b_id]["t1_backup"] += 1

                    if b.capability_verified and b.authorization_verified and b.is_available:
                        verified_backups_count += 1
                    else:
                        vulnerabilities.append(
                            f"Backup '{b.backup_user_name}' is unverified or unavailable."
                        )

            is_single_person_dependent = (verified_backups_count == 0)
            if is_single_person_dependent:
                if resp.criticality_tier == CriticalityTier.TIER_1_ESSENTIAL:
                    risk_rating = DependencyRiskRating.CRITICAL
                    vulnerabilities.append("Zero verified backups for Essential (Tier 1) governance responsibility.")
                elif resp.criticality_tier == CriticalityTier.TIER_2_CRITICAL:
                    risk_rating = DependencyRiskRating.HIGH
                    vulnerabilities.append("Zero verified backups for Critical (Tier 2) governance responsibility.")
                else:
                    risk_rating = DependencyRiskRating.MEDIUM
            else:
                if verified_backups_count == 1 and resp.criticality_tier == CriticalityTier.TIER_1_ESSENTIAL:
                    risk_rating = DependencyRiskRating.MEDIUM
                    vulnerabilities.append("Single backup redundancy presents moderate fragility.")
                else:
                    risk_rating = DependencyRiskRating.LOW

            single_person_deps.append(
                SinglePersonDependencyRecord(
                    dependency_id=f"dep-{uuid.uuid4().hex[:12]}",
                    tenant_id=tenant_id,
                    responsibility_id=resp.responsibility_id,
                    role_title=resp.role_title,
                    primary_owner_id=resp.primary_owner_id,
                    verified_backups_count=verified_backups_count,
                    is_single_person_dependent=is_single_person_dependent,
                    risk_rating=risk_rating,
                    vulnerabilities=vulnerabilities,
                )
            )

        # Build personnel concentration bottlenecks
        concentrations: List[PersonnelConcentrationRecord] = []
        for u_id, data in user_role_counts.items():
            total = data["total"]
            is_bottleneck = total >= request.bottleneck_threshold
            if total >= 5:
                rating = DependencyRiskRating.CRITICAL
            elif total >= request.bottleneck_threshold:
                rating = DependencyRiskRating.HIGH
            elif total >= 2:
                rating = DependencyRiskRating.MEDIUM
            else:
                rating = DependencyRiskRating.LOW

            concentrations.append(
                PersonnelConcentrationRecord(
                    concentration_id=f"conc-{uuid.uuid4().hex[:12]}",
                    tenant_id=tenant_id,
                    user_id=u_id,
                    user_name=data["name"],
                    tier1_primary_roles_count=data["t1_primary"],
                    tier1_backup_roles_count=data["t1_backup"],
                    total_critical_roles_covered=total,
                    associated_responsibility_ids=list(data["resp_ids"]),
                    risk_rating=rating,
                    is_bottleneck=is_bottleneck,
                )
            )

        return single_person_deps, concentrations


_dependency_analysis_service: Optional[GovernanceRoleDependencyAnalysisService] = None


def get_governance_role_dependency_analysis_service() -> GovernanceRoleDependencyAnalysisService:
    global _dependency_analysis_service
    if _dependency_analysis_service is None:
        _dependency_analysis_service = GovernanceRoleDependencyAnalysisService(
            get_governance_role_coverage_repository()
        )
    return _dependency_analysis_service

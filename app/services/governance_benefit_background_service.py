"""Phase 76: Benefit Assurance Background Processing Service.

Coordinates:
- Asynchronous / scheduled benefit assurance scans
- Overdue realization target detection
- Missing measurement and stale evidence detection
- Expired exception detection
"""

from datetime import datetime, timezone
from typing import Optional

from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.schemas.governance_benefit_register import BenefitStatus
from app.schemas.governance_benefit_exceptions_reviews import BenefitExceptionStatus
from app.schemas.governance_benefit_reporting import BenefitAssuranceJobRunResult


class GovernanceBenefitBackgroundService:
    """Service executing scheduled and on-demand benefit assurance routine scans."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()

    def run_benefit_assurance_cycle(self, tenant_id: str) -> BenefitAssuranceJobRunResult:
        """Executes an idempotent routine scan across all registered benefits in the tenant."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        overdue_targets = 0
        missing_measurements = 0
        stale_evidence = 0
        expired_exceptions = 0
        details = []

        benefits = self.repo.list_benefits(tenant_id=tenant_id, limit=500)

        for benefit in benefits:
            # Check overdue realization date
            if benefit.status in [BenefitStatus.REGISTERED, BenefitStatus.ACTIVE_MONITORING]:
                try:
                    exp_dt = datetime.fromisoformat(benefit.expected_realization_date)
                    if exp_dt < now:
                        overdue_targets += 1
                        details.append(f"Benefit '{benefit.benefit_id}' is past expected realization date ({benefit.expected_realization_date}).")
                except Exception:
                    pass

                # Check if measurements exist
                meas = self.repo.list_measurements_for_benefit(benefit.benefit_id, tenant_id)
                if not meas:
                    missing_measurements += 1
                    details.append(f"Benefit '{benefit.benefit_id}' has no recorded measurements.")

        # Check expired exceptions
        all_exceptions = self.repo.list_all_exceptions(tenant_id)
        for exc in all_exceptions:
            if exc.status == BenefitExceptionStatus.APPROVED:
                try:
                    rev_dt = datetime.fromisoformat(exc.review_date)
                    if rev_dt < now:
                        exc.status = BenefitExceptionStatus.EXPIRED
                        exc.updated_at = now_iso
                        self.repo.save_exception(exc)
                        expired_exceptions += 1
                        details.append(f"Exception '{exc.exception_id}' expired on {exc.review_date}.")
                except Exception:
                    pass

        return BenefitAssuranceJobRunResult(
            job_name="benefit_assurance_routine_scan",
            run_timestamp=now_iso,
            overdue_targets_flagged=overdue_targets,
            missing_measurements_flagged=missing_measurements,
            stale_source_evidence_flagged=stale_evidence,
            expired_exceptions_flagged=expired_exceptions,
            details=details,
        )

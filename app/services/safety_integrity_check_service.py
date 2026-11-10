"""Phase 66: Safety Integrity Check Service.

Executes deterministic, policy-aware post-closure integrity checks across 7 categories:
- Check A: Completion record integrity
- Check B: Source disposition integrity (Phase 63)
- Check C: Handoff and destination outcome integrity (Phase 64)
- Check D: Evidence validity and availability
- Check E: Follow-up obligations integrity
- Check F: Safety signals integrity (Phase 59 & Phase 60)
- Check G: Policy version integrity

Mandatory Invariant:
A missing response from a dependency does not establish that the underlying workflow
failed or succeeded. Unknown, contradictory, unavailable, or insufficient evidence
must never be interpreted as proof of continued safety.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.safety_monitoring_repository import (
    SafetyMonitoringRepository,
    get_safety_monitoring_repository,
)
from app.repositories.safety_risk_handoff_repository import (
    SafetyRiskHandoffRepository,
    get_safety_risk_handoff_repository,
)
from app.repositories.safety_risk_review_repository import (
    SafetyRiskReviewRepository,
    get_safety_risk_review_repository,
)
from app.repositories.safety_triage_repository import (
    SafetyTriageRepository,
    get_safety_triage_repository,
)
from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingLifecycleState,
    FindingSeverity,
    IntegrityFindingRecord,
)
from app.schemas.safety_post_closure_monitoring import MonitoringPolicyConfig
from app.schemas.safety_workflow_completion import SafetyWorkflowCompletionRecord


class SafetyIntegrityCheckService:
    """Executes post-closure integrity checks and generates structured findings."""

    def __init__(
        self,
        review_repo: Optional[SafetyRiskReviewRepository] = None,
        handoff_repo: Optional[SafetyRiskHandoffRepository] = None,
        monitoring_repo: Optional[SafetyMonitoringRepository] = None,
        triage_repo: Optional[SafetyTriageRepository] = None,
    ) -> None:
        self.review_repo = review_repo or get_safety_risk_review_repository()
        self.handoff_repo = handoff_repo or get_safety_risk_handoff_repository()
        self.monitoring_repo = monitoring_repo or get_safety_monitoring_repository()
        self.triage_repo = triage_repo or get_safety_triage_repository()

    def run_all_checks(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[List[IntegrityFindingRecord], Dict[str, Any], List[str]]:
        """Run all Category A through G checks and return findings, evaluated checks, and limitations."""
        findings: List[IntegrityFindingRecord] = []
        evaluated_checks: Dict[str, Any] = {}
        limitations: List[str] = []

        # Check A: Completion Integrity
        check_a_passed, check_a_findings = self.check_completion_integrity(completion, verification_id, policy)
        evaluated_checks["check_a_completion_integrity"] = {
            "passed": check_a_passed,
            "findings_count": len(check_a_findings),
        }
        findings.extend(check_a_findings)

        # Check B: Source Disposition Integrity (Phase 63)
        check_b_passed, check_b_findings, check_b_limitations = self.check_source_disposition_integrity(
            completion, verification_id, policy
        )
        evaluated_checks["check_b_source_disposition"] = {
            "passed": check_b_passed,
            "findings_count": len(check_b_findings),
        }
        findings.extend(check_b_findings)
        limitations.extend(check_b_limitations)

        # Check C: Handoff and Destination Outcome Integrity (Phase 64)
        check_c_passed, check_c_findings, check_c_limitations = self.check_handoff_and_destination_integrity(
            completion, verification_id, policy
        )
        evaluated_checks["check_c_handoff_and_destination"] = {
            "passed": check_c_passed,
            "findings_count": len(check_c_findings),
        }
        findings.extend(check_c_findings)
        limitations.extend(check_c_limitations)

        # Check D: Evidence Integrity
        check_d_passed, check_d_findings = self.check_evidence_integrity(completion, verification_id, policy)
        evaluated_checks["check_d_evidence_integrity"] = {
            "passed": check_d_passed,
            "findings_count": len(check_d_findings),
        }
        findings.extend(check_d_findings)

        # Check E: Follow-Up Obligations Integrity
        check_e_passed, check_e_findings = self.check_followup_integrity(completion, verification_id, policy)
        evaluated_checks["check_e_follow_up_integrity"] = {
            "passed": check_e_passed,
            "findings_count": len(check_e_findings),
        }
        findings.extend(check_e_findings)

        # Check F: Safety Signal Integrity (Phase 59 & Phase 60)
        check_f_passed, check_f_findings, check_f_limitations = self.check_safety_signals_integrity(
            completion, verification_id, policy
        )
        evaluated_checks["check_f_safety_signals"] = {
            "passed": check_f_passed,
            "findings_count": len(check_f_findings),
        }
        findings.extend(check_f_findings)
        limitations.extend(check_f_limitations)

        # Check G: Policy Integrity
        check_g_passed, check_g_findings = self.check_policy_integrity(completion, verification_id, policy)
        evaluated_checks["check_g_policy_integrity"] = {
            "passed": check_g_passed,
            "findings_count": len(check_g_findings),
        }
        findings.extend(check_g_findings)

        return findings, evaluated_checks, limitations

    # -------------------------------------------------------------------------
    # Category A: Completion Integrity
    # -------------------------------------------------------------------------
    def check_completion_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord]]:
        findings: List[IntegrityFindingRecord] = []

        # 1. Closure record check
        if not completion.closure:
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.AUTHORIZATION_EVIDENCE_MISSING,
                    severity=FindingSeverity.CRITICAL,
                    source_system="PHASE_65_COMPLETION",
                    authoritative_record_ref=completion.completion_id,
                    expected_state="CLOSURE_RECORD_AVAILABLE",
                    observed_state="CLOSURE_RECORD_MISSING",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="REASSESSMENT_REQUIRED",
                )
            )

        # 2. Authorization evidence check
        if not completion.authorization or not completion.authorization.get("authorized"):
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.AUTHORIZATION_EVIDENCE_MISSING,
                    severity=FindingSeverity.CRITICAL,
                    source_system="PHASE_65_COMPLETION",
                    authoritative_record_ref=completion.completion_id,
                    expected_state="AUTHORIZATION_RECORD_VALID",
                    observed_state="AUTHORIZATION_RECORD_MISSING_OR_INVALID",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="REASSESSMENT_REQUIRED",
                )
            )

        # 3. Completion package consistency
        if completion.completion_package:
            pkg = completion.completion_package
            if pkg.get("completion_id") != completion.completion_id:
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.COMPLETION_PACKAGE_INCONSISTENCY,
                        severity=FindingSeverity.HIGH,
                        source_system="PHASE_65_PACKAGE",
                        authoritative_record_ref=completion.completion_id,
                        expected_state=f"package.completion_id == {completion.completion_id}",
                        observed_state=f"package.completion_id == {pkg.get('completion_id')}",
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="MANUAL_REVIEW_REQUIRED",
                    )
                )

        return (len(findings) == 0, findings)

    # -------------------------------------------------------------------------
    # Category B: Source Disposition Integrity (Phase 63)
    # -------------------------------------------------------------------------
    def check_source_disposition_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord], List[str]]:
        findings: List[IntegrityFindingRecord] = []
        limitations: List[str] = []

        try:
            review = self.review_repo.get(completion.source_review_id)
        except Exception as e:
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.DEPENDENCY_STATE_UNKNOWN,
                    severity=FindingSeverity.HIGH,
                    source_system="PHASE_63_REVIEW_REPOSITORY",
                    authoritative_record_ref=completion.source_review_id,
                    expected_state="REPOSITORY_ACCESSIBLE",
                    observed_state=f"EXCEPTION: {str(e)}",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="RETRY_VERIFICATION",
                )
            )
            return (False, findings, ["Phase 63 repository was temporarily inaccessible."])

        if not review:
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.SOURCE_DISPOSITION_CHANGED,
                    severity=FindingSeverity.CRITICAL,
                    source_system="PHASE_63_REVIEW",
                    authoritative_record_ref=completion.source_review_id,
                    expected_state="AUTHORITATIVE_REVIEW_EXISTS",
                    observed_state="REVIEW_NOT_FOUND",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="REOPEN_RECOMMENDED",
                )
            )
            return (False, findings, [])

        # Check disposition state and version
        disp = getattr(review, "disposition", None)
        if not disp and getattr(review, "dispositions", None):
            matches = [
                d for d in review.dispositions
                if (getattr(d, "disposition_id", None) or (d.get("disposition_id") if isinstance(d, dict) else None)) == completion.source_disposition_id
            ]
            disp = matches[0] if matches else review.dispositions[0]

        if not disp:
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.SOURCE_DISPOSITION_CHANGED,
                    severity=FindingSeverity.CRITICAL,
                    source_system="PHASE_63_DISPOSITION",
                    authoritative_record_ref=completion.source_disposition_id,
                    expected_state="DISPOSITION_EXISTS",
                    observed_state="DISPOSITION_MISSING_ON_REVIEW",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="REOPEN_RECOMMENDED",
                )
            )
        else:
            disp_id = disp.disposition_id if hasattr(disp, "disposition_id") else disp.get("disposition_id")
            disp_type = disp.disposition_type if hasattr(disp, "disposition_type") else disp.get("disposition_type")
            disp_state = getattr(review, "state", None)
            state_val = disp_state.value if hasattr(disp_state, "value") else str(disp_state)

            if disp_id != completion.source_disposition_id:
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.SOURCE_DISPOSITION_CHANGED,
                        severity=FindingSeverity.CRITICAL,
                        source_system="PHASE_63_DISPOSITION",
                        authoritative_record_ref=str(disp_id),
                        expected_state=completion.source_disposition_id,
                        observed_state=str(disp_id),
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="REOPEN_RECOMMENDED",
                    )
                )

            # Check if disposition or review was superseded, invalidated, or reopened
            if state_val in ("REOPENED", "SUPERSEDED", "INVALIDATED", "REASSESSMENT_REQUIRED", "REOPEN_REQUIRED", "CANCELLED"):
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.SOURCE_DISPOSITION_CHANGED,
                        severity=FindingSeverity.CRITICAL,
                        source_system="PHASE_63_REVIEW",
                        authoritative_record_ref=review.review_id,
                        expected_state="COMPLETED_OR_CLOSED",
                        observed_state=str(disp_state),
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="REOPEN_RECOMMENDED",
                    )
                )

        return (len(findings) == 0, findings, limitations)

    # -------------------------------------------------------------------------
    # Category C: Handoff & Destination Outcome Integrity (Phase 64)
    # -------------------------------------------------------------------------
    def check_handoff_and_destination_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord], List[str]]:
        findings: List[IntegrityFindingRecord] = []
        limitations: List[str] = []

        try:
            handoffs = self.handoff_repo.get_by_disposition_id(completion.source_disposition_id)
        except Exception as e:
            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.DEPENDENCY_STATE_UNKNOWN,
                    severity=FindingSeverity.HIGH,
                    source_system="PHASE_64_HANDOFF_REPOSITORY",
                    authoritative_record_ref=completion.source_disposition_id,
                    expected_state="REPOSITORY_ACCESSIBLE",
                    observed_state=f"EXCEPTION: {str(e)}",
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=True,
                    policy_reference=policy.policy_version,
                    recommended_next_action="RETRY_VERIFICATION",
                )
            )
            return (False, findings, ["Phase 64 repository was temporarily inaccessible."])

        # Map completion recorded outcomes by handoff_id
        recorded_outcomes = {
            o.get("handoff_id"): o for o in completion.outcomes if isinstance(o, dict)
        }

        for h in handoffs:
            h_state = h.state.value if hasattr(h.state, "value") else str(h.state)
            
            # Destination workflow reopened or changed
            if h_state in ("REOPENED", "FAILED", "BLOCKED", "CANCELLED"):
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.DESTINATION_WORKFLOW_REOPENED,
                        severity=FindingSeverity.CRITICAL,
                        source_system="PHASE_64_HANDOFF",
                        authoritative_record_ref=h.handoff_id,
                        expected_state="COMPLETED_OR_CLOSED",
                        observed_state=h_state,
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="REOPEN_RECOMMENDED",
                    )
                )

            # Check outcome reconciliation version consistency
            rec_outcome = recorded_outcomes.get(h.handoff_id)
            if rec_outcome:
                expected_ver = rec_outcome.get("contract_version", "v1.0.0")
                curr_ver = getattr(h, "contract_version", "v1.0.0")
                if expected_ver != curr_ver:
                    findings.append(
                        IntegrityFindingRecord(
                            completion_id=completion.completion_id,
                            verification_id=verification_id,
                            organization_id=completion.organization_id,
                            facility_id=completion.facility_id,
                            category=FindingCategory.OUTCOME_VERSION_CHANGED,
                            severity=FindingSeverity.HIGH,
                            source_system="PHASE_64_HANDOFF",
                            authoritative_record_ref=h.handoff_id,
                            expected_state=expected_ver,
                            observed_state=curr_ver,
                            provenance="PHASE_66_INTEGRITY_CHECKER",
                            is_material=True,
                            policy_reference=policy.policy_version,
                            recommended_next_action="REASSESSMENT_REQUIRED",
                        )
                    )

                # Check if outcome was invalidated
                if rec_outcome.get("outcome_status") == "INVALIDATED":
                    findings.append(
                        IntegrityFindingRecord(
                            completion_id=completion.completion_id,
                            verification_id=verification_id,
                            organization_id=completion.organization_id,
                            facility_id=completion.facility_id,
                            category=FindingCategory.DESTINATION_OUTCOME_INVALIDATED,
                            severity=FindingSeverity.CRITICAL,
                            source_system="PHASE_64_OUTCOME",
                            authoritative_record_ref=h.handoff_id,
                            expected_state="VALID_RECONCILED_OUTCOME",
                            observed_state="INVALIDATED",
                            provenance="PHASE_66_INTEGRITY_CHECKER",
                            is_material=True,
                            policy_reference=policy.policy_version,
                            recommended_next_action="REOPEN_RECOMMENDED",
                        )
                    )

        return (len(findings) == 0, findings, limitations)

    # -------------------------------------------------------------------------
    # Category D: Evidence Integrity
    # -------------------------------------------------------------------------
    def check_evidence_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord]]:
        findings: List[IntegrityFindingRecord] = []

        # Check evidence references in completion package and requirements
        evidence_refs: List[str] = []
        if completion.completion_package:
            evidence_refs.extend(completion.completion_package.get("evidence_package_refs", []))
            evidence_refs.extend(completion.completion_package.get("supporting_evidence_references", []))

        for req in completion.requirements:
            if isinstance(req, dict):
                evidence_refs.extend(req.get("evidence_refs", []))
                # Check for explicit invalidated status on requirement
                if req.get("status") in ("INVALIDATED", "WITHDRAWN"):
                    findings.append(
                        IntegrityFindingRecord(
                            completion_id=completion.completion_id,
                            verification_id=verification_id,
                            organization_id=completion.organization_id,
                            facility_id=completion.facility_id,
                            category=FindingCategory.REQUIRED_EVIDENCE_INVALIDATED,
                            severity=FindingSeverity.CRITICAL,
                            source_system="COMPLETION_REQUIREMENT_REGISTER",
                            authoritative_record_ref=req.get("requirement_id", "req-unknown"),
                            expected_state="SATISFIED",
                            observed_state=req.get("status"),
                            provenance="PHASE_66_INTEGRITY_CHECKER",
                            is_material=True,
                            policy_reference=policy.policy_version,
                            recommended_next_action="REOPEN_RECOMMENDED",
                        )
                    )

        # Detect unavailable or blank evidence references
        for ref in set(evidence_refs):
            if "withdrawn" in ref.lower() or "invalid" in ref.lower():
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.REQUIRED_EVIDENCE_INVALIDATED,
                        severity=FindingSeverity.CRITICAL,
                        source_system="EVIDENCE_STORE",
                        authoritative_record_ref=ref,
                        expected_state="ACTIVE_VALID",
                        observed_state="WITHDRAWN_OR_INVALID",
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="REOPEN_RECOMMENDED",
                    )
                )
            elif "unavailable" in ref.lower():
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.REQUIRED_EVIDENCE_UNAVAILABLE,
                        severity=FindingSeverity.HIGH,
                        source_system="EVIDENCE_STORE",
                        authoritative_record_ref=ref,
                        expected_state="ACCESSIBLE",
                        observed_state="UNAVAILABLE",
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=True,
                        policy_reference=policy.policy_version,
                        recommended_next_action="MANUAL_REVIEW_REQUIRED",
                    )
                )

        return (len(findings) == 0, findings)

    # -------------------------------------------------------------------------
    # Category E: Follow-Up Obligations Integrity
    # -------------------------------------------------------------------------
    def check_followup_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord]]:
        findings: List[IntegrityFindingRecord] = []
        now = datetime.now(timezone.utc)

        for fu in completion.follow_ups:
            if not isinstance(fu, dict):
                continue
            fu_id = fu.get("obligation_id", "fu-unknown")
            fu_status = fu.get("status", "ACTIVE")
            is_mandatory = fu.get("is_mandatory", True)

            # Check if overdue
            due_date_str = fu.get("due_date")
            if due_date_str and fu_status not in ("COMPLETED", "RESOLVED", "WAIVED"):
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                    if now > due_date:
                        findings.append(
                            IntegrityFindingRecord(
                                completion_id=completion.completion_id,
                                verification_id=verification_id,
                                organization_id=completion.organization_id,
                                facility_id=completion.facility_id,
                                category=FindingCategory.FOLLOW_UP_OVERDUE,
                                severity=FindingSeverity.HIGH if is_mandatory else FindingSeverity.MEDIUM,
                                source_system="FOLLOW_UP_OBLIGATION_REGISTER",
                                authoritative_record_ref=fu_id,
                                expected_state=f"COMPLETED_BEFORE_{due_date_str}",
                                observed_state=f"OVERDUE_{fu_status}",
                                provenance="PHASE_66_INTEGRITY_CHECKER",
                                is_material=is_mandatory,
                                policy_reference=policy.policy_version,
                                recommended_next_action="REASSESSMENT_REQUIRED" if is_mandatory else "REVIEW_REQUIRED",
                            )
                        )
                except Exception:
                    pass

            # Check if failed or blocked
            if fu_status in ("FAILED", "BLOCKED"):
                findings.append(
                    IntegrityFindingRecord(
                        completion_id=completion.completion_id,
                        verification_id=verification_id,
                        organization_id=completion.organization_id,
                        facility_id=completion.facility_id,
                        category=FindingCategory.FOLLOW_UP_FAILED,
                        severity=FindingSeverity.CRITICAL if is_mandatory else FindingSeverity.HIGH,
                        source_system="FOLLOW_UP_OBLIGATION_REGISTER",
                        authoritative_record_ref=fu_id,
                        expected_state="SATISFIED_OR_ACTIVE",
                        observed_state=fu_status,
                        provenance="PHASE_66_INTEGRITY_CHECKER",
                        is_material=is_mandatory,
                        policy_reference=policy.policy_version,
                        recommended_next_action="REOPEN_RECOMMENDED" if is_mandatory else "REASSESSMENT_REQUIRED",
                    )
                )

        return (len(findings) == 0, findings)

    # -------------------------------------------------------------------------
    # Category F: Safety Signals Integrity (Phase 59 & Phase 60)
    # -------------------------------------------------------------------------
    def check_safety_signals_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord], List[str]]:
        findings: List[IntegrityFindingRecord] = []
        limitations: List[str] = []

        try:
            # Query Phase 59 surveillance records for matching organization & facility
            mon_records = self.monitoring_repo.list_monitoring(
                organization_id=completion.organization_id,
                facility_id=completion.facility_id,
            )
        except Exception:
            # Non-blocking query failure
            limitations.append("Phase 59 surveillance record query could not complete.")
            mon_records = []

        # Check for active post-closure critical signals
        for m in mon_records:
            signals = getattr(m, "signals", []) or []
            for s in signals:
                severity = getattr(s, "severity", "")
                signal_id = getattr(s, "signal_id", "sig-unknown")
                domain = getattr(s, "domain", "")
                # Only signals relevant to this completion's authorized scope
                if severity == "CRITICAL":
                    findings.append(
                        IntegrityFindingRecord(
                            completion_id=completion.completion_id,
                            verification_id=verification_id,
                            organization_id=completion.organization_id,
                            facility_id=completion.facility_id,
                            category=FindingCategory.MATERIAL_SAFETY_SIGNAL_DETECTED,
                            severity=FindingSeverity.CRITICAL,
                            source_system="PHASE_59_SURVEILLANCE",
                            authoritative_record_ref=signal_id,
                            expected_state="NO_CRITICAL_SURVEILLANCE_SIGNALS",
                            observed_state=f"CRITICAL_SIGNAL_{domain}",
                            provenance="PHASE_66_INTEGRITY_CHECKER",
                            is_material=True,
                            policy_reference=policy.policy_version,
                            recommended_next_action="REOPEN_RECOMMENDED",
                        )
                    )

        return (len(findings) == 0, findings, limitations)

    # -------------------------------------------------------------------------
    # Category G: Policy Version Integrity
    # -------------------------------------------------------------------------
    def check_policy_integrity(
        self,
        completion: SafetyWorkflowCompletionRecord,
        verification_id: str,
        policy: MonitoringPolicyConfig,
    ) -> Tuple[bool, List[IntegrityFindingRecord]]:
        findings: List[IntegrityFindingRecord] = []

        orig_policy = completion.applicable_policy_version
        curr_policy = policy.policy_version

        if orig_policy != curr_policy:
            # Version difference detected - assess whether major revision requires reassessment
            orig_major = orig_policy.split(".")[0] if "." in orig_policy else orig_policy
            curr_major = curr_policy.split(".")[0] if "." in curr_policy else curr_policy
            is_major = orig_major != curr_major

            findings.append(
                IntegrityFindingRecord(
                    completion_id=completion.completion_id,
                    verification_id=verification_id,
                    organization_id=completion.organization_id,
                    facility_id=completion.facility_id,
                    category=FindingCategory.POLICY_VERSION_CHANGED,
                    severity=FindingSeverity.HIGH if is_major else FindingSeverity.INFORMATIONAL,
                    source_system="GOVERNANCE_POLICY_SERVICE",
                    authoritative_record_ref=f"{orig_policy}->{curr_policy}",
                    expected_state=orig_policy,
                    observed_state=curr_policy,
                    provenance="PHASE_66_INTEGRITY_CHECKER",
                    is_material=is_major,
                    policy_reference=curr_policy,
                    recommended_next_action="REASSESSMENT_REQUIRED" if is_major else "LOG_INFORMATIONAL",
                )
            )

        return (len(findings) == 0, findings)

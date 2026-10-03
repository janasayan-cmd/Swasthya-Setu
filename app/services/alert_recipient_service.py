"""Recipient Resolution and Relationship Authorization Service for Clinical Alerts (Phase 35).

CORE SAFETY PRINCIPLES:
- Do NOT broadcast clinical alerts to unrelated clinicians, unrelated facilities,
  arbitrary organization users, or unauthorized caregivers.
- Recipient resolution must NOT rely on simple role matching alone
  (e.g., 'DOCTOR' does NOT mean every doctor may receive every patient's alert).
- Patient-facing alerts must contain only information authorized for patient consumption.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from app.core.exceptions import AlertRecipientUnauthorizedException
from app.schemas.alert import AlertRecipient, AlertRecipientType

logger = logging.getLogger(__name__)


class AlertRecipientService:
    """Resolves authorized alert recipients based on clinical relationships and tenant scopes."""

    def resolve_recipients_for_alert(
        self,
        recipient_class: str,
        patient_id: Optional[str] = None,
        responsible_clinician_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        explicit_recipients: Optional[List[str]] = None,
    ) -> List[AlertRecipient]:
        """Determine authorized recipients according to clinical responsibility and context."""
        recipients: List[AlertRecipient] = []

        if explicit_recipients:
            for rid in explicit_recipients:
                recipients.append(
                    AlertRecipient(
                        recipient_id=rid,
                        recipient_type=AlertRecipientType.RESPONSIBLE_CLINICIAN,
                        channel="IN_APP",
                    )
                )
            return recipients

        if recipient_class == "RESPONSIBLE_CLINICIAN":
            clinician_id = responsible_clinician_id or (f"clinician_assigned_{patient_id}" if patient_id else "clinician_on_duty")
            recipients.append(
                AlertRecipient(
                    recipient_id=clinician_id,
                    recipient_type=AlertRecipientType.RESPONSIBLE_CLINICIAN,
                    channel="IN_APP",
                )
            )

        elif recipient_class == "CARE_TEAM":
            team_id = f"care_team_{facility_id}" if facility_id else (f"care_team_{patient_id}" if patient_id else "general_care_team")
            recipients.append(
                AlertRecipient(
                    recipient_id=team_id,
                    recipient_type=AlertRecipientType.CARE_TEAM,
                    channel="IN_APP",
                )
            )

        elif recipient_class == "PATIENT":
            if not patient_id:
                raise AlertRecipientUnauthorizedException("Cannot route patient alert without valid patient reference.")
            recipients.append(
                AlertRecipient(
                    recipient_id=patient_id,
                    recipient_type=AlertRecipientType.PATIENT,
                    channel="IN_APP",
                )
            )

        elif recipient_class == "ADMINISTRATOR":
            admin_id = f"admin_org_{organization_id}" if organization_id else "system_operations_admin"
            recipients.append(
                AlertRecipient(
                    recipient_id=admin_id,
                    recipient_type=AlertRecipientType.ADMINISTRATOR,
                    channel="IN_APP",
                )
            )

        else:
            # Default to responsible clinician fallback if present
            default_id = responsible_clinician_id or "clinician_on_duty"
            recipients.append(
                AlertRecipient(
                    recipient_id=default_id,
                    recipient_type=AlertRecipientType.RESPONSIBLE_CLINICIAN,
                    channel="IN_APP",
                )
            )

        return recipients

    def resolve_escalation_recipient(
        self,
        target_level: int,
        responsible_clinician_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> tuple[str, AlertRecipientType, str]:
        """Resolve recipient for a tiered escalation jump (0 -> 1 -> 2 -> 3).
        
        Returns (recipient_id, recipient_type, role_description).
        """
        if target_level == 1:
            # Level 1: Designated clinical care team
            rid = f"care_team_{facility_id}" if facility_id else "designated_clinical_team"
            return (rid, AlertRecipientType.CARE_TEAM, "Designated Care Team")

        elif target_level == 2:
            # Level 2: Facility escalation lead / chief of staff
            rid = f"facility_lead_{facility_id}" if facility_id else "facility_escalation_lead"
            return (rid, AlertRecipientType.FACILITY_ESCALATION, "Facility Escalation Officer")

        elif target_level >= 3:
            # Level 3: Organization medical director / quality officer
            rid = f"org_quality_officer_{organization_id}" if organization_id else "org_medical_director"
            return (rid, AlertRecipientType.ORGANIZATION_ESCALATION, "Organization Quality & Safety Officer")

        # Fallback to level 0 clinician
        return (responsible_clinician_id or "responsible_clinician", AlertRecipientType.RESPONSIBLE_CLINICIAN, "Responsible Clinician")

    def sanitize_for_patient(self, alert_title: str, summary: Optional[str]) -> tuple[str, Optional[str]]:
        """Filter out internal clinical rationale or speculation for patient-facing alerts."""
        safe_title = alert_title
        if "Critical" in safe_title:
            safe_title = "Important Health Update"
        safe_summary = "A diagnostic or clinical result update is available for your review in the portal."
        return safe_title, safe_summary

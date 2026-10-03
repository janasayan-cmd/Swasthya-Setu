"""Phase 33 — Patient Insurance Coverage Schemas.

CRITICAL CLINICAL BOUNDARIES:
- INSURANCE ≠ CLINICAL DECISION
- INSURANCE ELIGIBILITY ≠ CLINICAL ELIGIBILITY
- PATIENT ≠ SUBSCRIBER (patient can be dependent, subscriber, or covered member)
- SENSITIVE IDENTIFIERS MUST NOT BE EXPOSED UNNECESSARILY IN LOGS/AUDIT
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoverageStatus(str, Enum):
    """Database-contract coverage states."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"
    TERMINATED = "TERMINATED"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"


class RelationshipType(str, Enum):
    """Relationship of patient to subscriber/policy-holder."""
    SELF = "SELF"
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    DEPENDENT = "DEPENDENT"
    OTHER = "OTHER"


def mask_identifier(val: Optional[str]) -> str:
    """Mask insurance identifier for privacy-safe logging and response views."""
    if not val:
        return ""
    if len(val) <= 4:
        return "****"
    return f"{'*' * (len(val) - 4)}{val[-4:]}"


class SubscriberInfo(BaseModel):
    """Subscriber / Primary Policyholder Information."""
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    subscriber_id: str = Field(..., description="Subscriber unique identifier with payer")
    full_name: str = Field(..., description="Full name of subscriber")
    date_of_birth: Optional[str] = Field(None, description="ISO date string (YYYY-MM-DD) of subscriber DOB")
    relationship: RelationshipType = Field(default=RelationshipType.SELF, description="Patient relation to subscriber")


class PayerInfo(BaseModel):
    """Payer / TPA organization information."""
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    payer_id: str = Field(..., description="Unique identifier of insurance payer organization")
    payer_name: str = Field(..., description="Legal name of insurance company or payer")
    payer_code: Optional[str] = Field(None, description="Payer gateway clearinghouse or registry code")
    tpa_name: Optional[str] = Field(None, description="Third-Party Administrator (TPA) name if applicable")


class InsuranceCoverageCreate(BaseModel):
    """Request payload to register patient insurance coverage."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Target patient identifier")
    payer_id: str = Field(..., description="Payer organization reference")
    payer_name: str = Field(..., description="Payer organization name")
    policy_number: str = Field(..., min_length=2, max_length=64, description="Insurance policy number")
    member_id: str = Field(..., min_length=2, max_length=64, description="Beneficiary/Member ID")
    group_number: Optional[str] = Field(None, max_length=64, description="Employer/Group policy number")
    plan_name: Optional[str] = Field(None, max_length=128, description="Health insurance plan name")
    plan_type: Optional[str] = Field(None, max_length=64, description="Type of plan (HMO, PPO, INDEMNITY, CASHLESS)")
    subscriber: SubscriberInfo = Field(default_factory=lambda: SubscriberInfo(subscriber_id="self", full_name="Self", relationship=RelationshipType.SELF))
    start_date: Optional[str] = Field(None, description="Coverage effective start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Coverage expiry / termination date (YYYY-MM-DD)")
    is_primary: bool = Field(default=True, description="Whether this is the patient's primary policy")
    document_reference_id: Optional[str] = Field(None, description="Phase 5 document reference of insurance card")


class InsuranceCoverageUpdate(BaseModel):
    """Payload to update existing insurance coverage."""
    model_config = ConfigDict(extra="forbid")

    status: Optional[CoverageStatus] = Field(None, description="Updated status")
    plan_name: Optional[str] = Field(None, max_length=128)
    group_number: Optional[str] = Field(None, max_length=64)
    is_primary: Optional[bool] = Field(None)
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


class InsuranceCoverageResponse(BaseModel):
    """Patient insurance coverage response view."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    payer: PayerInfo
    policy_number: str
    member_id: str
    group_number: Optional[str] = None
    plan_name: Optional[str] = None
    plan_type: Optional[str] = None
    subscriber: SubscriberInfo
    status: CoverageStatus
    is_primary: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    document_reference_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @property
    def masked_policy_number(self) -> str:
        return mask_identifier(self.policy_number)

    @property
    def masked_member_id(self) -> str:
        return mask_identifier(self.member_id)


class InsuranceCoverageRecord(BaseModel):
    """Internal domain & persistence representation of insurance coverage."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    payer_id: str
    payer_name: str
    payer_code: Optional[str] = None
    tpa_name: Optional[str] = None
    policy_number: str
    member_id: str
    group_number: Optional[str] = None
    plan_name: Optional[str] = None
    plan_type: Optional[str] = None
    subscriber_id: str
    subscriber_name: str
    subscriber_dob: Optional[str] = None
    relationship: RelationshipType = RelationshipType.SELF
    status: CoverageStatus = CoverageStatus.UNVERIFIED
    is_primary: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    document_reference_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> InsuranceCoverageResponse:
        return InsuranceCoverageResponse(
            id=self.id,
            patient_id=self.patient_id,
            payer=PayerInfo(
                payer_id=self.payer_id,
                payer_name=self.payer_name,
                payer_code=self.payer_code,
                tpa_name=self.tpa_name,
            ),
            policy_number=self.policy_number,
            member_id=self.member_id,
            group_number=self.group_number,
            plan_name=self.plan_name,
            plan_type=self.plan_type,
            subscriber=SubscriberInfo(
                subscriber_id=self.subscriber_id,
                full_name=self.subscriber_name,
                date_of_birth=self.subscriber_dob,
                relationship=self.relationship,
            ),
            status=self.status,
            is_primary=self.is_primary,
            start_date=self.start_date,
            end_date=self.end_date,
            document_reference_id=self.document_reference_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

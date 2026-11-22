"""Phase 84: Delegated-Authority Readiness Schemas.

Verifies readiness of delegated governance authorities to execute emergency responsibilities
without creating, altering, or granting legal authority or operational delegations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class DelegatedAuthorityStatus(str, Enum):
    VERIFIED_READY = "VERIFIED_READY"
    AWARENESS_DEMONSTRATED_UNVERIFIED_AUTHORITY = "AWARENESS_DEMONSTRATED_UNVERIFIED_AUTHORITY"
    EXPIRED_DELEGATION_EVIDENCE = "EXPIRED_DELEGATION_EVIDENCE"
    DEMONSTRATION_REQUIRED = "DEMONSTRATION_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DelegatedAuthorityReadinessRecord(BaseModel):
    delegation_readiness_id: str
    tenant_id: str
    delegated_authority_reference: str
    delegate_user_id: str
    delegator_role: str
    authorized_scope: str
    delegation_valid_until: Optional[datetime] = None
    awareness_demonstrated: bool = False
    documentation_capability_verified: bool = False
    escalation_pathway_verified: bool = False
    practical_scenario_demonstrated: bool = False
    status: DelegatedAuthorityStatus = DelegatedAuthorityStatus.INSUFFICIENT_EVIDENCE
    limitations: Optional[str] = None
    assessed_by: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class AssessDelegatedAuthorityReadinessRequest(BaseModel):
    delegated_authority_reference: str
    delegate_user_id: str
    delegator_role: str
    authorized_scope: str
    delegation_valid_until: Optional[datetime] = None
    awareness_demonstrated: bool = False
    documentation_capability_verified: bool = False
    escalation_pathway_verified: bool = False
    practical_scenario_demonstrated: bool = False
    limitations: Optional[str] = None

"""Pydantic schemas for user identity and context representation."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from app.schemas.auth import AccountStatus, UserRole


class UserIdentityResponse(BaseModel):
    """User profile data returned by /auth/me."""

    id: str = Field(description="Unique user identifier")
    role: UserRole = Field(description="User primary role")
    status: AccountStatus = Field(description="Account operational status")


class AuthenticatedUserContext(BaseModel):
    """Lightweight backend context representing the authenticated caller.

    IMPORTANT: Contains NO clinical data (diagnoses, prescriptions, history).
    """

    user_id: str = Field(default="", description="Unique user identifier")
    role: UserRole
    account_status: AccountStatus = Field(default=AccountStatus.ACTIVE)
    organization_id: Optional[str] = Field(default=None, description="Optional tenant organization reference")
    facility_id: Optional[str] = Field(default=None, description="Optional facility reference")
    patient_id: Optional[str] = Field(default=None, description="Optional patient reference")

    def __init__(self, **data: Any) -> None:
        if "id" in data and "user_id" not in data:
            data["user_id"] = data["id"]
        super().__init__(**data)

    @property
    def id(self) -> str:
        """Alias for user_id for convenience."""
        return self.user_id

    @property
    def is_active(self) -> bool:
        """Check if caller account is in active status."""
        return self.account_status == AccountStatus.ACTIVE

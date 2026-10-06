"""Clinical Record History & Version Query Contracts (Phase 46).

Defines:
- Version summary items and history query responses
- Version diff comparisons
- History pagination metadata
- Strict historical read semantics (historical records are explicitly flagged `is_current=False`)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.versioning import ClinicalVersionRecord, RecordTemporalMetadata, VersionType


class VersionSummaryItem(BaseModel):
    """Compact summary of a historical version for chronological listing."""

    model_config = ConfigDict(extra="ignore")

    version_id: str = Field(description="Unique version record identifier")
    version_number: int = Field(ge=1, description="Monotonically increasing version index")
    version_type: VersionType = Field(description="Transition type e.g. CREATED, UPDATED, CORRECTED")
    is_current: bool = Field(description="True if this is the active current version")
    actor_id: str = Field(description="Actor identifier who made the change")
    actor_role: str = Field(description="Role of actor")
    change_reason: str = Field(description="Clinical reason for this transition")
    verification_state: str = Field(description="Verification trust state at this version")
    provenance_id: Optional[str] = Field(default=None, description="Reference to provenance audit")
    source_system: Optional[str] = Field(default=None, description="Origin source system")
    is_deleted: bool = Field(default=False, description="Soft-deletion indicator")
    effective_time: datetime = Field(description="Clinically effective timestamp")
    recorded_time: datetime = Field(description="System recording timestamp")
    created_at: datetime = Field(description="Version record creation timestamp")


class HistoryQueryResponse(BaseModel):
    """Enveloped response for resource version history."""

    model_config = ConfigDict(extra="ignore")

    resource_id: str = Field(description="Clinical entity identifier")
    resource_type: str = Field(description="Resource domain type")
    patient_id: str = Field(description="Canonical patient ID")
    current_version_number: int = Field(ge=1, description="Latest active version number")
    total_versions: int = Field(ge=1, description="Total count of recorded versions")
    versions: List[VersionSummaryItem] = Field(description="Chronological or reverse-chronological list of versions")
    next_cursor: Optional[str] = Field(default=None, description="Cursor for pagination if more items exist")
    has_more: bool = Field(default=False, description="True if further historical records exist")


class FieldDiff(BaseModel):
    """Field-level differential between two versions."""

    field_name: str
    old_value: Any = None
    new_value: Any = None


class VersionDiffResponse(BaseModel):
    """Differential comparison between two versions of a clinical resource."""

    model_config = ConfigDict(extra="ignore")

    resource_id: str
    resource_type: str
    base_version_number: int
    compared_version_number: int
    diff_count: int
    field_diffs: List[FieldDiff]
    generated_at: datetime

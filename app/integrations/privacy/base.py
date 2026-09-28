"""Abstract interfaces for privacy, retention, and de-identification providers (Phase 24)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.schemas.privacy import (
    DataClassification,
    DataProcessingPurpose,
    DeletionEligibilityCheck,
    LegalHold,
    PrivacyEvaluationResponse,
    RetentionPolicy,
)


class PrivacyPolicyEvaluator(ABC):
    """Abstract interface for evaluating privacy policies and purpose validation."""

    @abstractmethod
    async def evaluate_access(
        self,
        actor_id: str,
        role: str,
        resource_type: str,
        resource_id: str,
        patient_id: Optional[str],
        purpose: DataProcessingPurpose,
    ) -> PrivacyEvaluationResponse:
        """Evaluate if actor has authorization and purpose to access the classified resource."""
        pass


class RetentionOrchestrator(ABC):
    """Abstract interface for resource lifecycle, archival, and controlled deletion."""

    @abstractmethod
    async def get_policy(self, resource_type: str) -> Optional[RetentionPolicy]:
        """Fetch active retention policy for resource type."""
        pass

    @abstractmethod
    async def check_deletion_eligibility(
        self, resource_type: str, resource_id: str, patient_id: Optional[str] = None
    ) -> DeletionEligibilityCheck:
        """Verify whether a resource can be safely deleted or if holds/dependencies prevent it."""
        pass

    @abstractmethod
    async def archive_resource(
        self, resource_type: str, resource_id: str, actor_id: str
    ) -> bool:
        """Move resource into ARCHIVED state with immutable provenance."""
        pass

    @abstractmethod
    async def execute_deletion(
        self, resource_type: str, resource_id: str, actor_id: str, reason: str, force: bool = False
    ) -> bool:
        """Execute controlled deletion following fail-closed hold checks."""
        pass


class DeidentificationEngine(ABC):
    """Abstract interface for non-production de-identification transformations."""

    @abstractmethod
    def deidentify_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip direct identifiers, redact free-text PHI, and generalize demographics."""
        pass

    @abstractmethod
    def redact_text(self, text: str) -> str:
        """Redact names, phone numbers, emails, dates from clinical narratives."""
        pass


class PseudonymizationEngine(ABC):
    """Abstract interface for cryptographically salted pseudonymization."""

    @abstractmethod
    def pseudonymize(self, identifier: str) -> str:
        """Generate a deterministic pseudonymous token using secret salt."""
        pass

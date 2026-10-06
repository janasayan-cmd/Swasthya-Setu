"""Phase 50: Safety Learning Repository.

Thread-safe storage layer for safety learning analysis jobs, results,
candidate patterns, recommendations, and effectiveness evaluations.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.safety_analysis import (
    AnalysisScopeType,
    AnalysisType,
    SafetyAnalysisJob,
    SafetyAnalysisResult,
)
from app.schemas.safety_effectiveness import CorrectiveActionEffectivenessRecord
from app.schemas.safety_pattern import SafetyPatternCandidate
from app.schemas.safety_recommendation import SafetyRecommendation


class SafetyLearningRepository:
    """Thread-safe in-memory repository for Phase 50 safety learning entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: Dict[str, SafetyAnalysisJob] = {}
        self._results: Dict[str, SafetyAnalysisResult] = {}
        self._idempotency_map: Dict[str, str] = {}  # key -> job_id
        self._patterns: Dict[str, SafetyPatternCandidate] = {}
        self._recommendations: Dict[str, SafetyRecommendation] = {}
        self._effectiveness: Dict[str, CorrectiveActionEffectivenessRecord] = {}  # action_id -> eff

    def save_job(self, job: SafetyAnalysisJob) -> SafetyAnalysisJob:
        """Persist analysis job and index idempotency key."""
        with self._lock:
            self._jobs[job.id] = job
            if job.idempotency_key:
                self._idempotency_map[job.idempotency_key] = job.id
            return job

    def get_job(self, job_id: str) -> Optional[SafetyAnalysisJob]:
        """Retrieve analysis job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def find_job_by_idempotency_key(self, key: str) -> Optional[SafetyAnalysisJob]:
        """Find job by idempotency key."""
        with self._lock:
            job_id = self._idempotency_map.get(key)
            return self._jobs.get(job_id) if job_id else None

    def list_jobs(self, organization_id: Optional[str] = None) -> List[SafetyAnalysisJob]:
        """List all analysis jobs, optionally filtered by organization."""
        with self._lock:
            jobs = list(self._jobs.values())
            if organization_id:
                jobs = [j for j in jobs if j.organization_id == organization_id or j.organization_id is None]
            return jobs

    def save_result(self, result: SafetyAnalysisResult) -> SafetyAnalysisResult:
        """Persist safety analysis result."""
        with self._lock:
            self._results[result.id] = result
            return result

    def get_result(self, result_id: str) -> Optional[SafetyAnalysisResult]:
        """Retrieve result by ID."""
        with self._lock:
            return self._results.get(result_id)

    def get_result_by_analysis_id(self, analysis_id: str) -> Optional[SafetyAnalysisResult]:
        """Retrieve result by parent analysis/job ID."""
        with self._lock:
            for r in self._results.values():
                if r.analysis_id == analysis_id:
                    return r
            return None

    def save_pattern(self, pattern: SafetyPatternCandidate) -> SafetyPatternCandidate:
        """Persist pattern candidate."""
        with self._lock:
            self._patterns[pattern.id] = pattern
            return pattern

    def get_pattern(self, pattern_id: str) -> Optional[SafetyPatternCandidate]:
        """Retrieve pattern candidate by ID."""
        with self._lock:
            return self._patterns.get(pattern_id)

    def list_patterns(self) -> List[SafetyPatternCandidate]:
        """List all pattern candidates."""
        with self._lock:
            return list(self._patterns.values())

    def save_recommendation(self, rec: SafetyRecommendation) -> SafetyRecommendation:
        """Persist recommendation."""
        with self._lock:
            self._recommendations[rec.id] = rec
            return rec

    def get_recommendation(self, rec_id: str) -> Optional[SafetyRecommendation]:
        """Retrieve recommendation by ID."""
        with self._lock:
            return self._recommendations.get(rec_id)

    def list_recommendations(self) -> List[SafetyRecommendation]:
        """List all recommendations."""
        with self._lock:
            return list(self._recommendations.values())

    def save_effectiveness(self, eff: CorrectiveActionEffectivenessRecord) -> CorrectiveActionEffectivenessRecord:
        """Persist corrective action effectiveness evaluation."""
        with self._lock:
            self._effectiveness[eff.action_id] = eff
            return eff

    def get_effectiveness(self, action_id: str) -> Optional[CorrectiveActionEffectivenessRecord]:
        """Retrieve effectiveness evaluation by corrective action ID."""
        with self._lock:
            return self._effectiveness.get(action_id)

    def reset(self) -> None:
        """Clear all stores for testing."""
        with self._lock:
            self._jobs.clear()
            self._results.clear()
            self._idempotency_map.clear()
            self._patterns.clear()
            self._recommendations.clear()
            self._effectiveness.clear()


# Global singleton
safety_learning_repository = SafetyLearningRepository()

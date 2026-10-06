"""Phase 49: Clinical Safety Incident Repository.

Thread-safe storage layer for clinical safety signals, safety incidents,
evidence references, root-cause hypotheses, and corrective actions.
Distinct from Phase 27 operational incidents.
"""

from datetime import datetime, timezone, timedelta
import threading
from typing import Any, Dict, List, Optional

from app.schemas.corrective_actions import CorrectiveActionRecord
from app.schemas.incident_evidence import EvidenceReference
from app.schemas.incident_investigation import RootCauseHypothesis
from app.schemas.incidents import (
    IncidentImpactStatus,
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    SafetySignal,
)


class SafetyIncidentRepository:
    """Thread-safe in-memory repository for clinical safety incidents and investigation entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._signals: Dict[str, SafetySignal] = {}
        self._signal_correlation_map: Dict[str, str] = {}  # key -> signal_id
        self._incidents: Dict[str, IncidentRecord] = {}
        self._patient_incidents: Dict[str, List[str]] = {}
        self._decision_incidents: Dict[str, List[str]] = {}
        self._evidence: Dict[str, EvidenceReference] = {}
        self._incident_evidence: Dict[str, List[str]] = {}
        self._hypotheses: Dict[str, RootCauseHypothesis] = {}
        self._incident_hypotheses: Dict[str, List[str]] = {}
        self._actions: Dict[str, CorrectiveActionRecord] = {}
        self._incident_actions: Dict[str, List[str]] = {}

    def save_signal(self, signal: SafetySignal) -> SafetySignal:
        """Persist a safety signal and index correlation key."""
        with self._lock:
            self._signals[signal.id] = signal
            if signal.correlation_id:
                self._signal_correlation_map[signal.correlation_id] = signal.id
            return signal

    def get_signal(self, signal_id: str) -> Optional[SafetySignal]:
        """Retrieve safety signal by ID."""
        with self._lock:
            return self._signals.get(signal_id)

    def find_duplicate_signal(self, correlation_key: str, window_seconds: int = 3600) -> Optional[SafetySignal]:
        """Check if an identical signal was captured within the deduplication window."""
        with self._lock:
            signal_id = self._signal_correlation_map.get(correlation_key)
            if not signal_id:
                return None
            signal = self._signals.get(signal_id)
            if not signal:
                return None
            now = datetime.now(timezone.utc)
            if now - signal.detected_at <= timedelta(seconds=window_seconds):
                return signal
            return None

    def save_incident(self, incident: IncidentRecord) -> IncidentRecord:
        """Persist or update a clinical safety incident record."""
        with self._lock:
            self._incidents[incident.id] = incident
            if incident.patient_id:
                p_list = self._patient_incidents.setdefault(incident.patient_id, [])
                if incident.id not in p_list:
                    p_list.append(incident.id)
            if incident.decision_id:
                d_list = self._decision_incidents.setdefault(incident.decision_id, [])
                if incident.id not in d_list:
                    d_list.append(incident.id)
            return incident

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        """Retrieve clinical safety incident by ID."""
        with self._lock:
            return self._incidents.get(incident_id)

    def list_incidents(
        self,
        patient_id: Optional[str] = None,
        incident_type: Optional[IncidentType] = None,
        status: Optional[IncidentStatus] = None,
    ) -> List[IncidentRecord]:
        """Filter and list clinical safety incidents."""
        with self._lock:
            candidates = list(self._incidents.values())
            if patient_id:
                candidates = [i for i in candidates if i.patient_id == patient_id]
            if incident_type:
                candidates = [i for i in candidates if i.incident_type == incident_type]
            if status:
                candidates = [i for i in candidates if i.status == status]
            return candidates

    def save_evidence(self, evidence: EvidenceReference) -> EvidenceReference:
        """Persist an evidence pointer linked to a safety incident."""
        with self._lock:
            self._evidence[evidence.id] = evidence
            e_list = self._incident_evidence.setdefault(evidence.incident_id, [])
            if evidence.id not in e_list:
                e_list.append(evidence.id)
            return evidence

    def list_evidence(self, incident_id: str) -> List[EvidenceReference]:
        """List all evidence references for a safety incident."""
        with self._lock:
            e_ids = self._incident_evidence.get(incident_id, [])
            return [self._evidence[eid] for eid in e_ids if eid in self._evidence]

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceReference]:
        """Retrieve evidence reference by ID."""
        with self._lock:
            return self._evidence.get(evidence_id)

    def save_hypothesis(self, hypothesis: RootCauseHypothesis) -> RootCauseHypothesis:
        """Persist a root-cause hypothesis."""
        with self._lock:
            self._hypotheses[hypothesis.id] = hypothesis
            h_list = self._incident_hypotheses.setdefault(hypothesis.incident_id, [])
            if hypothesis.id not in h_list:
                h_list.append(hypothesis.id)
            return hypothesis

    def list_hypotheses(self, incident_id: str) -> List[RootCauseHypothesis]:
        """List all hypotheses documented for a safety incident."""
        with self._lock:
            h_ids = self._incident_hypotheses.get(incident_id, [])
            return [self._hypotheses[hid] for hid in h_ids if hid in self._hypotheses]

    def get_hypothesis(self, hypothesis_id: str) -> Optional[RootCauseHypothesis]:
        """Retrieve hypothesis by ID."""
        with self._lock:
            return self._hypotheses.get(hypothesis_id)

    def save_action(self, action: CorrectiveActionRecord) -> CorrectiveActionRecord:
        """Persist a corrective or preventive action record."""
        with self._lock:
            self._actions[action.id] = action
            a_list = self._incident_actions.setdefault(action.incident_id, [])
            if action.id not in a_list:
                a_list.append(action.id)
            return action

    def list_actions(self, incident_id: str) -> List[CorrectiveActionRecord]:
        """List all corrective/preventive actions for a safety incident."""
        with self._lock:
            a_ids = self._incident_actions.get(incident_id, [])
            return [self._actions[aid] for aid in a_ids if aid in self._actions]

    def get_action(self, action_id: str) -> Optional[CorrectiveActionRecord]:
        """Retrieve corrective action by ID."""
        with self._lock:
            return self._actions.get(action_id)

    def reset(self) -> None:
        """Clear all stores for isolated testing."""
        with self._lock:
            self._signals.clear()
            self._signal_correlation_map.clear()
            self._incidents.clear()
            self._patient_incidents.clear()
            self._decision_incidents.clear()
            self._evidence.clear()
            self._incident_evidence.clear()
            self._hypotheses.clear()
            self._incident_hypotheses.clear()
            self._actions.clear()
            self._incident_actions.clear()


# Global singleton for Phase 49 clinical safety incident repository
safety_incident_repository = SafetyIncidentRepository()

import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  ShieldAlert,
  Server,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  Users,
  Terminal,
  Cpu,
  BarChart3,
  Layers,
  ShieldCheck,
  Unlock,
  KeyRound,
  FileText,
  DollarSign,
  AlertOctagon
} from 'lucide-react';
import { apiClient } from '../../services/api';
import type { UserProfile } from '../../services/authStore';
import type {
  OperationalIncident,
  IncidentSeverity,
  IncidentStatus,
  IncidentCategory,
  AdminUserRecord,
  SupportSessionRecord,
  AnalyticsOverview,
  OperationalAnomaly,
  ProviderUsageMetric,
} from '../../types';

interface AdminPortalProps {
  currentUser?: UserProfile | null;
}

// Fallback synthetic telemetry when offline or in standalone demo mode
const DEFAULT_ANALYTICS_OVERVIEW: AnalyticsOverview = {
  total_requests: 148290,
  successful_requests: 147104,
  client_errors: 1042,
  server_errors: 144,
  error_rate_percentage: 0.80,
  latency_percentiles: {
    p50: 42.5,
    p90: 118.2,
    p95: 184.6,
    p99: 342.1,
    avg: 64.8,
    min: 4.2,
    max: 1420.0,
  },
  latency_distribution: {
    under_50ms: 88400,
    from_50ms_to_200ms: 45200,
    from_200ms_to_500ms: 12100,
    from_500ms_to_1s: 2100,
    from_1s_to_5s: 460,
    over_5s: 30,
  },
  active_anomalies_count: 2,
  provider_count: 5,
  window_minutes: 60,
};

const DEFAULT_ANOMALIES: OperationalAnomaly[] = [
  {
    anomaly_id: 'anom-9041-lat',
    anomaly_type: 'LATENCY_SPIKE',
    severity: 'HIGH',
    status: 'DETECTED',
    title: 'P95 Latency Degradation on Document Extraction API',
    description: 'P95 response time rose from baseline 180ms to 480ms (+166%) over the past 15 minutes due to heavy PDF batch ingestion.',
    detected_at: new Date(Date.now() - 14 * 60 * 1000).toISOString(),
    metric_name: 'p95_latency_ms',
    current_value: 480.0,
    threshold_value: 300.0,
    baseline_value: 180.0,
    deviation_percent: 166.7,
    endpoint: '/api/v1/patients/{patient_id}/documents',
  },
  {
    anomaly_id: 'anom-9042-err',
    anomaly_type: 'PROVIDER_ERROR_BURST',
    severity: 'MEDIUM',
    status: 'ACKNOWLEDGED',
    title: 'Upstream Rate Limit (HTTP 429) on RxNorm Terminology API',
    description: 'Upstream provider returned HTTP 429 for 3.4% of medication normalization queries. Circuit breaker engaged gracefully.',
    detected_at: new Date(Date.now() - 48 * 60 * 1000).toISOString(),
    acknowledged_at: new Date(Date.now() - 32 * 60 * 1000).toISOString(),
    acknowledged_by: 'ADM-OPS-9901',
    metric_name: 'provider_error_rate',
    current_value: 3.4,
    threshold_value: 2.0,
    baseline_value: 0.1,
    deviation_percent: 3300.0,
    provider_name: 'RxNorm NLM Provider',
  },
];

const DEFAULT_PROVIDERS: ProviderUsageMetric[] = [
  {
    provider_name: 'RxNorm NLM Terminology',
    total_calls: 34210,
    success_count: 33890,
    error_count: 320,
    availability_percentage: 99.06,
    avg_duration_ms: 84.5,
    p95_duration_ms: 210.0,
    estimated_cost_usd: 0.00,
    quota_utilization_percentage: 42.0,
  },
  {
    provider_name: 'OpenFDA Drug Interaction Engine',
    total_calls: 19840,
    success_count: 19820,
    error_count: 20,
    availability_percentage: 99.90,
    avg_duration_ms: 112.4,
    p95_duration_ms: 245.0,
    estimated_cost_usd: 0.00,
    quota_utilization_percentage: 28.5,
  },
  {
    provider_name: 'Google Gemini 1.5 Flash (Clinical AI)',
    total_calls: 8450,
    success_count: 8432,
    error_count: 18,
    availability_percentage: 99.79,
    avg_duration_ms: 640.2,
    p95_duration_ms: 1250.0,
    total_tokens: 3840200,
    estimated_cost_usd: 1.48,
    quota_utilization_percentage: 16.2,
  },
  {
    provider_name: 'Tesseract OCR Document Worker',
    total_calls: 1240,
    success_count: 1215,
    error_count: 25,
    availability_percentage: 97.98,
    avg_duration_ms: 1420.0,
    p95_duration_ms: 2890.0,
    estimated_cost_usd: 0.00,
    quota_utilization_percentage: 64.0,
  },
  {
    provider_name: 'NDHM / ABDM Health Bridge',
    total_calls: 5120,
    success_count: 5098,
    error_count: 22,
    availability_percentage: 99.57,
    avg_duration_ms: 320.0,
    p95_duration_ms: 680.0,
    estimated_cost_usd: 0.00,
    quota_utilization_percentage: 31.0,
  },
];

const DEFAULT_INCIDENTS: OperationalIncident[] = [
  {
    id: 'INC-2026-088',
    title: 'Upstream Medication Interaction Latency Elevation',
    description: 'Elevated response latency observed on external terminology normalization checks. Local Redis cache fallbacks active.',
    category: 'MEDICATION_PROVIDER_OUTAGE',
    severity: 'MEDIUM',
    status: 'INVESTIGATING',
    detected_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    acknowledged_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    owner: 'Platform SRE Team',
    correlation_id: 'corr-med-lat-992',
    created_by: 'ADM-OPS-9901',
    updated_by: 'ADM-OPS-9901',
    created_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
  {
    id: 'INC-2026-087',
    title: 'Nightly OCR Worker Queue Backlog Cleared',
    description: 'Batch upload burst caused worker task backlog. Auto-scaler provisioned 3 extra worker containers; queue drained.',
    category: 'QUEUE_FAILURE',
    severity: 'LOW',
    status: 'RESOLVED',
    detected_at: new Date(Date.now() - 4 * 3600 * 1000).toISOString(),
    acknowledged_at: new Date(Date.now() - 3.8 * 3600 * 1000).toISOString(),
    resolved_at: new Date(Date.now() - 3.2 * 3600 * 1000).toISOString(),
    resolution_summary: 'Worker pool scaled from 2 to 5 nodes. All 380 enqueued OCR tasks completed successfully with zero data loss.',
    owner: 'Async Worker Team',
    created_by: 'ADM-OPS-9901',
    updated_by: 'ADM-OPS-9901',
    created_at: new Date(Date.now() - 4 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 3.2 * 3600 * 1000).toISOString(),
  },
];

const DEFAULT_USERS: AdminUserRecord[] = [
  {
    id: 'HS-DOC-2045',
    name: 'Dr. Priya Nair',
    email: 'doctor@healthsetu.org',
    role: 'DOCTOR',
    is_active: true,
    mfa_enabled: true,
    facility_id: 'fac-apollo-001',
    created_at: '2024-01-14T10:00:00Z',
    last_login: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
  },
  {
    id: 'HS-PAT-8921',
    name: 'Rohan Sharma',
    email: 'rohan.sharma@example.com',
    role: 'PATIENT',
    is_active: true,
    mfa_enabled: false,
    created_at: '2026-09-12T08:30:00Z',
    last_login: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
  },
  {
    id: 'HOSP-APOLLO-01',
    name: 'Apollo Indraprastha Hospital Desk',
    email: 'emergency@apollo-delhi.org',
    role: 'HOSPITAL_ADMIN',
    is_active: true,
    mfa_enabled: true,
    facility_id: 'fac-apollo-001',
    created_at: '2023-01-01T00:00:00Z',
    last_login: new Date(Date.now() - 1 * 3600 * 1000).toISOString(),
  },
  {
    id: 'ADM-OPS-9901',
    name: 'Platform Operations Admin',
    email: 'ops@healthsetu.org',
    role: 'SYSTEM_ADMIN',
    is_active: true,
    mfa_enabled: true,
    created_at: '2026-01-01T00:00:00Z',
    last_login: new Date().toISOString(),
  },
];

const DEFAULT_AUDIT_LOGS = [
  {
    event_id: 'aud-001',
    action: 'ADMIN_SYSTEM_STATUS_VIEWED',
    actor_id: 'ADM-OPS-9901',
    actor_role: 'SYSTEM_ADMIN',
    occurred_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    details: 'Viewed operational health metrics and telemetry percentiles dashboard.',
  },
  {
    event_id: 'aud-002',
    action: 'OPERATIONAL_ANOMALY_ACKNOWLEDGED',
    actor_id: 'ADM-OPS-9901',
    actor_role: 'SYSTEM_ADMIN',
    occurred_at: new Date(Date.now() - 32 * 60 * 1000).toISOString(),
    details: 'Acknowledged anomaly anom-9042-err (RxNorm Rate Limit).',
  },
  {
    event_id: 'aud-003',
    action: 'INCIDENT_STATUS_TRANSITION',
    actor_id: 'ADM-OPS-9901',
    actor_role: 'SYSTEM_ADMIN',
    occurred_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    details: 'Transitioned incident INC-2026-088 status from OPEN to INVESTIGATING.',
  },
];

export const AdminPortal: React.FC<AdminPortalProps> = ({ currentUser }) => {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'analytics' | 'incidents' | 'users' | 'audit'>('analytics');
  const [windowMinutes, setWindowMinutes] = useState<number>(60);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Telemetry & Analytics State (Phase 28)
  const [analytics, setAnalytics] = useState<AnalyticsOverview>(DEFAULT_ANALYTICS_OVERVIEW);
  const [anomalies, setAnomalies] = useState<OperationalAnomaly[]>(DEFAULT_ANOMALIES);
  const [providers, setProviders] = useState<ProviderUsageMetric[]>(DEFAULT_PROVIDERS);
  const [totalCostUsd, setTotalCostUsd] = useState<number>(1.48);

  // Admin & Incident State (Phase 27)
  const [incidents, setIncidents] = useState<OperationalIncident[]>(DEFAULT_INCIDENTS);
  const [users, setUsers] = useState<AdminUserRecord[]>(DEFAULT_USERS);
  const [auditLogs, setAuditLogs] = useState<any[]>(DEFAULT_AUDIT_LOGS);

  // Action Modals State
  const [selectedAnomaly, setSelectedAnomaly] = useState<OperationalAnomaly | null>(null);
  const [anomalyNotes, setAnomalyNotes] = useState<string>('');
  const [isResolveModalOpen, setIsResolveModalOpen] = useState<boolean>(false);

  const [isNewIncidentModalOpen, setIsNewIncidentModalOpen] = useState<boolean>(false);
  const [newIncidentTitle, setNewIncidentTitle] = useState<string>('');
  const [newIncidentDesc, setNewIncidentDesc] = useState<string>('');
  const [newIncidentSeverity, setNewIncidentSeverity] = useState<IncidentSeverity>('MEDIUM');
  const [newIncidentCategory, setNewIncidentCategory] = useState<IncidentCategory>('PERFORMANCE_INCIDENT');

  const [selectedIncident, setSelectedIncident] = useState<OperationalIncident | null>(null);
  const [resolutionSummary, setResolutionSummary] = useState<string>('');

  const [userSearch, setUserSearch] = useState<string>('');

  // Break-glass support session modal
  const [isBreakGlassModalOpen, setIsBreakGlassModalOpen] = useState<boolean>(false);
  const [breakGlassReason, setBreakGlassReason] = useState<string>('');
  const [breakGlassTicket, setBreakGlassTicket] = useState<string>('');
  const [supportSessions, setSupportSessions] = useState<SupportSessionRecord[]>([]);

  // Fetch telemetry and operational data from backend
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Fetch Analytics Overview (Phase 28)
      const ovRes = await apiClient.getAnalyticsOverview({ window_minutes: windowMinutes });
      if (ovRes.overview) {
        setAnalytics(ovRes.overview);
      }

      // 2. Fetch Operational Anomalies (Phase 28)
      const anomRes = await apiClient.getOperationalAnomalies();
      if (anomRes.anomalies && anomRes.anomalies.length > 0) {
        setAnomalies(anomRes.anomalies);
      }

      // 3. Fetch Provider Consumption (Phase 28)
      const provRes = await apiClient.getProviderUsage({ window_minutes: windowMinutes });
      if (provRes.providers && provRes.providers.length > 0) {
        setProviders(provRes.providers);
        if (provRes.total_cost_usd !== undefined) setTotalCostUsd(provRes.total_cost_usd);
      }

      // 4. Fetch System Health & Incidents (Phase 27)
      const incRes = await apiClient.getAdminIncidents();
      if (incRes.incidents && incRes.incidents.length > 0) {
        setIncidents(incRes.incidents);
      }

      const usrRes = await apiClient.getAdminUsers();
      if (usrRes.users && usrRes.users.length > 0) {
        setUsers(usrRes.users);
      }

      const audRes = await apiClient.getAdminAuditLogs({ limit: 10 });
      if (audRes.logs && audRes.logs.length > 0) {
        setAuditLogs(audRes.logs);
      }

      const sessRes = await apiClient.getSupportSessions();
      if (sessRes.sessions) {
        setSupportSessions(sessRes.sessions);
      }
    } catch (e) {
      console.warn('Backend offline or unauthenticated; utilizing stateful local memory:', e);
    } finally {
      setIsLoading(false);
    }
  }, [windowMinutes]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Periodic polling if auto-refresh is active
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchData();
    }, 15000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchData]);

  // Handlers for Anomaly Actions
  const handleAcknowledgeAnomaly = async (anomaly: OperationalAnomaly) => {
    const res = await apiClient.acknowledgeOperationalAnomaly(anomaly.anomaly_id, 'Acknowledged by operator');
    if (res.anomaly) {
      setAnomalies(prev => prev.map(a => a.anomaly_id === anomaly.anomaly_id ? res.anomaly! : a));
    } else {
      setAnomalies(prev => prev.map(a => a.anomaly_id === anomaly.anomaly_id ? {
        ...a,
        status: 'ACKNOWLEDGED',
        acknowledged_at: new Date().toISOString(),
        acknowledged_by: currentUser?.id || 'ADM-OPS-9901'
      } : a));
    }
  };

  const handleResolveAnomaly = async () => {
    if (!selectedAnomaly) return;
    const res = await apiClient.resolveOperationalAnomaly(selectedAnomaly.anomaly_id, anomalyNotes || 'Resolved following telemetry stabilization.');
    if (res.anomaly) {
      setAnomalies(prev => prev.map(a => a.anomaly_id === selectedAnomaly.anomaly_id ? res.anomaly! : a));
    } else {
      setAnomalies(prev => prev.map(a => a.anomaly_id === selectedAnomaly.anomaly_id ? {
        ...a,
        status: 'RESOLVED',
        resolved_at: new Date().toISOString(),
        resolution_notes: anomalyNotes || 'Resolved following telemetry stabilization.'
      } : a));
    }
    setIsResolveModalOpen(false);
    setSelectedAnomaly(null);
    setAnomalyNotes('');
  };

  // Handlers for Incidents
  const handleCreateIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIncidentTitle.trim()) return;

    const newIncData = {
      title: newIncidentTitle.trim(),
      description: newIncidentDesc.trim() || 'Operational incident raised via Backoffice console.',
      severity: newIncidentSeverity,
      category: newIncidentCategory,
      owner: currentUser?.id || 'Platform SRE Team',
    };

    const res = await apiClient.createAdminIncident(newIncData);
    if (res.incident) {
      setIncidents(prev => [res.incident!, ...prev]);
    } else {
      const fallbackInc: OperationalIncident = {
        id: `INC-2026-${Math.floor(100 + Math.random() * 900)}`,
        title: newIncidentTitle.trim(),
        description: newIncidentDesc.trim() || 'Operational incident raised via Backoffice console.',
        severity: newIncidentSeverity,
        category: newIncidentCategory,
        status: 'OPEN',
        detected_at: new Date().toISOString(),
        owner: currentUser?.id || 'Platform SRE Team',
        created_by: currentUser?.id || 'ADM-OPS-9901',
        updated_by: currentUser?.id || 'ADM-OPS-9901',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setIncidents(prev => [fallbackInc, ...prev]);
    }

    setNewIncidentTitle('');
    setNewIncidentDesc('');
    setIsNewIncidentModalOpen(false);
  };

  const handleTransitionIncidentStatus = async (inc: OperationalIncident, nextStatus: IncidentStatus) => {
    if (nextStatus === 'RESOLVED' || nextStatus === 'CLOSED') {
      setSelectedIncident(inc);
      return;
    }

    const res = await apiClient.updateAdminIncident(inc.id, { status: nextStatus });
    if (res.incident) {
      setIncidents(prev => prev.map(i => i.id === inc.id ? res.incident! : i));
    } else {
      setIncidents(prev => prev.map(i => i.id === inc.id ? {
        ...i,
        status: nextStatus,
        acknowledged_at: nextStatus === 'INVESTIGATING' ? new Date().toISOString() : i.acknowledged_at,
        updated_at: new Date().toISOString()
      } : i));
    }
  };

  const handleConfirmResolveIncident = async () => {
    if (!selectedIncident) return;
    const summary = resolutionSummary.trim() || 'Remediation completed; metrics stabilized within normal baseline.';
    const res = await apiClient.resolveAdminIncident(selectedIncident.id, summary);
    if (res.incident) {
      setIncidents(prev => prev.map(i => i.id === selectedIncident.id ? res.incident! : i));
    } else {
      setIncidents(prev => prev.map(i => i.id === selectedIncident.id ? {
        ...i,
        status: 'RESOLVED',
        resolved_at: new Date().toISOString(),
        resolution_summary: summary,
        updated_at: new Date().toISOString(),
      } : i));
    }
    setSelectedIncident(null);
    setResolutionSummary('');
  };

  // User Administration Handlers
  const handleToggleUserStatus = async (user: AdminUserRecord) => {
    const nextStatus = !user.is_active;
    const reason = nextStatus ? 'Reactivated by admin' : 'Administrative suspension';
    const res = await apiClient.setAdminUserStatus(user.id, nextStatus, reason);
    if (res.user) {
      setUsers(prev => prev.map(u => u.id === user.id ? res.user! : u));
    } else {
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: nextStatus } : u));
    }
  };

  const handleResetMFA = async (user: AdminUserRecord) => {
    const reason = 'User requested secondary credential recovery';
    await apiClient.resetAdminUserMFA(user.id, reason);
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, mfa_enabled: false } : u));
    alert(`MFA recovery token generated for user ${user.id}. Audit log emitted.`);
  };

  // Break-glass support session handler
  const handleCreateBreakGlassSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!breakGlassReason.trim()) return;

    const data = {
      reason: breakGlassReason.trim(),
      ticket_id: breakGlassTicket.trim() || undefined,
      duration_minutes: 60,
    };

    const res = await apiClient.createSupportSession(data);
    if (res.session) {
      setSupportSessions(prev => [res.session!, ...prev]);
    } else {
      const fallbackSession: SupportSessionRecord = {
        session_id: `SESS-${Math.floor(1000 + Math.random() * 9000)}`,
        requested_by: currentUser?.id || 'ADM-OPS-9901',
        reason: breakGlassReason.trim(),
        ticket_id: breakGlassTicket.trim() || 'OPS-TICKET-AUTO',
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        is_active: true,
      };
      setSupportSessions(prev => [fallbackSession, ...prev]);
    }

    setBreakGlassReason('');
    setBreakGlassTicket('');
    setIsBreakGlassModalOpen(false);
  };

  // Severity styling helper
  const getSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-red-900/30 text-red-400 border border-red-800/60';
      case 'HIGH':
        return 'bg-orange-900/30 text-orange-400 border border-orange-800/60';
      case 'MEDIUM':
        return 'bg-yellow-900/30 text-yellow-400 border border-yellow-800/60';
      default:
        return 'bg-blue-900/30 text-blue-400 border border-blue-800/60';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'OPEN':
      case 'DETECTED':
        return 'bg-red-950/40 text-red-300 border border-red-800/50';
      case 'INVESTIGATING':
      case 'ACKNOWLEDGED':
        return 'bg-amber-950/40 text-amber-300 border border-amber-800/50';
      case 'MITIGATED':
        return 'bg-indigo-950/40 text-indigo-300 border border-indigo-800/50';
      case 'RESOLVED':
      case 'CLOSED':
        return 'bg-emerald-950/40 text-emerald-300 border border-emerald-800/50';
      default:
        return 'bg-slate-800 text-slate-300 border border-slate-700';
    }
  };

  const filteredUsers = users.filter(u => 
    u.name.toLowerCase().includes(userSearch.toLowerCase()) ||
    u.id.toLowerCase().includes(userSearch.toLowerCase()) ||
    (u.email && u.email.toLowerCase().includes(userSearch.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-[#0E1520] text-[#E2E8F0] font-sans pt-20 pb-16 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* =====================================================================
            Top Operational Control Bar & Sovereign Header
        ===================================================================== */}
        <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#E07B39] to-[#9A3412] flex items-center justify-center shadow-lg shadow-[#E07B39]/20">
              <Server className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  HealthSetu Backoffice & Operational Intelligence
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wider uppercase bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live Telemetry Active
                </span>
              </div>
              <p className="text-xs text-[#8BA1BA] mt-0.5">
                Phase 27 Admin Operations & Phase 28 API Analytics · ISO 27001 / ABDM Sovereign Governance
              </p>
            </div>
          </div>

          {/* Right Control Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 bg-[#0E1520] border border-[#233348] rounded-lg p-1 text-xs">
              {[15, 60, 1440].map((mins) => (
                <button
                  key={mins}
                  onClick={() => setWindowMinutes(mins)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                    windowMinutes === mins
                      ? 'bg-[#233348] text-white shadow-sm'
                      : 'text-[#8BA1BA] hover:text-white'
                  }`}
                >
                  {mins === 15 ? '15m' : mins === 60 ? '1h' : '24h'}
                </button>
              ))}
            </div>

            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                autoRefresh
                  ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60'
                  : 'bg-[#141E2D] text-[#8BA1BA] border-[#233348] hover:text-white'
              }`}
              title="Toggle 15s auto-polling"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${autoRefresh && isLoading ? 'animate-spin' : ''}`} />
              <span>{autoRefresh ? 'Live (15s)' : 'Paused'}</span>
            </button>

            <button
              onClick={fetchData}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#233348] hover:bg-[#2C405B] text-white border border-[#334A68] transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* =====================================================================
            Sub-Navigation Tabs
        ===================================================================== */}
        <div className="flex border-b border-[#233348] gap-2 overflow-x-auto pb-1">
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs font-semibold transition-all border-b-2 ${
              activeTab === 'analytics'
                ? 'bg-[#141E2D] text-white border-[#E07B39]'
                : 'text-[#8BA1BA] border-transparent hover:text-white hover:bg-[#141E2D]/50'
            }`}
          >
            <BarChart3 className="w-4 h-4 text-[#E07B39]" />
            <span>API Telemetry & Percentiles (Phase 28)</span>
            {anomalies.filter(a => a.status === 'DETECTED').length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-red-900/60 text-red-300 border border-red-700/60">
                {anomalies.filter(a => a.status === 'DETECTED').length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('incidents')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs font-semibold transition-all border-b-2 ${
              activeTab === 'incidents'
                ? 'bg-[#141E2D] text-white border-[#E07B39]'
                : 'text-[#8BA1BA] border-transparent hover:text-white hover:bg-[#141E2D]/50'
            }`}
          >
            <AlertOctagon className="w-4 h-4 text-orange-400" />
            <span>Operational Incidents (Phase 27)</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-[#233348] text-[#8BA1BA]">
              {incidents.filter(i => i.status !== 'RESOLVED' && i.status !== 'CLOSED').length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs font-semibold transition-all border-b-2 ${
              activeTab === 'users'
                ? 'bg-[#141E2D] text-white border-[#E07B39]'
                : 'text-[#8BA1BA] border-transparent hover:text-white hover:bg-[#141E2D]/50'
            }`}
          >
            <Users className="w-4 h-4 text-emerald-400" />
            <span>User Governance & Access Control</span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs font-semibold transition-all border-b-2 ${
              activeTab === 'audit'
                ? 'bg-[#141E2D] text-white border-[#E07B39]'
                : 'text-[#8BA1BA] border-transparent hover:text-white hover:bg-[#141E2D]/50'
            }`}
          >
            <Terminal className="w-4 h-4 text-blue-400" />
            <span>Audit Trail & Break-Glass Sessions</span>
          </button>
        </div>

        {/* =====================================================================
            TAB 1: API ANALYTICS & OPERATIONAL INTELLIGENCE (PHASE 28)
        ===================================================================== */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            
            {/* Top Operational KPI Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Total Requests */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-4 shadow-lg">
                <div className="flex items-center justify-between text-xs text-[#8BA1BA]">
                  <span>Total Invocations</span>
                  <Activity className="w-4 h-4 text-blue-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-1">
                  {analytics.total_requests.toLocaleString()}
                </div>
                <div className="text-[11px] text-[#8BA1BA] mt-2 flex items-center justify-between border-t border-[#1C2A3D] pt-2">
                  <span className="text-emerald-400 font-semibold">{analytics.successful_requests.toLocaleString()} 2xx/3xx</span>
                  <span className="text-red-400">{analytics.server_errors} 5xx</span>
                </div>
              </div>

              {/* P95 Latency */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-4 shadow-lg">
                <div className="flex items-center justify-between text-xs text-[#8BA1BA]">
                  <span>P95 Tail Latency</span>
                  <Zap className="w-4 h-4 text-[#E07B39]" />
                </div>
                <div className="text-2xl font-bold text-white mt-1">
                  {analytics.latency_percentiles.p95} <span className="text-xs font-normal text-[#8BA1BA]">ms</span>
                </div>
                <div className="text-[11px] text-[#8BA1BA] mt-2 flex items-center justify-between border-t border-[#1C2A3D] pt-2">
                  <span>P50: {analytics.latency_percentiles.p50}ms</span>
                  <span>P99: {analytics.latency_percentiles.p99}ms</span>
                </div>
              </div>

              {/* Error Rate */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-4 shadow-lg">
                <div className="flex items-center justify-between text-xs text-[#8BA1BA]">
                  <span>Error Rate</span>
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-1 flex items-baseline gap-2">
                  {analytics.error_rate_percentage.toFixed(2)}%
                  <span className="text-[10px] text-emerald-400 font-semibold uppercase">Within SLO</span>
                </div>
                <div className="text-[11px] text-[#8BA1BA] mt-2 flex items-center justify-between border-t border-[#1C2A3D] pt-2">
                  <span>4xx: {analytics.client_errors}</span>
                  <span>5xx: {analytics.server_errors}</span>
                </div>
              </div>

              {/* Active Anomalies */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-4 shadow-lg">
                <div className="flex items-center justify-between text-xs text-[#8BA1BA]">
                  <span>Operational Anomalies</span>
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-1 flex items-baseline gap-2">
                  {anomalies.filter(a => a.status === 'DETECTED').length}
                  <span className="text-xs font-normal text-[#8BA1BA]">Unresolved</span>
                </div>
                <div className="text-[11px] text-[#8BA1BA] mt-2 flex items-center justify-between border-t border-[#1C2A3D] pt-2">
                  <span>{anomalies.length} tracked today</span>
                  <span className="text-emerald-400 font-semibold">Auto-evaluating</span>
                </div>
              </div>

              {/* Provider Health & Tokens */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-4 shadow-lg">
                <div className="flex items-center justify-between text-xs text-[#8BA1BA]">
                  <span>External AI / Integrations</span>
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-1">
                  ${totalCostUsd.toFixed(2)}
                </div>
                <div className="text-[11px] text-[#8BA1BA] mt-2 flex items-center justify-between border-t border-[#1C2A3D] pt-2">
                  <span>{providers.length} Active Connectors</span>
                  <span className="text-emerald-400">99.4% Avail</span>
                </div>
              </div>
            </div>

            {/* High-Resolution Latency Distribution & SLO Percentiles */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Latency Percentiles Card */}
              <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-[#E07B39]" />
                    High-Resolution Latency Percentiles
                  </h3>
                  <span className="text-[11px] text-[#8BA1BA]">ISO 25010 Benchmark</span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-[#0E1520] rounded-lg border border-[#1C2A3D]">
                    <div className="text-[#8BA1BA]">P50 (Median)</div>
                    <div className="text-lg font-bold text-white mt-0.5">{analytics.latency_percentiles.p50} ms</div>
                    <div className="text-[10px] text-emerald-400 mt-1">Interactive Standard</div>
                  </div>
                  <div className="p-3 bg-[#0E1520] rounded-lg border border-[#1C2A3D]">
                    <div className="text-[#8BA1BA]">P90 Threshold</div>
                    <div className="text-lg font-bold text-white mt-0.5">{analytics.latency_percentiles.p90} ms</div>
                    <div className="text-[10px] text-emerald-400 mt-1">High-Load Window</div>
                  </div>
                  <div className="p-3 bg-[#0E1520] rounded-lg border border-[#E07B39]/30 bg-[#E07B39]/5">
                    <div className="text-[#E07B39] font-semibold">P95 (SLO Target)</div>
                    <div className="text-lg font-bold text-white mt-0.5">{analytics.latency_percentiles.p95} ms</div>
                    <div className="text-[10px] text-emerald-400 mt-1">Target: &lt; 250 ms</div>
                  </div>
                  <div className="p-3 bg-[#0E1520] rounded-lg border border-red-900/30 bg-red-950/10">
                    <div className="text-red-400 font-semibold">P99 (Outliers)</div>
                    <div className="text-lg font-bold text-white mt-0.5">{analytics.latency_percentiles.p99} ms</div>
                    <div className="text-[10px] text-amber-400 mt-1">Heavy OCR & Batch</div>
                  </div>
                </div>

                <div className="text-[11px] text-[#8BA1BA] border-t border-[#1C2A3D] pt-3 flex items-center justify-between">
                  <span>Fastest: {analytics.latency_percentiles.min}ms</span>
                  <span>Average: {analytics.latency_percentiles.avg}ms</span>
                  <span>Max Peak: {analytics.latency_percentiles.max}ms</span>
                </div>
              </div>

              {/* Latency Distribution Histogram / Buckets */}
              <div className="lg:col-span-2 bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    Response Duration Distribution Buckets
                  </h3>
                  <span className="text-[11px] text-[#8BA1BA]">Total Sample: {analytics.total_requests.toLocaleString()}</span>
                </div>

                <div className="space-y-3">
                  {[
                    { label: '< 50ms (Cached / Instant)', count: analytics.latency_distribution.under_50ms, color: 'bg-emerald-500' },
                    { label: '50ms - 200ms (Interactive)', count: analytics.latency_distribution.from_50ms_to_200ms, color: 'bg-teal-500' },
                    { label: '200ms - 500ms (Acceptable)', count: analytics.latency_distribution.from_200ms_to_500ms, color: 'bg-blue-500' },
                    { label: '500ms - 1s (Compute Heavy)', count: analytics.latency_distribution.from_500ms_to_1s, color: 'bg-amber-500' },
                    { label: '1s - 5s (Aggregations / OCR)', count: analytics.latency_distribution.from_1s_to_5s, color: 'bg-orange-500' },
                    { label: '> 5s (Degraded Alert)', count: analytics.latency_distribution.over_5s, color: 'bg-red-500' },
                  ].map((bucket, idx) => {
                    const pct = analytics.total_requests > 0 ? (bucket.count / analytics.total_requests) * 100 : 0;
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-[#8BA1BA] font-medium">{bucket.label}</span>
                          <span className="text-white font-semibold">{bucket.count.toLocaleString()} ({pct.toFixed(1)}%)</span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-[#0E1520] overflow-hidden border border-[#1C2A3D]">
                          <div
                            className={`h-full ${bucket.color} transition-all duration-500`}
                            style={{ width: `${Math.max(pct, 0.5)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Operational Anomalies Stream */}
            <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <AlertOctagon className="w-4 h-4 text-red-400" />
                    Automated Operational Anomaly Detection Stream
                  </h3>
                  <p className="text-xs text-[#8BA1BA] mt-0.5">
                    Evaluated continuously against rolling baseline models; auto-flags traffic surges, latency degradation, and error bursts.
                  </p>
                </div>
                <span className="text-xs px-2.5 py-1 rounded bg-[#0E1520] text-[#8BA1BA] border border-[#1C2A3D]">
                  {anomalies.length} Total Registered
                </span>
              </div>

              <div className="divide-y divide-[#1C2A3D]">
                {anomalies.map((anom) => (
                  <div key={anom.anomaly_id} className="py-3.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div className="space-y-1 max-w-3xl">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${getSeverityBadge(anom.severity)}`}>
                          {anom.severity}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${getStatusBadge(anom.status)}`}>
                          {anom.status}
                        </span>
                        <span className="text-xs font-semibold text-white">
                          {anom.title}
                        </span>
                      </div>
                      <p className="text-xs text-[#8BA1BA]">
                        {anom.description}
                      </p>
                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#5A738E] pt-1">
                        <span>Metric: <strong className="text-[#8BA1BA]">{anom.metric_name}</strong></span>
                        <span>Value: <strong className="text-red-400">{anom.current_value}</strong></span>
                        <span>Threshold: <strong className="text-[#8BA1BA]">{anom.threshold_value}</strong></span>
                        <span>Deviation: <strong className="text-amber-400">+{anom.deviation_percent?.toFixed(1)}%</strong></span>
                        <span>Detected: {new Date(anom.detected_at).toLocaleTimeString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {anom.status === 'DETECTED' && (
                        <button
                          onClick={() => handleAcknowledgeAnomaly(anom)}
                          className="px-3 py-1.5 rounded text-xs font-semibold bg-[#233348] hover:bg-[#2C405B] text-white border border-[#334A68] transition-all"
                        >
                          Acknowledge
                        </button>
                      )}
                      {anom.status !== 'RESOLVED' && (
                        <button
                          onClick={() => {
                            setSelectedAnomaly(anom);
                            setIsResolveModalOpen(true);
                          }}
                          className="px-3 py-1.5 rounded text-xs font-semibold bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/60 transition-all"
                        >
                          Resolve
                        </button>
                      )}
                      {anom.status === 'RESOLVED' && (
                        <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Resolved
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* External Provider & Cost Governance Table */}
            <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-emerald-400" />
                    External Provider Health, Token Consumption & Cost Governance
                  </h3>
                  <p className="text-xs text-[#8BA1BA] mt-0.5">
                    Live monitoring of external medication databases, OCR thread pools, and LLM clinical token costs.
                  </p>
                </div>
                <div className="text-xs text-[#8BA1BA]">
                  Total Window Cost: <strong className="text-emerald-400">${totalCostUsd.toFixed(2)} USD</strong>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#233348] text-[#8BA1BA]">
                      <th className="pb-2.5 font-semibold">Provider / Capability</th>
                      <th className="pb-2.5 font-semibold">Total Requests</th>
                      <th className="pb-2.5 font-semibold">Availability</th>
                      <th className="pb-2.5 font-semibold">Avg Latency</th>
                      <th className="pb-2.5 font-semibold">P95 Latency</th>
                      <th className="pb-2.5 font-semibold">Tokens</th>
                      <th className="pb-2.5 font-semibold">Cost (USD)</th>
                      <th className="pb-2.5 font-semibold">Quota Usage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1C2A3D]">
                    {providers.map((p, idx) => (
                      <tr key={idx} className="hover:bg-[#1A2638]/50 transition-colors">
                        <td className="py-3 font-semibold text-white flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${p.availability_percentage > 99 ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                          {p.provider_name}
                        </td>
                        <td className="py-3 text-[#8BA1BA]">{p.total_calls.toLocaleString()}</td>
                        <td className="py-3">
                          <span className={`font-semibold ${p.availability_percentage >= 99.5 ? 'text-emerald-400' : p.availability_percentage >= 98.0 ? 'text-amber-400' : 'text-red-400'}`}>
                            {p.availability_percentage.toFixed(2)}%
                          </span>
                        </td>
                        <td className="py-3 text-[#8BA1BA]">{p.avg_duration_ms.toFixed(1)} ms</td>
                        <td className="py-3 text-white font-medium">{p.p95_duration_ms.toFixed(1)} ms</td>
                        <td className="py-3 text-[#8BA1BA]">
                          {p.total_tokens ? p.total_tokens.toLocaleString() : '—'}
                        </td>
                        <td className="py-3 text-emerald-400 font-semibold">
                          ${p.estimated_cost_usd.toFixed(2)}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-[#0E1520] overflow-hidden">
                              <div
                                className={`h-full ${(p.quota_utilization_percentage || 0) > 80 ? 'bg-red-500' : 'bg-emerald-500'}`}
                                style={{ width: `${p.quota_utilization_percentage || 10}%` }}
                              />
                            </div>
                            <span className="text-[11px] text-[#8BA1BA]">{p.quota_utilization_percentage || 0}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}

        {/* =====================================================================
            TAB 2: OPERATIONAL INCIDENT MANAGEMENT (PHASE 27)
        ===================================================================== */}
        {activeTab === 'incidents' && (
          <div className="space-y-6">
            
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <AlertOctagon className="w-5 h-5 text-orange-400" />
                  Operational Incidents & Outage Triage
                </h2>
                <p className="text-xs text-[#8BA1BA] mt-0.5">
                  Controlled administrative lifecycle: OPEN &rarr; INVESTIGATING &rarr; MITIGATED &rarr; RESOLVED &rarr; CLOSED.
                </p>
              </div>

              <button
                onClick={() => setIsNewIncidentModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-[#E07B39] to-[#C96A28] text-white shadow-lg shadow-[#E07B39]/20 hover:brightness-110 transition-all"
              >
                <AlertOctagon className="w-4 h-4" />
                Declare New Incident
              </button>
            </div>

            {/* Incidents List */}
            <div className="space-y-4">
              {incidents.map((inc) => (
                <div key={inc.id} className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-3">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#1C2A3D] pb-3">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-[#E07B39]">{inc.id}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${getSeverityBadge(inc.severity)}`}>
                        {inc.severity}
                      </span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${getStatusBadge(inc.status)}`}>
                        {inc.status}
                      </span>
                      <span className="text-xs text-[#8BA1BA] px-2 py-0.5 rounded bg-[#0E1520] border border-[#1C2A3D]">
                        {inc.category}
                      </span>
                    </div>

                    <div className="text-xs text-[#8BA1BA]">
                      Detected: {new Date(inc.detected_at).toLocaleString()}
                    </div>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-white">{inc.title}</h3>
                    <p className="text-xs text-[#8BA1BA] mt-1">{inc.description}</p>
                  </div>

                  {inc.resolution_summary && (
                    <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-lg text-xs text-emerald-300">
                      <strong>Resolution Summary:</strong> {inc.resolution_summary}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-2 border-t border-[#1C2A3D]">
                    <div className="text-[#8BA1BA]">
                      Owner: <strong className="text-white">{inc.owner || 'Unassigned'}</strong>
                    </div>

                    <div className="flex items-center gap-2">
                      {inc.status === 'OPEN' && (
                        <button
                          onClick={() => handleTransitionIncidentStatus(inc, 'INVESTIGATING')}
                          className="px-3 py-1 rounded text-xs font-semibold bg-[#233348] hover:bg-[#2C405B] text-white border border-[#334A68] transition-all"
                        >
                          Mark Investigating
                        </button>
                      )}
                      {inc.status === 'INVESTIGATING' && (
                        <button
                          onClick={() => handleTransitionIncidentStatus(inc, 'MITIGATED')}
                          className="px-3 py-1 rounded text-xs font-semibold bg-indigo-950/50 hover:bg-indigo-900/50 text-indigo-300 border border-indigo-800/50 transition-all"
                        >
                          Mark Mitigated
                        </button>
                      )}
                      {(inc.status === 'INVESTIGATING' || inc.status === 'MITIGATED') && (
                        <button
                          onClick={() => handleTransitionIncidentStatus(inc, 'RESOLVED')}
                          className="px-3 py-1 rounded text-xs font-semibold bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/60 transition-all"
                        >
                          Resolve Incident
                        </button>
                      )}
                      {inc.status === 'RESOLVED' && (
                        <button
                          onClick={() => handleTransitionIncidentStatus(inc, 'CLOSED')}
                          className="px-3 py-1 rounded text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all"
                        >
                          Close Archive
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

          </div>
        )}

        {/* =====================================================================
            TAB 3: USER GOVERNANCE & SECURITY ACCESS CONTROL (PHASE 27)
        ===================================================================== */}
        {activeTab === 'users' && (
          <div className="space-y-6">
            
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Users className="w-5 h-5 text-emerald-400" />
                  Sovereign User Governance & Security Administration
                </h2>
                <p className="text-xs text-[#8BA1BA] mt-0.5">
                  Manage clinician clearance, patient account statuses, and trigger MFA recovery resets with mandatory audit reason logging.
                </p>
              </div>

              <div className="relative w-full sm:w-72">
                <Search className="w-4 h-4 text-[#8BA1BA] absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search user ID, name, email..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-[#0E1520] border border-[#233348] rounded-lg text-xs text-white placeholder-[#5A738E] focus:outline-none focus:border-[#E07B39]"
                />
              </div>
            </div>

            {/* Users Table */}
            <div className="bg-[#141E2D] border border-[#233348] rounded-xl overflow-hidden shadow-lg">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-[#0E1520] border-b border-[#233348] text-[#8BA1BA]">
                    <th className="py-3 px-4 font-semibold">User ID & Name</th>
                    <th className="py-3 px-4 font-semibold">Role</th>
                    <th className="py-3 px-4 font-semibold">Facility / Org</th>
                    <th className="py-3 px-4 font-semibold">MFA Security</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold">Last Active</th>
                    <th className="py-3 px-4 font-semibold text-right">Administrative Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1C2A3D]">
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="hover:bg-[#1A2638]/50 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white">{u.name}</div>
                        <div className="text-[11px] font-mono text-[#8BA1BA]">{u.id}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[#233348] text-white">
                          {u.role}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[#8BA1BA]">
                        {u.facility_id || 'Cross-Tenant Network'}
                      </td>
                      <td className="py-3.5 px-4">
                        {u.mfa_enabled ? (
                          <span className="text-emerald-400 font-semibold flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5" />
                            Enforced (FIDO2/TOTP)
                          </span>
                        ) : (
                          <span className="text-amber-400 flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            Standard
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {u.is_active ? (
                          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
                            Active
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-950/60 text-red-300 border border-red-800/60">
                            Suspended
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-[#8BA1BA]">
                        {u.last_login ? new Date(u.last_login).toLocaleTimeString() : 'Never'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleResetMFA(u)}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-[#0E1520] hover:bg-[#1C2A3D] text-[#8BA1BA] hover:text-white border border-[#233348] transition-all"
                            title="Reset Multi-Factor Authentication"
                          >
                            <KeyRound className="w-3.5 h-3.5 inline mr-1" />
                            Reset MFA
                          </button>

                          <button
                            onClick={() => handleToggleUserStatus(u)}
                            className={`px-2.5 py-1 rounded text-[11px] font-semibold border transition-all ${
                              u.is_active
                                ? 'bg-red-950/40 text-red-300 border-red-800/50 hover:bg-red-900/50'
                                : 'bg-emerald-950/40 text-emerald-300 border-emerald-800/50 hover:bg-emerald-900/50'
                            }`}
                          >
                            {u.is_active ? 'Suspend' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

          </div>
        )}

        {/* =====================================================================
            TAB 4: IMMUTABLE AUDIT TRAIL & BREAK-GLASS SESSIONS (PHASE 27)
        ===================================================================== */}
        {activeTab === 'audit' && (
          <div className="space-y-6">
            
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-blue-400" />
                  Append-Only Administrative Audit Log & Break-Glass Access
                </h2>
                <p className="text-xs text-[#8BA1BA] mt-0.5">
                  Legally tamper-evident audit records. Emergency support sessions grant bounded, strictly audited operational elevation.
                </p>
              </div>

              <button
                onClick={() => setIsBreakGlassModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-red-950/60 text-red-300 border border-red-800/60 hover:bg-red-900/60 transition-all shadow-lg shadow-red-950/30"
              >
                <Unlock className="w-4 h-4 text-red-400" />
                Initiate Break-Glass Support Session
              </button>
            </div>

            {/* Active Break Glass Sessions */}
            {supportSessions.length > 0 && (
              <div className="bg-[#141E2D] border border-amber-900/40 rounded-xl p-5 shadow-lg space-y-3">
                <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Active Emergency Break-Glass Sessions
                </h3>
                <div className="space-y-2">
                  {supportSessions.map((sess) => (
                    <div key={sess.session_id} className="p-3 bg-[#0E1520] border border-amber-800/30 rounded-lg flex items-center justify-between text-xs">
                      <div>
                        <span className="font-mono text-white font-bold">{sess.session_id}</span>
                        <span className="text-[#8BA1BA] ml-3">Operator: <strong className="text-white">{sess.requested_by}</strong></span>
                        <span className="text-[#8BA1BA] ml-3">Reason: <span className="text-amber-300">{sess.reason}</span></span>
                      </div>
                      <div className="text-[11px] text-[#8BA1BA]">
                        Expires: {new Date(sess.expires_at).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Audit Log Stream */}
            <div className="bg-[#141E2D] border border-[#233348] rounded-xl p-5 shadow-lg space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                Administrative Event Log (Phase 15/27 Invariant)
              </h3>

              <div className="divide-y divide-[#1C2A3D]">
                {auditLogs.map((log, idx) => (
                  <div key={idx} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 font-mono">
                        <span className="text-[#E07B39] font-bold">{log.action}</span>
                        <span className="text-[#8BA1BA]">by</span>
                        <span className="text-white font-semibold">{log.actor_id}</span>
                      </div>
                      <p className="text-[#8BA1BA] text-[11px]">{log.details}</p>
                    </div>

                    <div className="text-[11px] text-[#5A738E] shrink-0 font-mono">
                      {new Date(log.occurred_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

      </div>

      {/* =====================================================================
          MODAL: Declare New Incident
      ===================================================================== */}
      {isNewIncidentModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#141E2D] border border-[#233348] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#233348] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <AlertOctagon className="w-5 h-5 text-orange-400" />
                Declare Operational Incident
              </h3>
              <button
                onClick={() => setIsNewIncidentModalOpen(false)}
                className="text-[#8BA1BA] hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateIncident} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Incident Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. OCR Worker Processing Latency Spike"
                  value={newIncidentTitle}
                  onChange={(e) => setNewIncidentTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-[#E07B39]"
                />
              </div>

              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Description & Evidence</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Describe the degradation, affected endpoints, and observed blast radius..."
                  value={newIncidentDesc}
                  onChange={(e) => setNewIncidentDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-[#E07B39]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#8BA1BA] font-medium mb-1">Severity</label>
                  <select
                    value={newIncidentSeverity}
                    onChange={(e) => setNewIncidentSeverity(e.target.value as IncidentSeverity)}
                    className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-[#E07B39]"
                  >
                    <option value="CRITICAL">CRITICAL (System Outage)</option>
                    <option value="HIGH">HIGH (Degraded SLO)</option>
                    <option value="MEDIUM">MEDIUM (Provider Variance)</option>
                    <option value="LOW">LOW (Informational / Triage)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[#8BA1BA] font-medium mb-1">Category</label>
                  <select
                    value={newIncidentCategory}
                    onChange={(e) => setNewIncidentCategory(e.target.value as IncidentCategory)}
                    className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-[#E07B39]"
                  >
                    <option value="PERFORMANCE_INCIDENT">PERFORMANCE_INCIDENT</option>
                    <option value="API_OUTAGE">API_OUTAGE</option>
                    <option value="QUEUE_FAILURE">QUEUE_FAILURE</option>
                    <option value="OCR_FAILURE">OCR_FAILURE</option>
                    <option value="MEDICATION_PROVIDER_OUTAGE">MEDICATION_PROVIDER_OUTAGE</option>
                    <option value="AI_PROVIDER_OUTAGE">AI_PROVIDER_OUTAGE</option>
                    <option value="DATABASE_FAILURE">DATABASE_FAILURE</option>
                    <option value="DATA_QUALITY_INCIDENT">DATA_QUALITY_INCIDENT</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#233348]">
                <button
                  type="button"
                  onClick={() => setIsNewIncidentModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-[#233348] text-[#8BA1BA] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg font-semibold bg-[#E07B39] text-white hover:brightness-110 shadow-lg shadow-[#E07B39]/20"
                >
                  Declare Incident
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =====================================================================
          MODAL: Resolve Incident Summary
      ===================================================================== */}
      {selectedIncident && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#141E2D] border border-[#233348] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#233348] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                Resolve Incident {selectedIncident.id}
              </h3>
              <button
                onClick={() => setSelectedIncident(null)}
                className="text-[#8BA1BA] hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-[#8BA1BA]">
                A resolution summary is mandatory under HealthSetu Phase 27 incident management invariants before marking resolved.
              </p>

              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Resolution Summary</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Summarize root cause analysis, fix deployed, and metric stabilization..."
                  value={resolutionSummary}
                  onChange={(e) => setResolutionSummary(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#233348]">
                <button
                  onClick={() => setSelectedIncident(null)}
                  className="px-4 py-2 rounded-lg bg-[#233348] text-[#8BA1BA] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmResolveIncident}
                  className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 text-white hover:bg-emerald-500 shadow-lg shadow-emerald-600/20"
                >
                  Confirm Resolution
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          MODAL: Resolve Anomaly
      ===================================================================== */}
      {isResolveModalOpen && selectedAnomaly && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#141E2D] border border-[#233348] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#233348] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                Resolve Anomaly
              </h3>
              <button
                onClick={() => setIsResolveModalOpen(false)}
                className="text-[#8BA1BA] hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-white font-semibold">{selectedAnomaly.title}</p>
              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Resolution Notes</label>
                <textarea
                  rows={3}
                  placeholder="Notes explaining stabilization or mitigation applied..."
                  value={anomalyNotes}
                  onChange={(e) => setAnomalyNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#233348]">
                <button
                  onClick={() => setIsResolveModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-[#233348] text-[#8BA1BA] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleResolveAnomaly}
                  className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 text-white hover:bg-emerald-500 shadow-lg shadow-emerald-600/20"
                >
                  Mark Anomaly Resolved
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          MODAL: Break-Glass Support Session
      ===================================================================== */}
      {isBreakGlassModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#141E2D] border border-red-800/60 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#233348] pb-3">
              <h3 className="text-base font-bold text-red-400 flex items-center gap-2">
                <Unlock className="w-5 h-5 text-red-400" />
                Emergency Break-Glass Authorization
              </h3>
              <button
                onClick={() => setIsBreakGlassModalOpen(false)}
                className="text-[#8BA1BA] hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateBreakGlassSession} className="space-y-3.5 text-xs">
              <div className="p-3 bg-red-950/40 border border-red-800/40 rounded-lg text-red-300">
                <strong>WARNING:</strong> Break-glass sessions unlock temporary cross-tenant operational troubleshooting. Every query executed during this session is immutably logged with actor sovereign ID and cryptographic hash.
              </div>

              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Ticket Reference (Jira / ServiceNow / PagerDuty)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. INC-8921 or PAGERDUTY-9921"
                  value={breakGlassTicket}
                  onChange={(e) => setBreakGlassTicket(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-red-500"
                />
              </div>

              <div>
                <label className="block text-[#8BA1BA] font-medium mb-1">Clinical / Technical Justification</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Explain why standard support elevation is insufficient..."
                  value={breakGlassReason}
                  onChange={(e) => setBreakGlassReason(e.target.value)}
                  className="w-full px-3 py-2 bg-[#0E1520] border border-[#233348] rounded-lg text-white focus:outline-none focus:border-red-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#233348]">
                <button
                  type="button"
                  onClick={() => setIsBreakGlassModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-[#233348] text-[#8BA1BA] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg font-semibold bg-red-600 text-white hover:bg-red-500 shadow-lg shadow-red-600/30"
                >
                  Authorize 60-Minute Session
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminPortal;

export type Role = 'landing' | 'patient' | 'doctor' | 'hospital' | 'admin';
export const Role = {} as unknown as Role;

export type TrustState = 'verified' | 'extracted' | 'ai-analyzed' | 'raw';
export const TrustState = {} as unknown as TrustState;

export type FreshnessState = 'current' | 'stale' | 'unknown';
export const FreshnessState = {} as unknown as FreshnessState;

export interface Medication {
  id: string;
  name: string;
  genericName: string;
  strength: string;
  dosage: string;
  frequency: string;
  route: string;
  duration: string;
  instructions: string;
  prescribingDoctor: string;
  hospital: string;
  datePrescribed: string;
  trustState: TrustState;
  timeOfDay: ('morning' | 'afternoon' | 'evening' | 'bedtime')[];
  mealTiming: 'before_food' | 'after_food' | 'with_food' | 'empty_stomach';
  category: string;
}
export const Medication = {} as unknown as Medication;

export interface Allergy {
  id: string;
  allergen: string;
  reaction: string;
  severity: 'mild' | 'moderate' | 'severe';
  recordedDate: string;
  recordedBy: string;
  trustState: TrustState;
}
export const Allergy = {} as unknown as Allergy;

export interface TimelineEvent {
  id: string;
  date: string;
  title: string;
  category: 'prescription' | 'consultation' | 'triage' | 'lab' | 'discharge';
  provider: string;
  facility: string;
  description: string;
  trustState: TrustState;
  details?: {
    diagnosis?: string;
    doctorNotes?: string;
    items?: string[];
  };
}
export const TimelineEvent = {} as unknown as TimelineEvent;

export interface AccessRequest {
  id: string;
  doctorId: string;
  doctorName: string;
  doctorRole: string;
  hospital: string;
  requestedScope: 'Full Clinical Record' | 'Prescription History Only' | 'Emergency Access';
  purpose: string;
  status: 'pending' | 'active' | 'revoked' | 'expired';
  requestedAt: string;
  expiresAt: string;
}
export const AccessRequest = {} as unknown as AccessRequest;

export interface HospitalFacility {
  id: string;
  name: string;
  city: string;
  distanceKm: number;
  availableBeds: {
    icu: number;
    emergency: number;
    general: number;
  };
  totalBeds: number;
  emergencyStatus: 'Available' | 'Critical Capacity' | 'Diverting';
  specialties: string[];
  freshness: FreshnessState;
  lastUpdated: string;
  phone: string;
  isNetworkShared: boolean;
}
export const HospitalFacility = {} as unknown as HospitalFacility;

export interface SafetyAlert {
  id: string;
  type: 'drug-interaction' | 'allergy-conflict' | 'duplicate-therapy' | 'food-precaution';
  severity: 'critical' | 'moderate' | 'advisory';
  title: string;
  description: string;
  drugsInvolved: string[];
  source: 'Authoritative Safety Rules (RxNorm/OpenFDA)' | 'Deterministic Rule' | 'AI-Observed Pattern';
}
export const SafetyAlert = {} as unknown as SafetyAlert;

// ---------------------------------------------------------------------
// Phase 27: Admin & Support Operations Types
// ---------------------------------------------------------------------
export type IncidentSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type IncidentStatus = 'OPEN' | 'INVESTIGATING' | 'MITIGATED' | 'RESOLVED' | 'CLOSED';
export type IncidentCategory = 
  | 'API_OUTAGE' 
  | 'DATABASE_FAILURE' 
  | 'QUEUE_FAILURE' 
  | 'OCR_FAILURE' 
  | 'MEDICATION_PROVIDER_OUTAGE' 
  | 'AI_PROVIDER_OUTAGE' 
  | 'INTEROPERABILITY_FAILURE' 
  | 'SECURITY_INCIDENT' 
  | 'DATA_QUALITY_INCIDENT' 
  | 'PERFORMANCE_INCIDENT' 
  | 'DEPLOYMENT_INCIDENT' 
  | 'OTHER';

export interface OperationalIncident {
  id: string;
  title: string;
  description: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
  detected_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
  closed_at?: string;
  owner?: string;
  correlation_id?: string;
  resolution_summary?: string;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface AdminUserRecord {
  id: string;
  name: string;
  email?: string;
  role: string;
  is_active: boolean;
  mfa_enabled?: boolean;
  created_at?: string;
  last_login?: string;
  facility_id?: string;
  organization_id?: string;
}

export interface AdminSystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime_seconds?: number;
  environment?: string;
  components: {
    database: { status: string; latency_ms?: number; message?: string };
    cache?: { status: string; latency_ms?: number };
    ocr_service?: { status: string };
    medication_provider?: { status: string };
    ai_provider?: { status: string };
  };
}

export interface SupportSessionRecord {
  session_id: string;
  requested_by: string;
  reason: string;
  target_user_id?: string;
  ticket_id?: string;
  created_at: string;
  expires_at: string;
  is_active: boolean;
}

// ---------------------------------------------------------------------
// Phase 28: API Analytics, Usage Governance & Operational Intelligence
// ---------------------------------------------------------------------
export interface LatencyPercentiles {
  p50: number;
  p90: number;
  p95: number;
  p99: number;
  avg: number;
  min: number;
  max: number;
}

export interface LatencyDistribution {
  under_50ms: number;
  from_50ms_to_200ms: number;
  from_200ms_to_500ms: number;
  from_500ms_to_1s: number;
  from_1s_to_5s: number;
  over_5s: number;
}

export interface AnalyticsOverview {
  total_requests: number;
  successful_requests: number;
  client_errors: number;
  server_errors: number;
  error_rate_percentage: number;
  latency_percentiles: LatencyPercentiles;
  latency_distribution: LatencyDistribution;
  active_anomalies_count: number;
  provider_count: number;
  window_minutes: number;
}

export interface OperationalAnomaly {
  anomaly_id: string;
  anomaly_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'DETECTED' | 'ACKNOWLEDGED' | 'RESOLVED';
  title: string;
  description: string;
  detected_at: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolution_notes?: string;
  metric_name?: string;
  current_value?: number;
  threshold_value?: number;
  baseline_value?: number;
  deviation_percent?: number;
  endpoint?: string;
  provider_name?: string;
}

export interface ProviderUsageMetric {
  provider_name: string;
  total_calls: number;
  success_count: number;
  error_count: number;
  availability_percentage: number;
  avg_duration_ms: number;
  p95_duration_ms: number;
  total_tokens?: number;
  estimated_cost_usd: number;
  quota_utilization_percentage?: number;
}


/**
 * HealthSetu Complete Backend API Service
 *
 * Full client integration with FastAPI backend:
 * - Phase 1: Health & Readiness probes (/api/v1/health, /api/v1/ready)
 * - Phase 2: Authentication & Token Lifecycle (/api/v1/auth/login, /api/v1/auth/me, /api/v1/auth/logout)
 * - Phase 3: Consent & Access Controls (/api/v1/consents, /api/v1/consents/{id}/revoke)
 * - Phase 4: Patient Profile & Clinical Records (Demographics, Allergies, Vitals, Conditions)
 * - Phase 5: Document Upload & Human-in-the-Loop OCR Extraction (/api/v1/patients/{id}/documents)
 * - Phase 6: Longitudinal Medications & Verification (/api/v1/patients/{id}/medications)
 * - Phase 7: Deterministic & External Medication Safety Check (/api/v1/patients/{id}/medication-safety)
 * - Phase 8: Clinical Triage & SBAR Synthesizer (/api/v1/patients/{id}/triage, /api/v1/patients/{id}/sbar)
 * - Phase 9: Personalized Care Plans & Warning Signs (/api/v1/patients/{id}/care-plans)
 * - Phase 10: Doctor Clinical Workspace (/api/v1/patients/{id}/clinical-workspace)
 * - Phase 11 & 12: Hospital Directory & Emergency Bed Discovery (/api/v1/facilities, /api/v1/facilities/discover)
 */

import type {
  Medication,
  Allergy,
  TimelineEvent,
  AccessRequest,
  HospitalFacility,
  SafetyAlert,
  OperationalIncident,
  AdminUserRecord,
  AdminSystemHealth,
  SupportSessionRecord,
  AnalyticsOverview,
  OperationalAnomaly,
  ProviderUsageMetric,
} from '../types';

// Support VITE_API_BASE_URL, VITE_API_URL, production Railway fallback, relative /api/v1, or localhost:8000
const rawApiUrl = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL) as string | undefined;
const API_BASE_URL = rawApiUrl
  ? (rawApiUrl.endsWith('/api/v1') ? rawApiUrl : `${rawApiUrl.replace(/\/+$/, '')}/api/v1`)
  : typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')
  ? 'https://healthsetu-production.up.railway.app/api/v1'
  : typeof window !== 'undefined' && window.location.origin
  ? '/api/v1'
  : 'http://localhost:8000/api/v1';

export interface BackendHealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version?: string;
  app?: string;
  timestamp?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface BackendUserSummary {
  id: string;
  role: 'PATIENT' | 'DOCTOR' | 'ADMIN';
  identifier?: string;
}

export interface BackendConsent {
  id: string;
  patient_id: string;
  grantee_id: string;
  purpose: string;
  scope: string;
  status: 'ACTIVE' | 'REVOKED' | 'EXPIRED' | 'PENDING' | 'DENIED';
  granted_at: string;
  effective_from: string;
  expires_at?: string;
  revoked_at?: string;
  revocation_reason?: string;
  notes?: string;
}

export interface BackendPatient {
  id: string;
  user_id?: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  sex: string;
  status: string;
  phone?: string;
  email?: string;
  preferred_language?: string;
}

export interface BackendPatientMedication {
  id: string;
  patient_id: string;
  drug_name_raw: string;
  strength_raw?: string;
  dosage_form_raw?: string;
  route_raw?: string;
  frequency_raw?: string;
  duration_raw?: string;
  instructions_raw?: string;
  status: string;
  verification_status: string;
  source: string;
  created_at?: string;
}

export interface BackendAllergy {
  id: string;
  patient_id: string;
  allergen: string;
  reaction?: string;
  severity: 'MILD' | 'MODERATE' | 'SEVERE';
  status: string;
  recorded_by?: string;
  created_at?: string;
}

export interface BackendVital {
  id: string;
  patient_id: string;
  vital_type: string;
  value: number;
  unit: string;
  measured_at: string;
  source: string;
  recorded_by?: string;
}

export interface BackendCarePlan {
  id?: string;
  care_plan_id?: string;
  patient_id: string;
  title: string;
  status: string;
  start_date: string;
  end_date: string;
  goals: Array<{ id: string; description: string; target_date?: string; status: string }>;
  tasks: Array<{
    id: string;
    category: string;
    title: string;
    instructions: string;
    frequency: string;
    day_offset: number;
    due_date?: string;
    status: string;
  }>;
  warning_signs: Array<{ red_flag: string; immediate_instruction: string }>;
  notes?: string;
}

export interface BackendSafetyEvaluation {
  evaluation_id: string;
  status: 'CLEAR' | 'ALERT' | 'CONTRAINDICATED' | 'EVALUATION_ERROR';
  alerts: Array<{
    alert_id: string;
    severity: string;
    title: string;
    description: string;
    medications_involved: Array<Record<string, string>>;
    source: string;
  }>;
  disclaimer: string;
}

export interface BackendFacilityItem {
  id: string;
  name: string;
  facility_type: string;
  status: string;
  phone?: string;
  email?: string;
  address?: {
    city?: string;
    line?: string;
    latitude?: number;
    longitude?: number;
  };
  operational_metadata?: {
    available_beds?: { icu?: number; emergency?: number; general?: number };
    total_beds?: number;
    emergency_status?: 'Available' | 'Critical Capacity' | 'Diverting';
    specialties?: string[];
    distance_km?: number;
    is_network_shared?: boolean;
  };
}

export interface DataQualityFinding {
  id: string;
  patient_id: string;
  resource_type: string;
  resource_id: string;
  finding_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  status: 'PENDING' | 'IN_REVIEW' | 'RESOLVED' | 'REJECTED' | 'UNRESOLVED';
  description: string;
  rule_id: string;
  rule_version: string;
  detected_at: string;
  version: number;
  reviewer_notes?: string;
  resolved_at?: string;
  resolved_by?: string;
  resolution_action?: string;
  resolution_notes?: string;
  source_references?: string[];
  conflicting_references?: string[];
}

export interface ClinicalReconciliation {
  id: string;
  patient_id: string;
  scope: string;
  status: 'PENDING' | 'RESOLVED' | 'UNRESOLVED';
  summary: string;
  sources: Array<{ source_name: string; resource_type: string; count: number }>;
  conflicts: Array<{ domain: string; field: string; source_a: string; val_a: string; source_b: string; val_b: string; risk: string }>;
  created_at: string;
  version: number;
  resolved_at?: string;
  resolution_action?: string;
}

class HealthSetuApiClient {
  private token: string | null = null;
  private activeRole: 'PATIENT' | 'DOCTOR' | 'ADMIN' | null = null;
  private lastPingMs: number | null = null;
  private isConnected: boolean | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('healthsetu_token');
      this.activeRole = (localStorage.getItem('healthsetu_role') as any) || null;
    }
  }

  setToken(token: string | null, role?: 'PATIENT' | 'DOCTOR' | 'ADMIN') {
    this.token = token;
    if (token) {
      localStorage.setItem('healthsetu_token', token);
      if (role) {
        this.activeRole = role;
        localStorage.setItem('healthsetu_role', role);
      }
    } else {
      localStorage.removeItem('healthsetu_token');
      localStorage.removeItem('healthsetu_role');
      this.activeRole = null;
    }
  }

  getToken(): string | null {
    return this.token;
  }

  getActiveRole(): string | null {
    return this.activeRole;
  }

  getLastPing(): number | null {
    return this.lastPingMs;
  }

  getConnectionStatus(): boolean | null {
    return this.isConnected;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<{ data?: T; error?: string; status?: number }> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const t0 = performance.now();
    try {
      // First try relative /api/v1 (proxied by Vite or on production host)
      let res = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      }).catch(async () => {
        // If relative proxy failed (e.g. running standalone), try direct port 8000
        return await fetch(`http://localhost:8000/api/v1${endpoint}`, {
          ...options,
          headers,
        });
      });

      this.lastPingMs = Math.round(performance.now() - t0);
      this.isConnected = res.ok;

      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('text/html')) {
        this.isConnected = false;
        return { error: 'API service not deployed on this domain', status: 404 };
      }

      const json = await res.json().catch(() => null);

      if (!res.ok) {
        const errorMsg =
          json?.error?.message ||
          json?.detail ||
          (typeof json?.error === 'string' ? json.error : `HTTP ${res.status}: Request failed`);
        return { error: errorMsg, status: res.status };
      }

      return {
        data: (json?.data !== undefined ? json.data : json) as T,
        status: res.status,
      };
    } catch (err: any) {
      this.isConnected = false;
      return {
        error: err.message || 'Unable to connect to HealthSetu backend service on port 8000',
        status: 0,
      };
    }
  }

  // =========================================================================
  // Phase 1: Probes
  // =========================================================================
  async checkHealth(): Promise<{ ok: boolean; data?: BackendHealthResponse; latencyMs?: number }> {
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_BASE_URL}/health`, { method: 'GET' }).catch(() =>
        fetch(`http://localhost:8000/api/v1/health`, { method: 'GET' })
      );
      const latencyMs = Math.round(performance.now() - t0);
      this.lastPingMs = latencyMs;
      this.isConnected = res.ok;

      if (res.ok) {
        const json = await res.json();
        return { ok: true, data: json.data || json, latencyMs };
      }
      return { ok: false, latencyMs };
    } catch {
      this.isConnected = false;
      return { ok: false };
    }
  }

  async checkReadiness(): Promise<{ ready: boolean; details?: any }> {
    try {
      const res = await fetch(`${API_BASE_URL}/ready`, { method: 'GET' }).catch(() =>
        fetch(`http://localhost:8000/api/v1/ready`, { method: 'GET' })
      );
      const json = await res.json().catch(() => null);
      return { ready: res.ok, details: json?.data || json };
    } catch {
      return { ready: false };
    }
  }

  // =========================================================================
  // Phase 2: Authentication
  // =========================================================================
  async login(
    identifier: string,
    password: string
  ): Promise<{ tokens?: AuthTokens; user?: BackendUserSummary; error?: string }> {
    const res = await this.request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: BackendUserSummary;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
    });

    if (res.data) {
      this.setToken(res.data.access_token, res.data.user?.role);
      return {
        tokens: res.data,
        user: res.data.user,
      };
    }
    return { error: res.error };
  }

  async register(
    data: {
      name: string;
      role: 'PATIENT' | 'DOCTOR' | 'ADMIN';
      identifier: string;
      password?: string;
      unique_id?: string;
      details?: Record<string, any>;
    }
  ): Promise<{ tokens?: AuthTokens; user?: BackendUserSummary; error?: string }> {
    const res = await this.request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      user: BackendUserSummary;
    }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        role: data.role,
        identifier: data.identifier,
        password: data.password || 'StrongP@ssw0rd123!',
        unique_id: data.unique_id,
        details: data.details,
      }),
    });

    if (res.data) {
      this.setToken(res.data.access_token, res.data.user?.role);
      return {
        tokens: res.data,
        user: res.data.user,
      };
    }
    return { error: res.error };
  }

  async logout(): Promise<void> {
    if (this.token) {
      await this.request('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: this.token }),
      }).catch(() => null);
    }
    this.setToken(null);
  }

  async getCurrentUser(): Promise<any> {
    return this.request('/auth/me', { method: 'GET' });
  }

  /**
   * Ensures an active authenticated session for the specified role.
   * Auto-authenticates using demo credentials if not already logged in with that role.
   */
  async ensureDemoSession(role: 'PATIENT' | 'DOCTOR' | 'ADMIN' = 'PATIENT'): Promise<string | null> {
    if (this.token && this.activeRole === role) {
      return this.token;
    }

    const emailMap: Record<string, string> = {
      PATIENT: 'patient@healthsetu.org',
      DOCTOR: 'doctor@healthsetu.org',
      ADMIN: 'admin@healthsetu.org',
    };

    const res = await this.login(emailMap[role] || 'patient@healthsetu.org', 'StrongP@ssw0rd123!');
    if (res.tokens) {
      return res.tokens.access_token;
    }
    return null;
  }

  // =========================================================================
  // Phase 3: Consent Management
  // =========================================================================
  async listConsents(): Promise<{ consents?: BackendConsent[]; error?: string }> {
    const res = await this.request<{ items: BackendConsent[] }>('/consents', { method: 'GET' });
    if (res.data) {
      return { consents: res.data.items || [] };
    }
    return { error: res.error };
  }

  async createConsent(payload: {
    grantee_id: string;
    purpose: string;
    scope: string;
    notes?: string;
    expires_at?: string;
  }): Promise<{ consent?: BackendConsent; error?: string }> {
    const res = await this.request<BackendConsent>('/consents', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (res.data) {
      return { consent: res.data };
    }
    return { error: res.error };
  }

  async revokeConsent(consentId: string, reason?: string): Promise<{ consent?: BackendConsent; error?: string }> {
    const res = await this.request<BackendConsent>(`/consents/${consentId}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Revoked by patient via HealthSetu portal' }),
    });
    if (res.data) {
      return { consent: res.data };
    }
    return { error: res.error };
  }

  // =========================================================================
  // Phase 4: Patient Clinical Records
  // =========================================================================
  async getPatient(patientId: string): Promise<{ patient?: BackendPatient; error?: string }> {
    const res = await this.request<BackendPatient>(`/patients/${patientId}`, { method: 'GET' });
    return { patient: res.data, error: res.error };
  }

  async getPatientClinicalSummary(patientId: string): Promise<{ summary?: any; error?: string }> {
    const res = await this.request<any>(`/patients/${patientId}/clinical-summary`, { method: 'GET' });
    return { summary: res.data, error: res.error };
  }

  async getPatientMedications(
    patientId: string
  ): Promise<{ medications?: BackendPatientMedication[]; error?: string }> {
    const res = await this.request<{ items: BackendPatientMedication[] }>(
      `/patients/${patientId}/medications`,
      { method: 'GET' }
    );
    return { medications: res.data?.items || [], error: res.error };
  }

  async getPatientAllergies(patientId: string): Promise<{ allergies?: BackendAllergy[]; error?: string }> {
    const res = await this.request<{ items: BackendAllergy[] }>(
      `/patients/${patientId}/allergies`,
      { method: 'GET' }
    );
    return { allergies: res.data?.items || [], error: res.error };
  }

  async getPatientVitals(patientId: string): Promise<{ vitals?: BackendVital[]; error?: string }> {
    const res = await this.request<{ items: BackendVital[] }>(
      `/patients/${patientId}/vitals`,
      { method: 'GET' }
    );
    return { vitals: res.data?.items || [], error: res.error };
  }

  // =========================================================================
  // Phase 5: Document Upload & Extraction
  // =========================================================================
  async uploadMedicalDocument(
    patientId: string,
    file: File | Blob,
    documentType: string = 'PRESCRIPTION'
  ): Promise<{ document?: any; error?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/patients/${patientId}/documents`, {
        method: 'POST',
        headers,
        body: formData,
      });

      const json = await res.json().catch(() => null);
      if (!res.ok) {
        return { error: json?.error?.message || `HTTP ${res.status}: Upload failed` };
      }
      return { document: json?.data || json };
    } catch (err: any) {
      return { error: err.message || 'Network error during document upload' };
    }
  }

  // =========================================================================
  // Phase 7: Medication Safety Checking
  // =========================================================================
  async checkProspectiveMedications(
    patientId: string,
    drugNames: Array<{ name: string; strength?: string; route?: string }>
  ): Promise<{ evaluation?: BackendSafetyEvaluation; error?: string }> {
    const payload = {
      medications: drugNames.map(d => ({
        name: d.name,
        strength: d.strength || 'Standard',
        route: d.route || 'Oral',
      })),
      include_current_medications: true,
    };

    const res = await this.request<BackendSafetyEvaluation>(
      `/patients/${patientId}/medication-safety/check-medications`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );

    return { evaluation: res.data, error: res.error };
  }

  async checkActiveMedicationsSafety(
    patientId: string
  ): Promise<{ evaluation?: BackendSafetyEvaluation; error?: string }> {
    const res = await this.request<BackendSafetyEvaluation>(
      `/patients/${patientId}/medication-safety/check`,
      {
        method: 'POST',
        body: JSON.stringify({ include_all_active: true }),
      }
    );
    return { evaluation: res.data, error: res.error };
  }

  // =========================================================================
  // Phase 9: Personalized Care Plans
  // =========================================================================
  async getPatientCarePlans(patientId: string): Promise<{ carePlans?: BackendCarePlan[]; error?: string }> {
    const res = await this.request<{ items: BackendCarePlan[] }>(
      `/patients/${patientId}/care-plans`,
      { method: 'GET' }
    );
    return { carePlans: res.data?.items || [], error: res.error };
  }

  // =========================================================================
  // Phase 10: Doctor Clinical Workspace
  // =========================================================================
  async getDoctorWorkspace(patientId: string): Promise<{ workspace?: any; error?: string }> {
    const res = await this.request<any>(
      `/patients/${patientId}/clinical-workspace`,
      { method: 'GET' }
    );
    return { workspace: res.data, error: res.error };
  }

  async createPrescription(payload: any): Promise<{ prescription?: any; error?: string }> {
    const res = await this.request<any>('/prescriptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return { prescription: res.data, error: res.error };
  }

  // =========================================================================
  // Phase 11 & 12: Facilities & Capacity Discovery
  // =========================================================================
  async searchFacilities(name?: string): Promise<{ facilities?: BackendFacilityItem[]; error?: string }> {
    const q = name ? `?name=${encodeURIComponent(name)}` : '';
    const res = await this.request<{ items: BackendFacilityItem[] }>(
      `/facilities/search${q}`,
      { method: 'GET' }
    );
    return { facilities: res.data?.items || [], error: res.error };
  }

  async discoverFacilities(params?: {
    latitude?: number;
    longitude?: number;
    radius_km?: number;
    facility_type?: string;
  }): Promise<{ discovery?: any; error?: string }> {
    const searchParams = new URLSearchParams();
    if (params?.latitude) searchParams.set('latitude', params.latitude.toString());
    if (params?.longitude) searchParams.set('longitude', params.longitude.toString());
    if (params?.radius_km) searchParams.set('radius_km', params.radius_km.toString());
    if (params?.facility_type) searchParams.set('facility_type', params.facility_type);

    const q = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await this.request<any>(`/facilities/discover${q}`, { method: 'GET' });
    return { discovery: res.data, error: res.error };
  }

  // =========================================================================
  // Sovereign Profile & Longitudinal Record Persistence (Cross-Device)
  // =========================================================================
  async getProfile(identifier: string): Promise<{ profile?: any; error?: string }> {
    const res = await this.request<any>(`/auth/profile/${encodeURIComponent(identifier.trim())}`, {
      method: 'GET',
    });
    return { profile: res.data, error: res.error };
  }

  async getFullPatientRecord(patientId: string): Promise<{ record?: any; error?: string }> {
    const res = await this.request<any>(`/patients/${encodeURIComponent(patientId.trim())}/full-record`, {
      method: 'GET',
    });
    return { record: res.data, error: res.error };
  }

  async syncPatientRecord(patientId: string, payload: any): Promise<{ record?: any; error?: string }> {
    const res = await this.request<any>(`/patients/${encodeURIComponent(patientId.trim())}/full-record`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return { record: res.data, error: res.error };
  }

  // =========================================================================
  // Phase 26: Data Quality & Clinical Reconciliation
  // =========================================================================
  async getPatientDataQualityFindings(patientId: string, status?: string): Promise<{ findings?: DataQualityFinding[]; total?: number; error?: string }> {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    const res = await this.request<{ items: DataQualityFinding[]; total: number }>(
      `/patients/${encodeURIComponent(patientId.trim())}/data-quality${q}`,
      { method: 'GET' }
    );
    return { findings: res.data?.items || [], total: res.data?.total || 0, error: res.error };
  }

  async runPatientDataQualityCheck(patientId: string, body?: {
    resource_types?: string[];
    rule_types?: string[];
    external_imports?: any[];
  }): Promise<{ result?: any; error?: string }> {
    const res = await this.request<any>(
      `/patients/${encodeURIComponent(patientId.trim())}/data-quality/check`,
      {
        method: 'POST',
        body: JSON.stringify(body || {}),
      }
    );
    return { result: res.data, error: res.error };
  }

  async reviewDataQualityFinding(patientId: string, findingId: string, notes: string): Promise<{ finding?: DataQualityFinding; error?: string }> {
    const res = await this.request<DataQualityFinding>(
      `/patients/${encodeURIComponent(patientId.trim())}/data-quality/${encodeURIComponent(findingId)}/review`,
      {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }
    );
    return { finding: res.data, error: res.error };
  }

  async resolveDataQualityFinding(
    patientId: string,
    findingId: string,
    action: string,
    expectedVersion: number,
    reason: string,
    notes?: string
  ): Promise<{ finding?: DataQualityFinding; error?: string }> {
    const res = await this.request<DataQualityFinding>(
      `/patients/${encodeURIComponent(patientId.trim())}/data-quality/${encodeURIComponent(findingId)}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({
          action,
          expected_version: expectedVersion,
          reason,
          notes,
        }),
      }
    );
    return { finding: res.data, error: res.error };
  }

  async reconcilePatientRecords(
    patientId: string,
    scope: string = 'all',
    externalRecords: any[] = []
  ): Promise<{ reconciliation?: ClinicalReconciliation; error?: string }> {
    const res = await this.request<ClinicalReconciliation>(
      `/patients/${encodeURIComponent(patientId.trim())}/data-quality/reconcile`,
      {
        method: 'POST',
        body: JSON.stringify({
          scope,
          external_records: externalRecords,
        }),
      }
    );
    return { reconciliation: res.data, error: res.error };
  }

  async resolveReconciliation(
    patientId: string,
    reconciliationId: string,
    action: string,
    expectedVersion: number,
    reason: string
  ): Promise<{ reconciliation?: ClinicalReconciliation; error?: string }> {
    const res = await this.request<ClinicalReconciliation>(
      `/patients/${encodeURIComponent(patientId.trim())}/reconciliation/${encodeURIComponent(reconciliationId)}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({
          action,
          expected_version: expectedVersion,
          reason,
        }),
      }
    );
    return { reconciliation: res.data, error: res.error };
  }

  async getClinicianDataQualityFindings(): Promise<{ findings?: DataQualityFinding[]; total?: number; error?: string }> {
    const res = await this.request<{ items: DataQualityFinding[]; total: number }>(
      `/clinicians/me/data-quality/findings`,
      { method: 'GET' }
    );
    return { findings: res.data?.items || [], total: res.data?.total || 0, error: res.error };
  }

  // =====================================================================
  // Phase 27: Administration, Support Operations & Controlled Backoffice
  // =====================================================================

  async getAdminSystemHealth(): Promise<{ health?: AdminSystemHealth; error?: string }> {
    const res = await this.request<AdminSystemHealth>('/admin/health', { method: 'GET' });
    return { health: res.data, error: res.error };
  }

  async getAdminUsers(params?: {
    role?: string;
    is_active?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ users?: AdminUserRecord[]; total?: number; error?: string }> {
    const q = new URLSearchParams();
    if (params?.role) q.append('role', params.role);
    if (params?.is_active !== undefined) q.append('is_active', String(params.is_active));
    if (params?.search) q.append('search', params.search);
    if (params?.limit) q.append('limit', String(params.limit));
    if (params?.offset) q.append('offset', String(params.offset));

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{ items: AdminUserRecord[]; total: number }>(`/admin/users${qs}`, {
      method: 'GET',
    });
    return { users: res.data?.items || [], total: res.data?.total || 0, error: res.error };
  }

  async setAdminUserStatus(
    userId: string,
    isActive: boolean,
    reason: string
  ): Promise<{ success?: boolean; user?: AdminUserRecord; error?: string }> {
    const res = await this.request<AdminUserRecord>(
      `/admin/users/${encodeURIComponent(userId)}/status`,
      {
        method: 'POST',
        body: JSON.stringify({ is_active: isActive, reason }),
      }
    );
    return { success: !res.error, user: res.data, error: res.error };
  }

  async resetAdminUserMFA(
    userId: string,
    reason: string
  ): Promise<{ success?: boolean; error?: string }> {
    const res = await this.request<{ message: string }>(
      `/admin/users/${encodeURIComponent(userId)}/reset-mfa`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }
    );
    return { success: !res.error, error: res.error };
  }

  async getAdminIncidents(params?: {
    status?: string;
    severity?: string;
    category?: string;
    limit?: number;
  }): Promise<{ incidents?: OperationalIncident[]; total?: number; error?: string }> {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.severity) q.append('severity', params.severity);
    if (params?.category) q.append('category', params.category);
    if (params?.limit) q.append('limit', String(params.limit));

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{ items: OperationalIncident[]; total: number }>(
      `/admin/incidents${qs}`,
      { method: 'GET' }
    );
    return { incidents: res.data?.items || [], total: res.data?.total || 0, error: res.error };
  }

  async createAdminIncident(incident: {
    title: string;
    description: string;
    category: string;
    severity: string;
    owner?: string;
  }): Promise<{ incident?: OperationalIncident; error?: string }> {
    const res = await this.request<OperationalIncident>('/admin/incidents', {
      method: 'POST',
      body: JSON.stringify(incident),
    });
    return { incident: res.data, error: res.error };
  }

  async updateAdminIncident(
    incidentId: string,
    patch: {
      status?: string;
      severity?: string;
      owner?: string;
      resolution_summary?: string;
    }
  ): Promise<{ incident?: OperationalIncident; error?: string }> {
    const res = await this.request<OperationalIncident>(
      `/admin/incidents/${encodeURIComponent(incidentId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }
    );
    return { incident: res.data, error: res.error };
  }

  async resolveAdminIncident(
    incidentId: string,
    resolutionSummary: string
  ): Promise<{ incident?: OperationalIncident; error?: string }> {
    const res = await this.request<OperationalIncident>(
      `/admin/incidents/${encodeURIComponent(incidentId)}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolution_summary: resolutionSummary }),
      }
    );
    return { incident: res.data, error: res.error };
  }

  async getAdminAuditLogs(params?: {
    action?: string;
    limit?: number;
    actor_id?: string;
  }): Promise<{ logs?: any[]; total?: number; error?: string }> {
    const q = new URLSearchParams();
    if (params?.action) q.append('action', params.action);
    if (params?.limit) q.append('limit', String(params.limit));
    if (params?.actor_id) q.append('actor_id', params.actor_id);

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{ items: any[]; total: number }>(`/admin/audit-logs${qs}`, {
      method: 'GET',
    });
    return { logs: res.data?.items || [], total: res.data?.total || 0, error: res.error };
  }

  async createSupportSession(data: {
    reason: string;
    ticket_id?: string;
    target_user_id?: string;
    duration_minutes?: number;
  }): Promise<{ session?: SupportSessionRecord; error?: string }> {
    const res = await this.request<SupportSessionRecord>('/admin/support-sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return { session: res.data, error: res.error };
  }

  async getSupportSessions(): Promise<{ sessions?: SupportSessionRecord[]; error?: string }> {
    const res = await this.request<{ items: SupportSessionRecord[] }>('/admin/support-sessions', {
      method: 'GET',
    });
    return { sessions: res.data?.items || [], error: res.error };
  }

  // =====================================================================
  // Phase 28: API Analytics, Usage Governance & Operational Intelligence
  // =====================================================================

  async getAnalyticsOverview(params?: {
    window_minutes?: number;
    organization_id?: string;
    facility_id?: string;
  }): Promise<{ overview?: AnalyticsOverview; error?: string }> {
    const q = new URLSearchParams();
    if (params?.window_minutes) q.append('window_minutes', String(params.window_minutes));
    if (params?.organization_id) q.append('organization_id', params.organization_id);
    if (params?.facility_id) q.append('facility_id', params.facility_id);

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<AnalyticsOverview>(`/analytics/overview${qs}`, {
      method: 'GET',
    });
    return { overview: res.data, error: res.error };
  }

  async getLatencyDistribution(params?: {
    window_minutes?: number;
  }): Promise<{ percentiles?: LatencyPercentiles; distribution?: LatencyDistribution; error?: string }> {
    const q = new URLSearchParams();
    if (params?.window_minutes) q.append('window_minutes', String(params.window_minutes));

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{
      percentiles: LatencyPercentiles;
      distribution: LatencyDistribution;
    }>(`/analytics/latency${qs}`, { method: 'GET' });

    return {
      percentiles: res.data?.percentiles,
      distribution: res.data?.distribution,
      error: res.error,
    };
  }

  async getErrorAnalytics(params?: {
    window_minutes?: number;
  }): Promise<{ error_rate?: number; client_errors?: number; server_errors?: number; top_errors?: any[]; error?: string }> {
    const q = new URLSearchParams();
    if (params?.window_minutes) q.append('window_minutes', String(params.window_minutes));

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<any>(`/analytics/errors${qs}`, { method: 'GET' });
    return {
      error_rate: res.data?.error_rate_percentage,
      client_errors: res.data?.client_errors,
      server_errors: res.data?.server_errors,
      top_errors: res.data?.top_failing_endpoints || [],
      error: res.error,
    };
  }

  async getProviderUsage(params?: {
    window_minutes?: number;
  }): Promise<{ providers?: ProviderUsageMetric[]; total_cost_usd?: number; error?: string }> {
    const q = new URLSearchParams();
    if (params?.window_minutes) q.append('window_minutes', String(params.window_minutes));

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{ items: ProviderUsageMetric[]; total_estimated_cost_usd: number }>(
      `/analytics/providers${qs}`,
      { method: 'GET' }
    );
    return {
      providers: res.data?.items || [],
      total_cost_usd: res.data?.total_estimated_cost_usd,
      error: res.error,
    };
  }

  async getOperationalAnomalies(params?: {
    status?: string;
    severity?: string;
  }): Promise<{ anomalies?: OperationalAnomaly[]; error?: string }> {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.severity) q.append('severity', params.severity);

    const qs = q.toString() ? `?${q.toString()}` : '';
    const res = await this.request<{ items: OperationalAnomaly[] }>(`/analytics/anomalies${qs}`, {
      method: 'GET',
    });
    return { anomalies: res.data?.items || [], error: res.error };
  }

  async acknowledgeOperationalAnomaly(
    anomalyId: string,
    notes?: string
  ): Promise<{ anomaly?: OperationalAnomaly; error?: string }> {
    const res = await this.request<OperationalAnomaly>(
      `/analytics/anomalies/${encodeURIComponent(anomalyId)}/acknowledge`,
      {
        method: 'POST',
        body: JSON.stringify({ notes: notes || 'Acknowledged by operator' }),
      }
    );
    return { anomaly: res.data, error: res.error };
  }

  async resolveOperationalAnomaly(
    anomalyId: string,
    notes: string
  ): Promise<{ anomaly?: OperationalAnomaly; error?: string }> {
    const res = await this.request<OperationalAnomaly>(
      `/analytics/anomalies/${encodeURIComponent(anomalyId)}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolution_notes: notes }),
      }
    );
    return { anomaly: res.data, error: res.error };
  }
}

export const apiClient = new HealthSetuApiClient();


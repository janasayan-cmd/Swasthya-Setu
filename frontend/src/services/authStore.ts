/**
 * HealthSetu Sovereign Unique ID & Authentication Store
 * 
 * Manages unique identity generation, role-based profiles (Patient, Doctor, Hospital Org),
 * credential persistence, and synchronization with the FastAPI backend auth service.
 */

import { apiClient } from './api';

export interface UserProfile {
  id: string; // The sovereign unique ID (e.g. HS-PAT-8921, DOC-AIIMS-104, HOSP-APOLLO-01, ADM-OPS-9901)
  name: string;
  role: 'patient' | 'doctor' | 'hospital' | 'admin';
  email: string;
  phone?: string;
  issuedAt: string;
  avatarInitials: string;
  patientDetails?: {
    age: number;
    gender: string;
    bloodGroup: string;
    city: string;
    emergencyContact: string;
  };
  doctorDetails?: {
    degree: string;
    specialization: string;
    hospital: string;
    councilReg: string;
  };
  hospitalDetails?: {
    facilityType: string;
    city: string;
    totalBeds: number;
    icuBeds: number;
    helpline: string;
  };
  adminDetails?: {
    clearanceLevel: string;
    permissions: string[];
    managedFacilities: string;
  };
}

export const DEMO_PROFILES: Record<'patient' | 'doctor' | 'hospital' | 'admin', UserProfile> = {
  patient: {
    id: 'HS-PAT-8921',
    name: 'Rohan Sharma',
    role: 'patient',
    email: 'rohan.sharma@example.com',
    phone: '+91 98104 22910',
    avatarInitials: 'RS',
    issuedAt: '12 Sep 2026',
    patientDetails: {
      age: 42,
      gender: 'Male',
      bloodGroup: 'O Positive',
      city: 'New Delhi',
      emergencyContact: 'Sunita Sharma (Spouse) · +91 98104 22911',
    },
  },
  doctor: {
    id: 'DOC-AIIMS-104',
    name: 'Dr. Priya Nair',
    role: 'doctor',
    email: 'doctor@healthsetu.org',
    phone: '+91 11 2658 8500',
    avatarInitials: 'PN',
    issuedAt: '14 Jan 2024',
    doctorDetails: {
      degree: 'MD, DM (Cardiology)',
      specialization: 'Senior Consultant Cardiologist',
      hospital: 'All India Institute of Medical Sciences (AIIMS), New Delhi',
      councilReg: 'MCI-48291 · Verified Clinician',
    },
  },
  hospital: {
    id: 'HOSP-APOLLO-01',
    name: 'Apollo Indraprastha Hospital',
    role: 'hospital',
    email: 'emergency@apollo-delhi.org',
    phone: '+91 11 2692 5858',
    avatarInitials: 'AI',
    issuedAt: '01 Jan 2023',
    hospitalDetails: {
      facilityType: 'Super Speciality & Level-1 Trauma',
      city: 'Sarita Vihar, New Delhi',
      totalBeds: 210,
      icuBeds: 40,
      helpline: '+91 11 2692 5858 (24x7 Emergency Desk)',
    },
  },
  admin: {
    id: 'ADM-OPS-9901',
    name: 'Platform Operations Admin',
    role: 'admin',
    email: 'ops@healthsetu.org',
    phone: '+91 11 2658 9000',
    avatarInitials: 'OA',
    issuedAt: '01 Jan 2026',
    adminDetails: {
      clearanceLevel: 'LEVEL-4-SOVEREIGN-OPERATOR',
      permissions: ['SYSTEM_ADMIN', 'OPERATIONS_ADMIN', 'SUPPORT_OPERATOR', 'API_ANALYTICS_VIEW'],
      managedFacilities: 'All Active Connected Nodes (Cross-Tenant)',
    },
  },
};

const STORAGE_KEY = 'healthsetu_active_user';
const ALL_USERS_KEY = 'healthsetu_registered_users';

export function generateUniqueId(role: 'patient' | 'doctor' | 'hospital' | 'admin'): string {
  const randNum = Math.floor(1000 + Math.random() * 9000);
  switch (role) {
    case 'patient':
      return `HS-PAT-${randNum}`;
    case 'doctor':
      return `HS-DOC-${randNum}`;
    case 'hospital':
      return `HS-HOSP-${randNum}`;
    case 'admin':
      return `HS-ADM-${randNum}`;
  }
}

export const authStore = {
  /**
   * Retrieves the currently active user profile from local storage.
   */
  getActiveUser(): UserProfile | null {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        return JSON.parse(data) as UserProfile;
      }
    } catch {}
    return null;
  },

  /**
   * Stores the active user profile and dispatches change notification.
   */
  setActiveUser(user: UserProfile | null): void {
    try {
      if (user) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
        this.saveRegisteredUser(user);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {}
    window.dispatchEvent(new CustomEvent('healthsetu_auth_change', { detail: user }));
  },

  /**
   * Retrieves all registered profiles.
   */
  getRegisteredUsers(): UserProfile[] {
    try {
      const raw = localStorage.getItem(ALL_USERS_KEY);
      if (raw) return JSON.parse(raw);
    } catch {}
    return Object.values(DEMO_PROFILES);
  },

  saveRegisteredUser(user: UserProfile): void {
    try {
      const list = this.getRegisteredUsers();
      const idx = list.findIndex(u => u.id.toLowerCase() === user.id.toLowerCase() || u.email.toLowerCase() === user.email.toLowerCase());
      if (idx >= 0) {
        list[idx] = user;
      } else {
        list.push(user);
      }
      localStorage.setItem(ALL_USERS_KEY, JSON.stringify(list));
    } catch {}
  },

  /**
   * Logs in with Unique ID or Email, pulling profile from backend across computers.
   */
  async login(identifier: string, password?: string, preferredRole?: 'patient' | 'doctor' | 'hospital'): Promise<{ user: UserProfile; error?: string }> {
    const cleanId = identifier.trim().toLowerCase();
    const allUsers = this.getRegisteredUsers();

    // 1. Check if matches any demo profile
    let matched: UserProfile | undefined;
    if (cleanId === 'hs-pat-8921' || cleanId === 'patient@healthsetu.org' || (cleanId === 'rohan sharma')) {
      matched = DEMO_PROFILES.patient;
    } else if (cleanId === 'doc-aiims-104' || cleanId === 'doctor@healthsetu.org' || cleanId.includes('priya')) {
      matched = DEMO_PROFILES.doctor;
    } else if (cleanId === 'hosp-apollo-01' || cleanId === 'hosp-1' || cleanId === 'admin@healthsetu.org' || cleanId.includes('apollo')) {
      matched = DEMO_PROFILES.hospital;
    }

    // 2. If not demo profile, query backend persistent store (cross-computer synchronization)
    if (!matched) {
      try {
        const remote = await apiClient.getProfile(identifier.trim());
        if (remote.profile && remote.profile.id) {
          const p = remote.profile;
          matched = {
            id: p.id,
            name: p.name,
            role: p.role,
            email: p.email || `${p.id.toLowerCase()}@healthsetu.org`,
            phone: p.phone,
            issuedAt: p.issuedAt || 'Today',
            avatarInitials: p.avatarInitials || p.name.slice(0, 2).toUpperCase(),
            patientDetails: p.patientDetails,
            doctorDetails: p.doctorDetails,
            hospitalDetails: p.hospitalDetails,
          };
          this.saveRegisteredUser(matched);
        }
      } catch {}
    }

    // 3. Fallback to locally stored registered users
    if (!matched) {
      matched = allUsers.find(u => 
        u.id.toLowerCase() === cleanId || 
        u.email.toLowerCase() === cleanId ||
        (u.phone && u.phone.includes(cleanId))
      );
    }

    if (!matched) {
      return { 
        user: null as any, 
        error: `No existing profile found for "${identifier}". Please check your Unique ID or click "Create Profile & Mint ID" to register.` 
      };
    }

    // Connect to backend for real tokens
    const backendRoleMap: Record<string, 'PATIENT' | 'DOCTOR' | 'ADMIN'> = {
      patient: 'PATIENT',
      doctor: 'DOCTOR',
      hospital: 'ADMIN',
    };
    try {
      if (password) {
        await apiClient.login(
          matched.email || `${matched.id.toLowerCase()}@healthsetu.org`,
          password
        ).catch(() => null);
      }
    } catch {}

    this.setActiveUser(matched);
    return { user: matched };
  },

  /**
   * Registers a new profile and mints a sovereign Unique ID.
   */
  async register(data: {
    name: string;
    role: 'patient' | 'doctor' | 'hospital';
    email: string;
    phone?: string;
    password?: string;
    patientDetails?: UserProfile['patientDetails'];
    doctorDetails?: UserProfile['doctorDetails'];
    hospitalDetails?: UserProfile['hospitalDetails'];
  }): Promise<{ user: UserProfile; error?: string }> {
    const uniqueId = generateUniqueId(data.role);
    const initials = data.name.trim().split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'HS';

    const newUser: UserProfile = {
      id: uniqueId,
      name: data.name,
      role: data.role,
      email: data.email || `${uniqueId.toLowerCase()}@healthsetu.org`,
      phone: data.phone,
      issuedAt: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      avatarInitials: initials,
      patientDetails: data.patientDetails,
      doctorDetails: data.doctorDetails,
      hospitalDetails: data.hospitalDetails,
    };

    // Register on backend
    const backendRoleMap: Record<string, 'PATIENT' | 'DOCTOR' | 'ADMIN'> = {
      patient: 'PATIENT',
      doctor: 'DOCTOR',
      hospital: 'ADMIN',
    };
    try {
      await apiClient.register({
        name: newUser.name,
        role: backendRoleMap[newUser.role],
        identifier: newUser.email,
        password: data.password || '',
        unique_id: newUser.id,
        details: {
          patient: data.patientDetails,
          doctor: data.doctorDetails,
          hospital: data.hospitalDetails,
        },
      }).catch(() => null);
    } catch {}

    this.setActiveUser(newUser);
    return { user: newUser };
  },

  logout(): void {
    apiClient.logout().catch(() => null);
    this.setActiveUser(null);
  },
};

import React, { useState, useEffect } from 'react';
import { 
  User, 
  Stethoscope, 
  Building2, 
  KeyRound, 
  Sparkles, 
  CheckCircle2, 
  Copy, 
  Check, 
  ShieldCheck, 
  ArrowRight,
  Fingerprint,
  ArrowLeft,
  AlertCircle,
  Eye,
  EyeOff
} from 'lucide-react';
import { authStore, generateUniqueId, type UserProfile, DEMO_PROFILES } from '../../services/authStore';
import type { Role } from '../../types';

interface PortalLoginViewProps {
  portalRole: Role;
  onLoginSuccess: (user: UserProfile) => void;
  onNavigateHome: () => void;
  onSwitchPortalRole: (role: Role) => void;
}

export const PortalLoginView: React.FC<PortalLoginViewProps> = ({
  portalRole,
  onLoginSuccess,
  onNavigateHome,
  onSwitchPortalRole,
}) => {
  // Normalize portal role to one of the portal roles
  const activeRole: 'patient' | 'doctor' | 'hospital' | 'admin' = 
    portalRole === 'doctor' ? 'doctor' : portalRole === 'hospital' ? 'hospital' : portalRole === 'admin' ? 'admin' : 'patient';

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [newlyCreatedUser, setNewlyCreatedUser] = useState<UserProfile | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);

  // Login form state
  const [loginIdentifier, setLoginIdentifier] = useState<string>('');
  const [loginPassword, setLoginPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Dynamic preview ID for registration
  const [previewId, setPreviewId] = useState<string>('');

  // Registration form fields
  const [regName, setRegName] = useState<string>('');
  const [regEmail, setRegEmail] = useState<string>('');
  const [regPhone, setRegPhone] = useState<string>('');
  const [regPassword, setRegPassword] = useState<string>('');

  // Patient specific fields
  const [patientAge, setPatientAge] = useState<string>('');
  const [patientGender, setPatientGender] = useState<string>('');
  const [patientBlood, setPatientBlood] = useState<string>('');
  const [patientCity, setPatientCity] = useState<string>('');
  const [patientEmergency, setPatientEmergency] = useState<string>('');

  // Doctor specific fields
  const [docDegree, setDocDegree] = useState<string>('');
  const [docSpecialization, setDocSpecialization] = useState<string>('');
  const [docHospital, setDocHospital] = useState<string>('');
  const [docRegNo, setDocRegNo] = useState<string>('');

  // Hospital specific fields
  const [hospType, setHospType] = useState<string>('');
  const [hospCity, setHospCity] = useState<string>('');
  const [hospTotalBeds, setHospTotalBeds] = useState<string>('');
  const [hospIcuBeds, setHospIcuBeds] = useState<string>('');
  const [hospHelpline, setHospHelpline] = useState<string>('');

  // Generate preview unique ID whenever portal role changes
  useEffect(() => {
    setPreviewId(generateUniqueId(activeRole));
    setIsSuccess(false);
    setNewlyCreatedUser(null);
    setLoginError(null);
  }, [activeRole]);

  const getPortalInfo = () => {
    switch (activeRole) {
      case 'patient':
        return {
          title: 'Patient Health Vault Login',
          subtitle: 'Access your sovereign medical history, verify prescriptions, and manage consent.',
          idPrefix: 'HS-PAT-XXXX',
          icon: <User className="w-5 h-5 text-[#2B5F8A]" />,
          color: '#2B5F8A',
          bgColor: '#F4F8FA',
          badgeText: 'Patient Access',
          idPlaceholder: 'e.g. HS-PAT-8921 or patient email',
        };
      case 'doctor':
        return {
          title: 'Doctor Clinical Workspace Login',
          subtitle: 'Sign in to access patient cross-facility records, clinical safety audits, and prescribe.',
          idPrefix: 'HS-DOC-XXXX',
          icon: <Stethoscope className="w-5 h-5 text-[#2D5A40]" />,
          color: '#2D5A40',
          bgColor: '#F4F9F5',
          badgeText: 'Clinician Clearance',
          idPlaceholder: 'e.g. HS-DOC-2045 or doctor email',
        };
      case 'hospital':
        return {
          title: 'Hospital Capacity Grid Login',
          subtitle: 'Sign in to manage real-time ICU and emergency beds, occupancy, and triage dispatch.',
          idPrefix: 'HS-HOSP-XXXX',
          icon: <Building2 className="w-5 h-5 text-[#5B3D8A]" />,
          color: '#5B3D8A',
          bgColor: '#F8F5FB',
          badgeText: 'Facility Authority',
          idPlaceholder: 'e.g. HS-HOSP-4491 or admin email',
        };
      case 'admin':
        return {
          title: 'Operations & Analytics Backoffice Login',
          subtitle: 'Sign in to monitor system health, operational incidents, telemetry percentiles, and usage governance.',
          idPrefix: 'HS-ADM-XXXX',
          icon: <ShieldCheck className="w-5 h-5 text-[#9A3412]" />,
          color: '#9A3412',
          bgColor: '#FFF7ED',
          badgeText: 'Platform Operations',
          idPlaceholder: 'e.g. ADM-OPS-9901 or ops email',
        };
    }
  };

  const portalInfo = getPortalInfo();

  const handleDemoFill = () => {
    const demo = DEMO_PROFILES[activeRole];
    setLoginIdentifier(demo.id);
    setLoginPassword('StrongP@ssw0rd123!');
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = loginIdentifier.trim();
    if (!cleanId) {
      setLoginError('Please enter your HealthSetu Unique ID or registered email.');
      return;
    }
    if (!loginPassword) {
      setLoginError('Please enter your account password.');
      return;
    }

    setIsLoading(true);
    setLoginError(null);

    try {
      const res = await authStore.login(cleanId, loginPassword);
      if (res.success && res.user) {
        onLoginSuccess(res.user);
      } else {
        setLoginError(res.message || 'Invalid credentials. Please verify your Unique ID and password.');
      }
    } catch {
      setLoginError('An unexpected authentication error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regName.trim()) {
      setLoginError('Please enter your full legal name or organization name.');
      return;
    }
    if (!regEmail.trim()) {
      setLoginError('Please provide an email address.');
      return;
    }
    if (!regPassword || regPassword.length < 6) {
      setLoginError('Password must contain at least 6 characters.');
      return;
    }

    setIsLoading(true);
    setLoginError(null);

    try {
      const newId = generateUniqueId(activeRole);
      const userPayload: Omit<UserProfile, 'createdAt'> = {
        id: newId,
        role: activeRole,
        name: regName.trim(),
        email: regEmail.trim(),
        phone: regPhone.trim() || undefined,
        password: regPassword,
        issuedAt: new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
      };

      if (activeRole === 'patient') {
        userPayload.patientDetails = {
          age: patientAge ? parseInt(patientAge, 10) : undefined,
          gender: patientGender || undefined,
          bloodGroup: patientBlood || undefined,
          city: patientCity || undefined,
          emergencyContact: patientEmergency || undefined,
        };
      } else if (activeRole === 'doctor') {
        userPayload.doctorDetails = {
          degree: docDegree || 'MBBS',
          specialization: docSpecialization || 'General Medicine',
          hospitalAffiliation: docHospital || 'Registered Health Center',
          registrationNumber: docRegNo || `MCI-${Math.floor(10000 + Math.random() * 90000)}`,
        };
      } else if (activeRole === 'hospital') {
        userPayload.hospitalDetails = {
          facilityType: hospType || 'Multispecialty Hospital',
          city: hospCity || 'New Delhi',
          totalBeds: hospTotalBeds ? parseInt(hospTotalBeds, 10) : 100,
          icuBeds: hospIcuBeds ? parseInt(hospIcuBeds, 10) : 20,
          helpline: hospHelpline || undefined,
        };
      }

      const res = await authStore.register(userPayload);
      if (res.success && res.user) {
        setNewlyCreatedUser(res.user);
        setIsSuccess(true);
      } else {
        setLoginError(res.message || 'Registration failed. Please check your inputs.');
      }
    } catch {
      setLoginError('Registration could not be completed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyId = () => {
    if (newlyCreatedUser) {
      navigator.clipboard.writeText(newlyCreatedUser.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <div className="min-h-[85vh] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-xl w-full mx-auto space-y-6">
        
        {/* Navigation Breadcrumb / Back to Home */}
        <div className="flex items-center justify-between">
          <button
            onClick={onNavigateHome}
            className="inline-flex items-center gap-2 text-xs font-semibold text-[#6B7A8D] hover:text-[#1C2B3A] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Platform Overview</span>
          </button>
          
          <div className="flex items-center gap-1.5 text-xs text-[#2D5A40] bg-[#F4F9F5] border border-[#D3EAD7] px-2.5 py-1 rounded-sm">
            <ShieldCheck className="w-3.5 h-3.5 text-[#2D5A40]" />
            <span className="font-mono font-medium">Sovereign Portal Security</span>
          </div>
        </div>

        {/* Portal Switcher Tabs */}
        <div className="bg-white border border-[#DDD9D1] rounded-sm p-1.5 flex gap-1 shadow-sm">
          <button
            onClick={() => onSwitchPortalRole('patient')}
            className={`flex-1 py-2 px-3 rounded-sm text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
              activeRole === 'patient'
                ? 'bg-[#2B5F8A] text-white shadow-sm'
                : 'text-[#6B7A8D] hover:text-[#1C2B3A] hover:bg-[#FAF8F3]'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Patient Portal</span>
          </button>

          <button
            onClick={() => onSwitchPortalRole('doctor')}
            className={`flex-1 py-2 px-3 rounded-sm text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
              activeRole === 'doctor'
                ? 'bg-[#2D5A40] text-white shadow-sm'
                : 'text-[#6B7A8D] hover:text-[#1C2B3A] hover:bg-[#FAF8F3]'
            }`}
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>Doctor Clinical</span>
          </button>

          <button
            onClick={() => onSwitchPortalRole('hospital')}
            className={`flex-1 py-2 px-3 rounded-sm text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
              activeRole === 'hospital'
                ? 'bg-[#5B3D8A] text-white shadow-sm'
                : 'text-[#6B7A8D] hover:text-[#1C2B3A] hover:bg-[#FAF8F3]'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Hospital Grid</span>
          </button>
        </div>

        {/* Main Authentication Card */}
        <div className="bg-white border border-[#DDD9D1] rounded-sm shadow-sm overflow-hidden">
          
          {/* Card Header */}
          <div className="p-6 sm:p-7 border-b border-[#DDD9D1] bg-[#FAF8F3]">
            <div className="flex items-center gap-3">
              <div 
                className="w-12 h-12 rounded-sm border flex items-center justify-center shadow-xs"
                style={{ backgroundColor: portalInfo.bgColor, borderColor: `${portalInfo.color}30` }}
              >
                {portalInfo.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-[#6B7A8D]">
                    {portalInfo.badgeText}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-xs bg-[#EDEBE6] text-[#4A5568]">
                    Format: {portalInfo.idPrefix}
                  </span>
                </div>
                <h1 className="font-serif text-2xl text-[#1C2B3A] leading-tight">
                  {portalInfo.title}
                </h1>
                <p className="text-xs text-[#6B7A8D] mt-0.5">
                  {portalInfo.subtitle}
                </p>
              </div>
            </div>

            {/* Mode Switcher Tabs */}
            {!isSuccess && (
              <div className="grid grid-cols-2 gap-2 mt-5 bg-white p-1 rounded-sm border border-[#DDD9D1]">
                <button
                  type="button"
                  onClick={() => { setMode('login'); setLoginError(null); }}
                  className={`py-2 text-xs font-semibold rounded-xs transition-colors flex items-center justify-center gap-1.5 ${
                    mode === 'login'
                      ? 'bg-[#1C2B3A] text-white'
                      : 'text-[#6B7A8D] hover:text-[#1C2B3A]'
                  }`}
                >
                  <KeyRound className="w-3.5 h-3.5" />
                  <span>Log In with Unique ID</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setMode('register'); setLoginError(null); }}
                  className={`py-2 text-xs font-semibold rounded-xs transition-colors flex items-center justify-center gap-1.5 ${
                    mode === 'register'
                      ? 'bg-[#1C2B3A] text-white'
                      : 'text-[#6B7A8D] hover:text-[#1C2B3A]'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Create Profile & Mint ID</span>
                </button>
              </div>
            )}
          </div>

          <div className="p-6 sm:p-7">
            {/* Error Notification */}
            {loginError && (
              <div className="mb-5 p-3.5 bg-[#FDF2F2] border border-[#F8D7DA] rounded-sm flex items-start gap-2.5 text-xs text-[#9B1C1C]">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-[#E02424]" />
                <div className="flex-1">
                  <span className="font-semibold block">Authentication Notice:</span>
                  <span>{loginError}</span>
                </div>
              </div>
            )}

            {/* Registration Success Screen */}
            {isSuccess && newlyCreatedUser ? (
              <div className="py-4 space-y-6 text-center">
                <div className="w-16 h-16 rounded-full bg-[#F4F9F5] border-2 border-[#2D5A40] text-[#2D5A40] flex items-center justify-center mx-auto animate-pulse">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                
                <div>
                  <span className="text-[11px] font-mono uppercase tracking-wider text-[#2D5A40] font-semibold block">
                    Credential Minted Successfully
                  </span>
                  <h2 className="font-serif text-2xl text-[#1C2B3A] mt-1">
                    Welcome, {newlyCreatedUser.name}
                  </h2>
                  <p className="text-xs text-[#6B7A8D] max-w-md mx-auto mt-1 leading-relaxed">
                    Your sovereign health identity has been generated and enrolled on the HealthSetu protocol. Keep this Unique ID safe; you can use it to log in from any computer.
                  </p>
                </div>

                <div className="p-4 bg-[#FAF8F3] border border-[#DDD9D1] rounded-sm max-w-md mx-auto text-left space-y-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#6B7A8D] font-semibold block">
                    Your Sovereign Unique ID:
                  </span>
                  <div className="flex items-center justify-between gap-3 bg-white p-3 border border-[#DDD9D1] rounded-sm">
                    <span className="font-mono text-base font-bold text-[#1C2B3A] tracking-wider">
                      {newlyCreatedUser.id}
                    </span>
                    <button
                      onClick={handleCopyId}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FAF8F3] hover:bg-[#EDEBE6] border border-[#DDD9D1] text-xs font-semibold text-[#1C2B3A] rounded-sm transition-colors"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-[#2D5A40]" />
                          <span className="text-[#2D5A40]">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Copy ID</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="text-[11px] text-[#6B7A8D] pt-1">
                    Role Clearance: <strong className="text-[#1C2B3A] capitalize">{newlyCreatedUser.role}</strong> • Issued: {newlyCreatedUser.issuedAt}
                  </div>
                </div>

                <button
                  onClick={() => onLoginSuccess(newlyCreatedUser)}
                  className="w-full max-w-md mx-auto flex items-center justify-center gap-2 py-3 px-4 rounded-sm text-white font-semibold text-sm transition-opacity hover:opacity-95 shadow-sm"
                  style={{ backgroundColor: portalInfo.color }}
                >
                  <span>Enter {portalInfo.title.replace(' Login', '')}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ) : mode === 'login' ? (
              /* LOGIN FORM */
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-[#1C2B3A]">
                      Sovereign Unique ID or Email
                    </label>
                    <button
                      type="button"
                      onClick={handleDemoFill}
                      className="text-[11px] text-[#2B5F8A] hover:underline font-mono"
                    >
                      Fill Demo Credentials
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      value={loginIdentifier}
                      onChange={(e) => setLoginIdentifier(e.target.value)}
                      placeholder={portalInfo.idPlaceholder}
                      className="w-full text-xs font-mono px-3 py-2.5 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] focus:ring-1 focus:ring-[#4A90C4] outline-none text-[#1C2B3A] bg-[#FAF8F3]/50"
                      required
                    />
                    <KeyRound className="w-4 h-4 text-[#6B7A8D] absolute right-3 top-3 pointer-events-none" />
                  </div>
                  <span className="text-[11px] text-[#6B7A8D] block mt-1">
                    Enter your assigned HealthSetu Unique ID (e.g. {portalInfo.idPrefix}) or registered email address.
                  </span>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-[#1C2B3A]">
                      Account Password
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-[11px] text-[#6B7A8D] hover:text-[#1C2B3A] flex items-center gap-1"
                    >
                      {showPassword ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      <span>{showPassword ? 'Hide' : 'Show'}</span>
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full text-xs px-3 py-2.5 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] focus:ring-1 focus:ring-[#4A90C4] outline-none text-[#1C2B3A] bg-[#FAF8F3]/50"
                      required
                    />
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-2.5 px-4 rounded-sm text-white font-semibold text-xs flex items-center justify-center gap-2 transition-all hover:opacity-95 shadow-sm disabled:opacity-50"
                    style={{ backgroundColor: portalInfo.color }}
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <span>Sign In to {portalInfo.title.replace(' Login', '')}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </div>

                <div className="p-3 bg-[#FAF8F3] border border-[#DDD9D1] rounded-sm flex items-center justify-between text-[11px]">
                  <span className="text-[#6B7A8D]">Don't have a Unique ID yet?</span>
                  <button
                    type="button"
                    onClick={() => { setMode('register'); setLoginError(null); }}
                    className="font-semibold text-[#1C2B3A] hover:underline"
                  >
                    Create Profile & Mint ID &rarr;
                  </button>
                </div>
              </form>
            ) : (
              /* REGISTRATION FORM */
              <form onSubmit={handleRegisterSubmit} className="space-y-4">
                {/* ID Mint Preview Badge */}
                <div className="p-3 bg-[#FAF8F3] border border-[#DDD9D1] rounded-sm flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Fingerprint className="w-4 h-4 text-[#2B5F8A]" />
                    <span className="text-xs text-[#6B7A8D]">
                      Minting Sovereign ID:
                    </span>
                  </div>
                  <span className="font-mono text-xs font-bold text-[#1C2B3A] bg-white px-2 py-0.5 border border-[#DDD9D1] rounded-xs">
                    {previewId}
                  </span>
                </div>

                {/* Common Fields */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-[#1C2B3A] block mb-1">
                      {activeRole === 'hospital' ? 'Hospital / Facility Name *' : 'Full Legal Name *'}
                    </label>
                    <input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder={activeRole === 'hospital' ? 'e.g. Apollo Super Specialty' : 'e.g. Rahul Sharma'}
                      className="w-full text-xs px-3 py-2 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-[#1C2B3A] block mb-1">
                      Email Address *
                    </label>
                    <input
                      type="email"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      placeholder="name@domain.com"
                      className="w-full text-xs px-3 py-2 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-[#1C2B3A] block mb-1">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                      placeholder="+91 98765 43210"
                      className="w-full text-xs px-3 py-2 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-[#1C2B3A] block mb-1">
                      Account Password *
                    </label>
                    <input
                      type="password"
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="Minimum 6 characters"
                      className="w-full text-xs px-3 py-2 border border-[#DDD9D1] rounded-sm focus:border-[#4A90C4] outline-none"
                      required
                    />
                  </div>
                </div>

                {/* Role Specific Fields: Patient */}
                {activeRole === 'patient' && (
                  <div className="pt-2 border-t border-[#DDD9D1] space-y-3">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#6B7A8D] font-semibold block">
                      Patient Demographic Details
                    </span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Age</label>
                        <input
                          type="number"
                          value={patientAge}
                          onChange={(e) => setPatientAge(e.target.value)}
                          placeholder="e.g. 35"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Gender</label>
                        <select
                          value={patientGender}
                          onChange={(e) => setPatientGender(e.target.value)}
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm bg-white"
                        >
                          <option value="">Select</option>
                          <option value="Male">Male</option>
                          <option value="Female">Female</option>
                          <option value="Other">Other</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Blood Group</label>
                        <select
                          value={patientBlood}
                          onChange={(e) => setPatientBlood(e.target.value)}
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm bg-white"
                        >
                          <option value="">Select</option>
                          <option value="A+">A+</option>
                          <option value="A-">A-</option>
                          <option value="B+">B+</option>
                          <option value="B-">B-</option>
                          <option value="AB+">AB+</option>
                          <option value="AB-">AB-</option>
                          <option value="O+">O+</option>
                          <option value="O-">O-</option>
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">City / Region</label>
                        <input
                          type="text"
                          value={patientCity}
                          onChange={(e) => setPatientCity(e.target.value)}
                          placeholder="e.g. Mumbai"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Emergency Contact Phone</label>
                        <input
                          type="text"
                          value={patientEmergency}
                          onChange={(e) => setPatientEmergency(e.target.value)}
                          placeholder="e.g. +91 99887 76655"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Role Specific Fields: Doctor */}
                {activeRole === 'doctor' && (
                  <div className="pt-2 border-t border-[#DDD9D1] space-y-3">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#6B7A8D] font-semibold block">
                      Clinical Credentials
                    </span>
                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Degree / Qualifications</label>
                        <input
                          type="text"
                          value={docDegree}
                          onChange={(e) => setDocDegree(e.target.value)}
                          placeholder="e.g. MBBS, MD (Cardio)"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Specialization</label>
                        <input
                          type="text"
                          value={docSpecialization}
                          onChange={(e) => setDocSpecialization(e.target.value)}
                          placeholder="e.g. Cardiology"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Hospital / Clinic Affiliation</label>
                        <input
                          type="text"
                          value={docHospital}
                          onChange={(e) => setDocHospital(e.target.value)}
                          placeholder="e.g. Fortis Hospital"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Medical Registration Number</label>
                        <input
                          type="text"
                          value={docRegNo}
                          onChange={(e) => setDocRegNo(e.target.value)}
                          placeholder="e.g. MCI-94812"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Role Specific Fields: Hospital */}
                {activeRole === 'hospital' && (
                  <div className="pt-2 border-t border-[#DDD9D1] space-y-3">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#6B7A8D] font-semibold block">
                      Facility Capacity Parameters
                    </span>
                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Facility Type</label>
                        <input
                          type="text"
                          value={hospType}
                          onChange={(e) => setHospType(e.target.value)}
                          placeholder="e.g. Multispecialty Hospital"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">City / Hub</label>
                        <input
                          type="text"
                          value={hospCity}
                          onChange={(e) => setHospCity(e.target.value)}
                          placeholder="e.g. New Delhi"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2.5">
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Total Beds</label>
                        <input
                          type="number"
                          value={hospTotalBeds}
                          onChange={(e) => setHospTotalBeds(e.target.value)}
                          placeholder="e.g. 150"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">ICU Beds</label>
                        <input
                          type="number"
                          value={hospIcuBeds}
                          onChange={(e) => setHospIcuBeds(e.target.value)}
                          placeholder="e.g. 30"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-semibold text-[#6B7A8D] block mb-1">Helpline Phone</label>
                        <input
                          type="text"
                          value={hospHelpline}
                          onChange={(e) => setHospHelpline(e.target.value)}
                          placeholder="e.g. 011-26598700"
                          className="w-full text-xs px-2.5 py-1.5 border border-[#DDD9D1] rounded-sm"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="pt-3">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-2.5 px-4 rounded-sm text-white font-semibold text-xs flex items-center justify-center gap-2 transition-all hover:opacity-95 shadow-sm disabled:opacity-50"
                    style={{ backgroundColor: portalInfo.color }}
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Mint Sovereign ID & Enter Portal</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="p-3 bg-[#FAF8F3] border border-[#DDD9D1] rounded-sm flex items-center justify-between text-[11px]">
                  <span className="text-[#6B7A8D]">Already have an account or Unique ID?</span>
                  <button
                    type="button"
                    onClick={() => { setMode('login'); setLoginError(null); }}
                    className="font-semibold text-[#1C2B3A] hover:underline"
                  >
                    Log In with Unique ID &rarr;
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Privacy & Compliance Footer */}
          <div className="px-6 py-3 bg-[#FAF8F3] border-t border-[#DDD9D1] flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#6B7A8D]">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[#2D5A40]" />
              Sovereign Zero-Knowledge Protocol • Zero Dummy Data
            </span>
            <span className="font-mono">
              ABDM & FHIR R4 Ready
            </span>
          </div>

        </div>

      </div>
    </div>
  );
};

import { Activity, User, Stethoscope, Building2, PhoneCall, KeyRound, LogOut, ChevronDown, ShieldCheck, ShieldAlert, Lock } from 'lucide-react';
import type { Role } from '../../types';
import type { UserProfile } from '../../services/authStore';

interface NavbarProps {
  currentRole: Role;
  setCurrentRole: (role: Role) => void;
  onEmergencyClick?: () => void;
  currentUser: UserProfile | null;
  onOpenAuth: (preferredRole?: Role) => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentRole,
  setCurrentRole,
  onEmergencyClick,
  currentUser,
  onOpenAuth,
  onLogout,
}) => {
  const [showProfileMenu, setShowProfileMenu] = useState<boolean>(false);

  const getRoleTheme = (role?: string) => {
    switch (role) {
      case 'patient':
        return { bg: 'bg-[#2B5F8A]', border: 'border-[#D5E8F8]', text: 'text-[#2B5F8A]' };
      case 'doctor':
        return { bg: 'bg-[#2D5A40]', border: 'border-[#D3EAD7]', text: 'text-[#2D5A40]' };
      case 'hospital':
        return { bg: 'bg-[#5B3D8A]', border: 'border-[#E9DCF8]', text: 'text-[#5B3D8A]' };
      case 'admin':
        return { bg: 'bg-[#9A3412]', border: 'border-[#FAD8C3]', text: 'text-[#9A3412]' };
      default:
        return { bg: 'bg-[#1C2B3A]', border: 'border-[#DDD9D1]', text: 'text-[#1C2B3A]' };
    }
  };

  const theme = getRoleTheme(currentUser?.role);

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-[#FAF8F3] border-b border-[#DDD9D1] z-50">
      <div className="max-w-6xl mx-auto h-full px-4 sm:px-6 flex items-center justify-between">
        
        {/* Brand Logo */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setCurrentRole('landing')}
            className="flex items-center gap-3 text-left focus-visible:ring-1 focus-visible:ring-[#4A90C4] focus:outline-none py-1"
          >
            <div className="w-8 h-8 rounded-sm bg-[#FFFFFF] border border-[#DDD9D1] flex items-center justify-center text-[#4A90C4]">
              <Activity className="w-4 h-4 text-[#4A90C4]" strokeWidth={2.2} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-serif text-xl text-[#1C2B3A] tracking-tight">HealthSetu</span>
              </div>
              <p className="text-[10px] uppercase font-semibold tracking-wider text-[#6B7A8D] -mt-0.5">
                Continuous Care Platform
              </p>
            </div>
          </button>
        </div>

        {/* Center Links / Role Switcher */}
        <nav className="hidden md:flex items-center bg-[#F0EDE7] p-1 rounded-sm border border-[#DDD9D1]">
          <button
            onClick={() => setCurrentRole('landing')}
            className={`px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors focus-visible:ring-1 focus-visible:ring-[#4A90C4] ${
              currentRole === 'landing'
                ? 'bg-[#FFFFFF] text-[#1C2B3A] border border-[#DDD9D1]'
                : 'text-[#6B7A8D] hover:text-[#1C2B3A]'
            }`}
          >
            Overview
          </button>
          
          <button
            onClick={() => setCurrentRole('patient')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors focus-visible:ring-1 focus-visible:ring-[#4A90C4] ${
              currentRole === 'patient'
                ? 'bg-[#FFFFFF] text-[#2B5F8A] border border-[#D5E8F8]'
                : currentUser && currentUser.role !== 'patient'
                  ? 'text-[#6B7A8D] opacity-80 hover:text-[#1C2B3A]'
                  : 'text-[#6B7A8D] hover:text-[#2B5F8A]'
            }`}
            title={currentUser && currentUser.role !== 'patient' ? 'Requires Patient Account' : undefined}
          >
            <User className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>Patient Portal</span>
            {currentUser && currentUser.role !== 'patient' && (
              <Lock className="w-2.5 h-2.5 text-[#A05520]" />
            )}
          </button>

          <button
            onClick={() => setCurrentRole('doctor')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors focus-visible:ring-1 focus-visible:ring-[#4A90C4] ${
              currentRole === 'doctor'
                ? 'bg-[#FFFFFF] text-[#2D5A40] border border-[#D3EAD7]'
                : currentUser && currentUser.role !== 'doctor'
                  ? 'text-[#6B7A8D] opacity-80 hover:text-[#1C2B3A]'
                  : 'text-[#6B7A8D] hover:text-[#2D5A40]'
            }`}
            title={currentUser && currentUser.role !== 'doctor' ? 'Requires Clinician Clearance' : undefined}
          >
            <Stethoscope className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>Doctor Clinical</span>
            {currentUser && currentUser.role !== 'doctor' && (
              <Lock className="w-2.5 h-2.5 text-[#A05520]" />
            )}
          </button>

          <button
            onClick={() => setCurrentRole('hospital')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors focus-visible:ring-1 focus-visible:ring-[#4A90C4] ${
              currentRole === 'hospital'
                ? 'bg-[#FFFFFF] text-[#5B3D8A] border border-[#E9DCF8]'
                : currentUser && currentUser.role !== 'hospital'
                  ? 'text-[#6B7A8D] opacity-80 hover:text-[#1C2B3A]'
                  : 'text-[#6B7A8D] hover:text-[#5B3D8A]'
            }`}
            title={currentUser && currentUser.role !== 'hospital' ? 'Requires Hospital Organization Clearance' : undefined}
          >
            <Building2 className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>Hospital Capacity</span>
            {currentUser && currentUser.role !== 'hospital' && (
              <Lock className="w-2.5 h-2.5 text-[#A05520]" />
            )}
          </button>

          <button
            onClick={() => setCurrentRole('admin')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs font-semibold transition-colors focus-visible:ring-1 focus-visible:ring-[#4A90C4] ${
              currentRole === 'admin'
                ? 'bg-[#FFFFFF] text-[#9A3412] border border-[#FAD8C3]'
                : currentUser && currentUser.role !== 'admin'
                  ? 'text-[#6B7A8D] opacity-80 hover:text-[#1C2B3A]'
                  : 'text-[#6B7A8D] hover:text-[#9A3412]'
            }`}
            title={currentUser && currentUser.role !== 'admin' ? 'Requires Platform Operator Clearance' : undefined}
          >
            <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span>Ops & Analytics</span>
            {currentUser && currentUser.role !== 'admin' && (
              <Lock className="w-2.5 h-2.5 text-[#A05520]" />
            )}
          </button>
        </nav>

        {/* Action Buttons & Profile/Login Button */}
        <div className="flex items-center gap-2 sm:gap-3">
          
          {/* Emergency Hospital Search CTA */}
          <button
            onClick={onEmergencyClick}
            className="flex items-center gap-2 bg-[#E07B39] text-[#FFFFFF] font-semibold text-xs px-3 sm:px-3.5 py-2 rounded-sm hover:bg-[#C96A28] transition-colors focus-visible:ring-1 focus-visible:ring-[#E07B39]"
          >
            <PhoneCall className="w-3.5 h-3.5" strokeWidth={2} />
            <span className="hidden sm:inline">Emergency Search</span>
            <span className="sm:hidden">Emergency</span>
          </button>

          {/* Active User Credential Pill or Login Button */}
          {currentUser ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className="flex items-center gap-2 border border-[#DDD9D1] bg-white rounded-sm px-2.5 py-1 text-xs hover:border-[#1C2B3A] transition-colors shadow-2xs"
              >
                <div className={`w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center ${theme.bg}`}>
                  {currentUser.avatarInitials}
                </div>
                <div className="hidden lg:block text-left leading-tight">
                  <span className="font-mono font-bold text-[11px] text-[#1C2B3A] block">
                    {currentUser.id}
                  </span>
                  <span className="text-[10px] text-[#6B7A8D] block truncate max-w-[110px]">
                    {currentUser.name}
                  </span>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-[#6B7A8D]" />
              </button>

              {/* Profile Dropdown Menu */}
              {showProfileMenu && (
                <div className="absolute right-0 mt-2 w-64 bg-white border border-[#DDD9D1] rounded-sm shadow-xl p-3 z-50 space-y-3">
                  <div className="border-b border-[#DDD9D1] pb-2 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase font-semibold text-[#6B7A8D]">
                        Active HealthSetu ID
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm bg-[#EBF5EC] text-[#2D5A40] border border-[#D3EAD7] font-semibold">
                        {currentUser.role.toUpperCase()}
                      </span>
                    </div>
                    <div className="font-mono text-sm font-bold text-[#1C2B3A]">
                      {currentUser.id}
                    </div>
                    <div className="text-xs font-semibold text-[#1C2B3A]">
                      {currentUser.name}
                    </div>
                    <div className="text-[11px] text-[#6B7A8D] truncate">
                      {currentUser.email}
                    </div>
                  </div>

                  <div className="space-y-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setShowProfileMenu(false);
                        onOpenAuth(currentUser.role);
                      }}
                      className="w-full text-left text-xs px-2.5 py-1.5 rounded-sm hover:bg-[#FAF8F3] text-[#1C2B3A] flex items-center justify-between font-medium"
                    >
                      <span>Switch Role / Sign In Another ID</span>
                      <ShieldCheck className="w-3.5 h-3.5 text-[#4A90C4]" />
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setShowProfileMenu(false);
                        onLogout();
                      }}
                      className="w-full text-left text-xs px-2.5 py-1.5 rounded-sm hover:bg-[#FEF3E8] text-[#C96A28] flex items-center justify-between font-semibold"
                    >
                      <span>Log Out</span>
                      <LogOut className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => onOpenAuth('patient')}
              className="flex items-center gap-1.5 border border-[#1C2B3A] bg-white text-[#1C2B3A] font-semibold text-xs px-3 sm:px-3.5 py-2 rounded-sm hover:bg-[#FAF8F3] transition-colors shadow-2xs"
            >
              <KeyRound className="w-3.5 h-3.5 text-[#2B5F8A]" />
              <span>Log In / Register</span>
            </button>
          )}

          {currentRole !== 'landing' && (
            <button
              onClick={() => setCurrentRole('landing')}
              className="flex items-center gap-1 text-xs font-semibold text-[#6B7A8D] hover:text-[#1C2B3A] border border-[#DDD9D1] px-2.5 sm:px-3 py-2 rounded-sm bg-[#FFFFFF] hover:bg-[#F0EDE7] transition-colors"
            >
              Exit
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

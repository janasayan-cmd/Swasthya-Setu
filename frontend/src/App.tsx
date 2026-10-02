import React, { useState, useEffect, useRef } from 'react';
import Lenis from 'lenis';
import 'lenis/dist/lenis.css';
import { Navbar } from './components/common/Navbar';
import { Hero } from './components/landing/Hero';
import { TrustStrip } from './components/landing/TrustStrip';
import { RoleSection } from './components/landing/RoleSection';
import { HowItWorks } from './components/landing/HowItWorks';
import { FeaturesGrid } from './components/landing/FeaturesGrid';
import { EmergencySection } from './components/landing/EmergencySection';
import { CTA } from './components/landing/CTA';
import { Footer } from './components/landing/Footer';
import { PatientPortal } from './components/patient/PatientPortal';
import { DoctorWorkspace } from './components/doctor/DoctorWorkspace';
import { HospitalPortal } from './components/hospital/HospitalPortal';
import { AdminPortal } from './components/admin/AdminPortal';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { AccessRestricted } from './components/common/AccessRestricted';
import { PortalLoginView } from './components/auth/PortalLoginView';
import { AuthModal } from './components/auth/AuthModal';
import { authStore, type UserProfile } from './services/authStore';
import type { Role } from './types';

export function App() {
  const [currentRole, setCurrentRole] = useState<Role>('landing');
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => authStore.getActiveUser());
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [authModalRole, setAuthModalRole] = useState<Role>('patient');
  const lenisRef = useRef<Lenis | null>(null);

  // Sync auth state changes across windows/components
  useEffect(() => {
    const handleAuthChange = (e: any) => {
      setCurrentUser(e.detail || null);
    };
    window.addEventListener('healthsetu_auth_change', handleAuthChange);
    return () => window.removeEventListener('healthsetu_auth_change', handleAuthChange);
  }, []);

  // Initialize Lenis smooth momentum scrolling (inspired by MINEGUARD architecture)
  useEffect(() => {
    let lenis: Lenis | null = null;
    let rafId: number;

    try {
      lenis = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        wheelMultiplier: 1.05,
        touchMultiplier: 1.6,
        infinite: false,
      });

      lenisRef.current = lenis;
      (window as unknown as { __lenis: Lenis | null }).__lenis = lenis;

      function raf(time: number) {
        lenis?.raf(time);
        rafId = requestAnimationFrame(raf);
      }
      rafId = requestAnimationFrame(raf);
    } catch (e) {
      console.warn('Lenis smooth scrolling fallback to native:', e);
    }

    return () => {
      cancelAnimationFrame(rafId);
      try {
        lenis?.destroy();
      } catch {}
      lenisRef.current = null;
      (window as unknown as { __lenis: Lenis | null }).__lenis = null;
    };
  }, []);

  // Smooth scroll to top on role switch
  useEffect(() => {
    try {
      if (lenisRef.current && typeof lenisRef.current.scrollTo === 'function') {
        lenisRef.current.scrollTo(0, { immediate: true });
      } else {
        window.scrollTo({ top: 0, behavior: 'instant' as any });
      }
    } catch {
      window.scrollTo(0, 0);
    }
  }, [currentRole]);

  // Smooth gliding anchor navigation with Lenis offset compensation
  const scrollToEmergency = () => {
    try {
      if (currentRole !== 'landing') {
        setCurrentRole('landing');
        setTimeout(() => {
          const el = document.getElementById('emergency');
          if (el) {
            try {
              if (lenisRef.current) {
                lenisRef.current.scrollTo(el, { offset: -70, duration: 1.2 });
              } else {
                el.scrollIntoView({ behavior: 'smooth' });
              }
            } catch {
              el.scrollIntoView({ behavior: 'smooth' });
            }
          }
        }, 120);
      } else {
        const el = document.getElementById('emergency');
        if (el) {
          try {
            if (lenisRef.current) {
              lenisRef.current.scrollTo(el, { offset: -70, duration: 1.2 });
            } else {
              el.scrollIntoView({ behavior: 'smooth' });
            }
          } catch {
            el.scrollIntoView({ behavior: 'smooth' });
          }
        }
      }
    } catch {
      window.scrollTo(0, 0);
    }
  };

  const handleOpenAuth = (preferredRole?: Role) => {
    setAuthModalRole(preferredRole || (currentRole === 'landing' ? 'patient' : currentRole));
    setIsAuthModalOpen(true);
  };

  const handleLoginSuccess = (user: UserProfile) => {
    setCurrentUser(user);
    setCurrentRole(user.role);
  };

  const handleLogout = () => {
    authStore.logout();
    setCurrentUser(null);
    setCurrentRole('landing');
  };

  return (
    <div className="min-h-screen bg-[#FAF8F3] text-[#1C2B3A] font-sans antialiased flex flex-col selection:bg-[#4A90C4]/20 selection:text-[#1C2B3A] relative">

      {/* Global Navigation Bar */}
      <Navbar
        currentRole={currentRole}
        setCurrentRole={setCurrentRole}
        onEmergencyClick={scrollToEmergency}
        currentUser={currentUser}
        onOpenAuth={handleOpenAuth}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        <ErrorBoundary fallbackTitle="Portal Interface" onReset={() => setCurrentRole('landing')}>
          {currentRole === 'landing' && (
            <>
              <Hero 
                onSelectRole={setCurrentRole} 
                onEmergencyClick={scrollToEmergency} 
                onOpenAuth={handleOpenAuth}
                currentUser={currentUser}
              />
              <TrustStrip />
              <RoleSection onSelectRole={setCurrentRole} />
              <HowItWorks />
              <FeaturesGrid />
              <EmergencySection />
              <CTA onSelectRole={setCurrentRole} />
            </>
          )}

          {/* Protected Portal Views with Role-Based Access Control (RBAC) */}
          {currentRole !== 'landing' && (
            (() => {
              // 1. Unauthenticated Visitor Guard: Render Portal Login Interface for every portal
              if (!currentUser) {
                return (
                  <PortalLoginView
                    portalRole={currentRole}
                    onLoginSuccess={handleLoginSuccess}
                    onNavigateHome={() => setCurrentRole('landing')}
                    onSwitchPortalRole={(role) => setCurrentRole(role)}
                  />
                );
              }

              // 2. Cross-Role Clearance Guard (e.g. Patient trying to access Doctor or Hospital portal)
              if (currentUser.role !== currentRole) {
                return (
                  <AccessRestricted
                    attemptedRole={currentRole}
                    currentUser={currentUser}
                    onNavigateHome={() => setCurrentRole('landing')}
                    onNavigateAllowedPortal={(role) => setCurrentRole(role)}
                    onOpenAuth={(role) => handleOpenAuth(role)}
                  />
                );
              }

              // 3. Authorized Portals
              if (currentRole === 'patient') {
                return (
                  <PatientPortal 
                    onEmergencyClick={scrollToEmergency} 
                    currentUser={currentUser}
                  />
                );
              }

              if (currentRole === 'doctor') {
                return (
                  <DoctorWorkspace 
                    currentUser={currentUser}
                  />
                );
              }

              if (currentRole === 'hospital') {
                return (
                  <HospitalPortal 
                    currentUser={currentUser}
                  />
                );
              }

              if (currentRole === 'admin') {
                return (
                  <AdminPortal 
                    currentUser={currentUser}
                  />
                );
              }

              return null;
            })()
          )}
        </ErrorBoundary>
      </main>

      {/* Unified Sovereign Unique ID & Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        defaultRole={authModalRole}
        onLoginSuccess={handleLoginSuccess}
      />

      {/* Global Footer */}
      <Footer onSelectRole={setCurrentRole} />

    </div>
  );
}

export default App;

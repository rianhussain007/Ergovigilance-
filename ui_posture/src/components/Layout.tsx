import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router';
import Sidebar from './Sidebar';
import { Header } from '@/src/components/layout/Header';
import AIAssistantPanel from '@/src/components/layout/AIAssistantPanel';
import MonitoringControls from '@/src/components/layout/MonitoringControls';
import { useDashboard } from '@/src/hooks/useDashboard';
import { AlertCenter } from '@/src/components/common/AlertCenter';
import ErrorBoundary from '@/src/components/common/ErrorBoundary';
import { AnimatePresence, motion } from 'motion/react';
import { Brain, Bell, LogOut, UserCog, Shield, Users, HardHat, ChevronDown } from 'lucide-react';
import { useAuth, type Role } from '@/src/auth/AuthContext';
import { useAlertToasts } from '@/src/hooks/useAlertToasts';
import OnboardingFlow from '@/src/components/common/OnboardingFlow';
import { ProductTour, KeyboardHelpPanel, useKeyboardShortcuts, useProductTour, FloatingHelpButton } from '@/src/components/common/ProductTour';
import SkipLink from '@/src/components/common/SkipLink';
import { AccessDenied } from '@/src/components/common/AccessDenied';
import { useFocusOnNavigate } from '@/src/hooks/useFocusOnNavigate';
import { rolePaths, isPathAllowed } from '@/src/auth/routes';
import { isActivationComplete, completeActivation } from '@/src/services/activation';

const roleConfig: Record<Role, { label: string; icon: React.ElementType }> = {
  operator: { label: 'Operator', icon: HardHat },
  supervisor: { label: 'Supervisor', icon: Users },
  safety_mgr: { label: 'Safety Mgr', icon: Shield },
  admin: { label: 'Admin', icon: UserCog },
};


function UserMenu({ roleLabel, roleIcon: RoleIcon, email, onLogout }: { roleLabel: string; roleIcon: React.ElementType; email: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('mousedown', close);
    return () => window.removeEventListener('mousedown', close);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-sm h-9 px-sm rounded-lg border border-outline-variant bg-surface-container text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors"
        aria-label={`User menu for ${email}`}
        aria-expanded={open}
        aria-haspopup="true"
        title={`Signed in as ${email}`}
      >
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/15 text-primary">
          <RoleIcon className="w-3.5 h-3.5" />
        </span>
        <span className="text-[11px] font-bold uppercase hidden md:inline">{roleLabel}</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-xs w-56 rounded-lg border border-outline-variant bg-surface-container shadow-xl z-50 py-xs">
          <div className="px-md py-sm border-b border-outline-variant/50">
            <p className="text-body-sm font-bold text-on-surface">{roleLabel}</p>
            <p className="text-[11px] text-on-surface-variant truncate">{email}</p>
          </div>
          <button onClick={onLogout} aria-label="Sign out" className="w-full flex items-center gap-sm px-md py-sm text-body-sm text-red-400 hover:bg-surface-container-highest transition-colors">
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}

function DemoModeBanner({ isDemoMode }: { isDemoMode: boolean }) {
  const [dismissed, setDismissed] = useState(false);
  if (!isDemoMode || dismissed) return null;
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-center flex items-center justify-center gap-3">
      <p className="text-xs font-semibold text-amber-400">
        DEMO MODE — Showing synthetic data. No real camera or workers are connected.
      </p>
      <button
        onClick={() => setDismissed(true)}
        className="text-amber-400/60 hover:text-amber-400 transition-colors ml-2"
        title="Dismiss"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export default function Layout() {
  const { user, logout, isDemoMode, isDemoSession } = useAuth();
  const { dashboard } = useDashboard();
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 1024);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 1023px)');
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  // Auto-collapse sidebar when entering mobile
  useEffect(() => {
    if (isMobile) setSidebarCollapsed(true);
  }, [isMobile]);
  const [showOnboarding, setShowOnboarding] = useState(() => {
    // One activation store drives this modal (audit F-UX-17): the checklist at
    // /onboarding writes the same state, so finishing one journey never leaves
    // the other re-appearing on the next login.
    return !isActivationComplete() && !isDemoSession;
  });
  const location = useLocation();



  useAlertToasts(() => setNotifOpen(true));
  useFocusOnNavigate();

  // Product tour + keyboard shortcuts
  const { showTour, showHelp, startTour, dismissTour, setShowHelp, dismissHelp } = useProductTour();

  // Auto-start tour for demo mode users on first visit
  useEffect(() => {
    // "Try Demo" clears the dismissal key before login (see AuthContext), so
    // every demo entry starts the guided tour. We only suppress a re-show when
    // the user dismissed the tour moments ago (e.g. a page refresh right after
    // ending it) — short session window, NOT 24h.
    //
    // Keyed on isDemoSession (this browser entered via Try Demo) rather than
    // isDemoMode (what the server actually serves): the tour is a UX
    // affordance, while isDemoMode alone drives the data-provenance banner.
    if (isDemoSession) {
      const lastDismissed = localStorage.getItem('ergovigilance_tour_dismissed_at');
      const recentlyDismissed = lastDismissed && (Date.now() - Number(lastDismissed)) < 300000;
      if (!recentlyDismissed) {
        const timer = setTimeout(() => startTour(), 800);
        return () => clearTimeout(timer);
      }
    }
  }, [isDemoSession, startTour]);

  // Stable callbacks for keyboard shortcuts (prevent listener churn)
  const handleToggleSearch = useCallback(() => {
    window.dispatchEvent(new Event('opensearch'));
  }, []);
  const handleToggleHelp = useCallback(() => {
    setShowHelp((prev) => !prev);
  }, [setShowHelp]);

  useKeyboardShortcuts({
    onToggleSearch: handleToggleSearch,
    onToggleHelp: handleToggleHelp,
    tourActive: showTour,
  });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't close panels during tour — ProductTour handles Escape itself
      if (showTour) return;
      if (e.key === 'Escape') { setAiPanelOpen(false); setNotifOpen(false); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [showTour]);

  if (!user) return <Navigate to="/login" replace />;

  const role = user.role;
  const allowedPaths = rolePaths[role];
  // A forbidden path used to silently redirect to /dashboard (audit F-UX-02).
  // It now renders an explanation *inside* the layout, so the sidebar stays
  // usable and the page never fires requests its role cannot make.
  const pathAllowed = isPathAllowed(location.pathname, allowedPaths);

  const currentRole = roleConfig[role];
  const RoleIcon = currentRole.icon;

  if (showOnboarding) {
    return (
      <OnboardingFlow
        onComplete={() => {
          completeActivation();
          setShowOnboarding(false);
        }}
      />
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface text-on-surface">
      <SkipLink />
      <Sidebar role={role} rolePaths={rolePaths} collapsed={sidebarCollapsed} onCollapsedChange={setSidebarCollapsed} isMobile={isMobile} />
      <div className={`flex flex-col flex-1 min-w-0 transition-[margin] duration-300 ease-out ${isMobile ? 'ml-0' : sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        <Header
          session={dashboard?.session || null}
        />

        <div className="px-lg pt-md pb-0 space-y-md">
          <div className="flex items-center gap-md flex-wrap">
            {/* Mobile hamburger menu */}
            {isMobile && (
              <button
                onClick={() => setSidebarCollapsed(false)}
                aria-label="Open navigation menu"
                className="flex items-center justify-center w-9 h-9 rounded-lg bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher transition-colors"
                title="Open menu"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            {/* Primary action + session setup cluster */}
            <MonitoringControls />

            {/* Secondary-weight group: assistant, alerts, account menu */}
            <div className="ml-auto flex items-center gap-sm">
              <button
                onClick={() => setAiPanelOpen(!aiPanelOpen)}
                aria-label="Toggle AI Assistant"
                aria-expanded={aiPanelOpen}
                title="AI Assistant"
                className={`flex items-center justify-center w-9 h-9 rounded-lg transition-colors shrink-0 ${aiPanelOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}
              >
                <Brain className="w-4 h-4" />
              </button>
              <button
                onClick={() => setNotifOpen(!notifOpen)}
                aria-label="Toggle alerts panel"
                aria-expanded={notifOpen}
                title="Alerts"
                className={`flex items-center justify-center w-9 h-9 rounded-lg transition-colors shrink-0 ${notifOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}
              >
                <Bell className="w-4 h-4" />
              </button>
              <UserMenu roleLabel={currentRole.label} roleIcon={RoleIcon} email={user.email} onLogout={logout} />
            </div>
          </div>
        </div>
        <main id="main-content" className="flex-1 overflow-y-auto" role="main" aria-label="Main content">
          <AnimatePresence mode="popLayout">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.12, ease: 'easeInOut' }}
              className="h-full w-full"
            >
              <ErrorBoundary>
                {user && <DemoModeBanner isDemoMode={isDemoMode} />}
                {pathAllowed ? (
                  <Outlet context={{ setNotifOpen }} />
                ) : (
                  <AccessDenied pathname={location.pathname} />
                )}
              </ErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <AIAssistantPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} />
      <div aria-live="polite" aria-atomic="true" className="sr-only" id="a11y-announcer" />

      {/* Product Tour */}
      {showTour && <ProductTour onComplete={dismissTour} />}

      {/* Keyboard Shortcuts Help */}
      {showHelp && <KeyboardHelpPanel onClose={dismissHelp} />}

      {/* Floating Help Button */}
      {!showTour && <FloatingHelpButton onClick={() => setShowHelp(true)} />}

      {notifOpen && (
        <>
          <div className="fixed inset-0 z-50" onClick={() => setNotifOpen(false)} aria-hidden="true" />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Alerts"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 35 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-96 bg-surface-container border-l border-outline-variant shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <AlertCenter onClose={() => setNotifOpen(false)} />
          </motion.div>
        </>
      )}
    </div>
  );
}

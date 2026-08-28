import React, { useState, useEffect, useRef } from 'react';
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

const roleConfig: Record<Role, { label: string; icon: React.ElementType }> = {
  operator: { label: 'Operator', icon: HardHat },
  supervisor: { label: 'Supervisor', icon: Users },
  safety_mgr: { label: 'Safety Mgr', icon: Shield },
  admin: { label: 'Admin', icon: UserCog },
};

const rolePaths: Record<Role, string[]> = {
  operator: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/workers', '/settings'],
  supervisor: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/workers', '/settings'],
  safety_mgr: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/audit', '/manager', '/workers', '/settings'],
  admin: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/audit', '/deployment', '/manager', '/workers', '/users', '/pilot-requests', '/settings'],
};

/** Exact match for static routes; /replay/:sessionId allowed for roles with /sessions access. */
function isPathAllowed(pathname: string, allowedPaths: string[]): boolean {
  if (allowedPaths.includes(pathname)) return true;
  if (pathname.startsWith('/replay/') && allowedPaths.includes('/sessions')) return true;
  return false;
}

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
          <button onClick={onLogout} className="w-full flex items-center gap-sm px-md py-sm text-body-sm text-red-400 hover:bg-surface-container-highest transition-colors">
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}

function DemoModeBanner({ isDemoMode }: { isDemoMode: boolean }) {
  if (!isDemoMode) return null;
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-center">
      <p className="text-xs font-semibold text-amber-400">
        DEMO MODE — Showing synthetic data. No real camera or workers are connected.
      </p>
    </div>
  );
}

export default function Layout() {
  const { user, logout, isDemoMode } = useAuth();
  const { dashboard } = useDashboard();
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(() => {
    // Show onboarding for new users (first login) unless they've completed it or are in demo mode
    return !localStorage.getItem('ergovigilance_onboarded') && !isDemoMode;
  });
  const location = useLocation();

  useEffect(() => {
    fetch('/api/demo-mode')
      .then(r => r.json())
      .then(d => { if (d.demo_mode) setDemoMode(true); })
      .catch(() => {});
  }, []);

  useAlertToasts(() => setNotifOpen(true));

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setAiPanelOpen(false); setNotifOpen(false); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (!user) return <Navigate to="/login" replace />;

  const role = user.role;
  const allowedPaths = rolePaths[role];
  if (!isPathAllowed(location.pathname, allowedPaths)) {
    return <Navigate to="/dashboard" replace />;
  }

  const currentRole = roleConfig[role];
  const RoleIcon = currentRole.icon;

  if (showOnboarding) {
    return <OnboardingFlow onComplete={() => setShowOnboarding(false)} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface text-on-surface">
      <Sidebar role={role} rolePaths={rolePaths} collapsed={sidebarCollapsed} onCollapsedChange={setSidebarCollapsed} />
      <div className={`flex flex-col flex-1 min-w-0 transition-[margin] duration-300 ease-out ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        <Header
          session={dashboard?.session || null}
        />
        {demoMode && (
          <div className="mx-lg mt-sm px-4 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-700 text-sm font-medium flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            Demo Mode — showing synthetic data for presentation
          </div>
        )}
        <div className="px-lg pt-md pb-0 space-y-md">
          <div className="flex items-center gap-md flex-wrap">
            {/* Primary action + session setup cluster */}
            <MonitoringControls />

            {/* Secondary-weight group: assistant, alerts, account menu */}
            <div className="ml-auto flex items-center gap-sm">
              <button
                onClick={() => setAiPanelOpen(!aiPanelOpen)}
                title="AI Assistant"
                className={`flex items-center justify-center w-9 h-9 rounded-lg transition-colors shrink-0 ${aiPanelOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}
              >
                <Brain className="w-4 h-4" />
              </button>
              <button
                onClick={() => setNotifOpen(!notifOpen)}
                title="Alerts"
                className={`flex items-center justify-center w-9 h-9 rounded-lg transition-colors shrink-0 ${notifOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}
              >
                <Bell className="w-4 h-4" />
              </button>
              <UserMenu roleLabel={currentRole.label} roleIcon={RoleIcon} email={user.email} onLogout={logout} />
            </div>
          </div>
        </div>
        <main className="flex-1 overflow-y-auto">
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
                <Outlet context={{ setNotifOpen }} />
              </ErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <AIAssistantPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} />

      {notifOpen && (
        <>
          <div className="fixed inset-0 z-50" onClick={() => setNotifOpen(false)} />
          <motion.div
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

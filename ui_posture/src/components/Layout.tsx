import React, { useState, useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router';
import Sidebar from './Sidebar';
import { Header } from '@/src/components/layout/Header';
import { useDashboard } from '@/src/hooks/useDashboard';
import { useDemo } from '@/src/demo/DemoProvider';
import { DemoControls, KpiRow, AIAssistantPanel } from '@/src/components/demo';
import { NotificationCenter } from '@/src/components/common/NotificationCenter';
import ErrorBoundary from '@/src/components/common/ErrorBoundary';
import { AnimatePresence, motion } from 'motion/react';
import { Brain, Bell, LogOut, UserCog, Shield, Users, HardHat } from 'lucide-react';
import { useAuth, type Role } from '@/src/auth/AuthContext';
import { useAlertToasts } from '@/src/hooks/useAlertToasts';

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

export default function Layout() {
  const { user, logout } = useAuth();
  const { dashboard } = useDashboard();
  const { state: demoState } = useDemo();
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

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

  return (
    <div className="flex h-screen overflow-hidden bg-surface text-on-surface">
      <Sidebar role={role} rolePaths={rolePaths} collapsed={sidebarCollapsed} onCollapsedChange={setSidebarCollapsed} />
      <div className={`flex flex-col flex-1 min-w-0 transition-[margin] duration-300 ease-out ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        <Header
          session={dashboard?.session || null}
        />
        <div className="px-lg pt-md pb-0 space-y-md">
          <div className="flex items-center gap-md flex-wrap">
            <DemoControls />
            <div className="flex items-center gap-sm bg-surface-container rounded-lg px-sm py-xs border border-outline-variant">
              <RoleIcon className="w-3.5 h-3.5 text-primary" />
              <div className="leading-tight">
                <p className="text-[10px] font-bold uppercase text-on-surface">{currentRole.label}</p>
                <p className="text-[9px] text-on-surface-variant max-w-[150px] truncate">{user.email}</p>
              </div>
            </div>
            <button onClick={() => setAiPanelOpen(!aiPanelOpen)} className={`flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium transition-colors shrink-0 ${aiPanelOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}>
              <Brain className="w-4 h-4" />
              <span className="hidden sm:inline">AI Assistant</span>
            </button>
            <button onClick={() => setNotifOpen(!notifOpen)} className={`flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium transition-colors shrink-0 ${notifOpen ? 'bg-primary text-on-primary' : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface'}`}>
              <Bell className="w-4 h-4" />
              <span className="hidden sm:inline">Alerts</span>
            </button>
            <button onClick={logout} className="flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium transition-colors shrink-0 bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-higher hover:text-on-surface">
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
          <KpiRow />
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
            <NotificationCenter onClose={() => setNotifOpen(false)} />
          </motion.div>
        </>
      )}
    </div>
  );
}

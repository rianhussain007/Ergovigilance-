import { useState, useMemo } from 'react';
import { NavLink } from 'react-router';
import { LayoutDashboard, Radio, BarChart3, FileText, History, Settings, ChevronLeft, ChevronRight, Activity, Building2, Camera, ScrollText, Server, Clapperboard, Users, ClipboardList, UserCog, Heart, Code, Wifi, SlidersHorizontal, Brain, Scan, TrendingUp, HeartPulse, ListChecks, Rocket, Network, Shield } from 'lucide-react';
import { motion } from 'motion/react';
import Logo from '../components/common/Logo';
import { useI18n } from '@/src/i18n';

// Navigation grouped into labeled sections. Each item keeps its own role gate
// so operator/supervisor roles never see admin-only destinations (Manager,
// Deployment, Audit Trail, Pilot Requests, Users).
const NAV_SECTIONS: { title: string; tKey: string; items: { to: string; label: string; tKey: string; icon: typeof LayoutDashboard; roles: string[] }[] }[] = [
  {
    title: 'Monitoring',
    tKey: 'nav.dashboard',
    items: [
      { to: '/dashboard', label: 'Dashboard', tKey: 'nav.dashboard', icon: LayoutDashboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/monitoring', label: 'Live Monitoring', tKey: 'nav.liveMonitoring', icon: Radio, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/my-posture', label: 'My Posture', tKey: 'nav.myPosture', icon: Heart, roles: ['operator'] },
      { to: '/video-review', label: 'Video Review', tKey: 'nav.videoReview', icon: Clapperboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
    ],
  },
  {
    title: 'Data',
    tKey: 'nav.analytics',
    items: [
      { to: '/analytics', label: 'Analytics', tKey: 'nav.analytics', icon: BarChart3, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/reports', label: 'Reports', tKey: 'nav.reports', icon: FileText, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/sessions', label: 'Sessions', tKey: 'nav.sessions', icon: History, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/workers', label: 'Workers', tKey: 'nav.workers', icon: Users, roles: ['supervisor', 'safety_mgr', 'admin'] },
      { to: '/cameras', label: 'Multi-Camera', tKey: 'nav.multiCamera', icon: Camera, roles: ['supervisor', 'safety_mgr', 'admin'] },
      { to: '/cloud-cameras', label: 'Cloud Cameras', tKey: 'nav.cloudCameras', icon: Wifi, roles: ['supervisor', 'safety_mgr', 'admin'] },
      { to: '/cloud-onboarding', label: 'Cloud Setup', tKey: 'nav.cloudSetup', icon: Rocket, roles: ['admin'] },
      { to: '/cloud-settings', label: 'Cloud Settings', tKey: 'nav.cloudSettings', icon: SlidersHorizontal, roles: ['admin'] },
      { to: '/model-dashboard', label: 'Model Dashboard', tKey: 'nav.modelDashboard', icon: Brain, roles: ['admin'] },
      { to: '/yolo-demo', label: 'YOLO Demo', tKey: 'nav.yoloDemo', icon: Scan, roles: ['admin', 'safety_mgr'] },
      { to: '/roi-analytics', label: 'ROI Analytics', tKey: 'nav.roiAnalytics', icon: TrendingUp, roles: ['admin', 'safety_mgr'] },
    ],
  },
  {
    title: 'Admin',
    tKey: 'nav.manager',
    items: [
      { to: '/manager', label: 'Manager', tKey: 'nav.manager', icon: Building2, roles: ['safety_mgr', 'admin'] },
      { to: '/deployment', label: 'Deployment', tKey: 'nav.deployment', icon: Server, roles: ['admin'] },
      { to: '/audit', label: 'Audit Trail', tKey: 'nav.auditTrail', icon: ScrollText, roles: ['safety_mgr', 'admin'] },
      { to: '/users', label: 'Users', tKey: 'nav.users', icon: UserCog, roles: ['admin'] },
      { to: '/pilot-requests', label: 'Pilot Requests', tKey: 'nav.pilotRequests', icon: ClipboardList, roles: ['admin'] },
      { to: '/api-docs', label: 'API Docs', tKey: 'nav.apiDocs', icon: Code, roles: ['admin'] },
      { to: '/system-health', label: 'System Health', tKey: 'nav.systemHealth', icon: HeartPulse, roles: ['admin'] },
      { to: '/architecture', label: 'Architecture', tKey: 'nav.architecture', icon: Network, roles: ['admin'] },
      { to: '/onboarding', label: 'Onboarding', tKey: 'nav.onboarding', icon: ListChecks, roles: ['admin'] },
      { to: '/consent', label: 'Consent', tKey: 'nav.consent', icon: Shield, roles: ['safety_mgr', 'admin'] },
      { to: '/settings', label: 'Settings', tKey: 'nav.settings', icon: Settings, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
    ],
  },
];

interface SidebarProps {
  role?: string;
  rolePaths?: Record<string, string[]>;
  /** Controlled collapsed state (lifted to the layout so content reflows). */
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Mobile mode: overlay sidebar with backdrop */
  isMobile?: boolean;
}

export default function Sidebar({ role = 'administrator', rolePaths, collapsed: collapsedProp, onCollapsedChange, isMobile }: SidebarProps) {
  const { t } = useI18n();
  // Internal fallback keeps Sidebar usable standalone; when `collapsed` is
  // provided by the parent, the parent owns the state.
  const [collapsedState, setCollapsedState] = useState(false);
  const collapsed = collapsedProp ?? collapsedState;
  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsedState(next);
    onCollapsedChange?.(next);
  };

  const sections = useMemo(() => {
    return NAV_SECTIONS
      .map((section) => ({
        title: section.title,
        items: section.items.filter((item) => item.roles.includes(role)),
      }))
      .filter((section) => section.items.length > 0);
  }, [role]);

  return (
    <>
      {/* Mobile backdrop overlay */}
      {isMobile && !collapsed && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={() => onCollapsedChange?.(true)}
        />
      )}
      <aside className={`h-screen fixed left-0 top-0 flex flex-col py-md bg-white dark:bg-surface-container-low/95 border-r border-slate-200 dark:border-outline-variant/60 z-50 transition-all duration-300 ease-out ${collapsed ? 'w-16' : 'w-64'} ${isMobile && !collapsed ? 'shadow-2xl' : ''}`}>
      <div className={`mb-xl transition-all duration-300 ${collapsed ? 'w-full flex justify-center' : 'px-lg'}`}>
        {collapsed ? (
          <Logo className="w-10 h-10" variant="light" iconOnly />
        ) : (
          <div className="transition-all duration-300">
            <Logo className="h-10 w-auto" variant="auto" />
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-sm pb-sm" role="navigation" aria-label="Main navigation">
        {sections.map((section) => (
          <div key={section.title} className={collapsed ? 'mt-md' : 'mt-sm'}>
            {!collapsed && (
              <p id={`nav-section-${section.title}`} className="font-label-caps text-[9px] text-slate-400 dark:text-on-surface-variant/60 uppercase tracking-widest px-md mb-xs mt-md" role="presentation">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  aria-label={item.label}
                  className={({ isActive }) =>
                    `w-full flex items-center gap-md rounded-xl text-body-sm font-medium transition-all duration-200 relative group ${
                      isActive
                        ? 'text-blue-700 dark:text-primary bg-blue-50 dark:bg-primary/10 border border-blue-200 dark:border-primary/15 shadow-sm shadow-blue-100 dark:shadow-primary/5'
                        : 'text-slate-600 dark:text-on-surface-variant hover:bg-slate-100 dark:hover:bg-surface-container-highest/80 hover:text-slate-900 dark:hover:text-on-surface border border-transparent'
                    } ${collapsed ? 'justify-center gap-0 py-2.5' : 'px-md py-2.5'}`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && !collapsed && (
                        <motion.div
                          layoutId="navIndicator"
                          className="absolute left-0 top-1 bottom-1 w-0.5 bg-blue-600 dark:bg-primary rounded-full"
                          transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                        />
                      )}
                      <item.icon className={`w-5 h-5 shrink-0 transition-colors duration-150 ${isActive ? 'text-blue-600 dark:text-primary' : 'text-slate-400 dark:text-on-surface-variant group-hover:text-slate-700 dark:group-hover:text-on-surface'}`} />
                      {!collapsed && (
                        <span className="truncate">{t(item.tKey)}</span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Mobile close button when expanded */}
      {isMobile && !collapsed && (
        <div className="px-sm pt-sm">
          <button
            onClick={() => onCollapsedChange?.(true)}
            className="w-full flex items-center justify-center gap-sm px-md py-2 rounded-xl text-sm font-medium text-slate-500 dark:text-on-surface-variant hover:bg-slate-100 dark:hover:bg-surface-container-highest transition-colors border border-slate-200 dark:border-outline-variant/50"
          >
            Close Menu
          </button>
        </div>
      )}

      <div className="px-sm pt-md border-t border-slate-200 dark:border-outline-variant mt-auto">
        <button
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className="w-full flex items-center justify-center px-md py-2.5 rounded-xl text-slate-400 dark:text-on-surface-variant hover:bg-slate-100 dark:hover:bg-surface-container-highest hover:text-slate-700 dark:hover:text-on-surface transition-all duration-150 gap-md"
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          {!collapsed && <span className="text-body-sm">Collapse</span>}
        </button>
      </div>
    </aside>
    </>
  );
}

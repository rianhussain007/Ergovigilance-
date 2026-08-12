import { useState, useMemo } from 'react';
import { NavLink } from 'react-router';
import { LayoutDashboard, Radio, BarChart3, FileText, History, Settings, ChevronLeft, ChevronRight, Activity, Building2, Camera, ScrollText, Server, Clapperboard, Users, ClipboardList, UserCog } from 'lucide-react';
import { motion } from 'motion/react';

// Navigation grouped into labeled sections. Each item keeps its own role gate
// so operator/supervisor roles never see admin-only destinations (Manager,
// Deployment, Audit Trail, Pilot Requests, Users).
const NAV_SECTIONS: { title: string; items: { to: string; label: string; icon: typeof LayoutDashboard; roles: string[] }[] }[] = [
  {
    title: 'Monitoring',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/monitoring', label: 'Live Monitoring', icon: Radio, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/video-review', label: 'Video Review', icon: Clapperboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
    ],
  },
  {
    title: 'Data',
    items: [
      { to: '/analytics', label: 'Analytics', icon: BarChart3, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/reports', label: 'Reports', icon: FileText, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/sessions', label: 'Sessions', icon: History, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
      { to: '/workers', label: 'Workers', icon: Users, roles: ['supervisor', 'safety_mgr', 'admin'] },
      { to: '/cameras', label: 'Multi-Camera', icon: Camera, roles: ['supervisor', 'safety_mgr', 'admin'] },
    ],
  },
  {
    title: 'Admin',
    items: [
      { to: '/manager', label: 'Manager', icon: Building2, roles: ['safety_mgr', 'admin'] },
      { to: '/deployment', label: 'Deployment', icon: Server, roles: ['admin'] },
      { to: '/audit', label: 'Audit Trail', icon: ScrollText, roles: ['safety_mgr', 'admin'] },
      { to: '/users', label: 'Users', icon: UserCog, roles: ['admin'] },
      { to: '/pilot-requests', label: 'Pilot Requests', icon: ClipboardList, roles: ['admin'] },
      { to: '/settings', label: 'Settings', icon: Settings, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
    ],
  },
];

interface SidebarProps {
  role?: string;
  rolePaths?: Record<string, string[]>;
  /** Controlled collapsed state (lifted to the layout so content reflows). */
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}

export default function Sidebar({ role = 'administrator', rolePaths, collapsed: collapsedProp, onCollapsedChange }: SidebarProps) {
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
    <aside className={`h-screen fixed left-0 top-0 flex flex-col py-md bg-surface-container-low/95 backdrop-blur-sm border-r border-outline-variant/60 z-50 transition-all duration-300 ease-out ${collapsed ? 'w-16' : 'w-64'}`}>
      <div className={`mb-xl transition-all duration-300 ${collapsed ? 'w-full flex justify-center' : 'px-lg'}`}>
        {collapsed ? (
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center hover:bg-primary/30 transition-colors">
            <Activity className="w-5 h-5 text-primary" />
          </div>
        ) : (
          <div className="transition-all duration-300">
            <h1 className="text-headline-md font-bold text-primary tracking-tight">ErgoVigilance</h1>
            <p className="font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest mt-xs opacity-70">Industrial Ergonomics</p>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-sm pb-sm">
        {sections.map((section) => (
          <div key={section.title} className={collapsed ? 'mt-md' : 'mt-sm'}>
            {!collapsed && (
              <p className="font-label-caps text-[9px] text-on-surface-variant/60 uppercase tracking-widest px-md mb-xs mt-md">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `w-full flex items-center gap-md rounded-lg text-body-sm font-medium transition-all duration-200 relative group ${
                      isActive
                        ? 'text-primary bg-primary/10 border border-primary/15 shadow-sm shadow-primary/5'
                        : 'text-on-surface-variant hover:bg-surface-container-highest/80 hover:text-on-surface border border-transparent'
                    } ${collapsed ? 'justify-center gap-0 py-sm' : 'px-md py-sm'}`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && !collapsed && (
                        <motion.div
                          layoutId="navIndicator"
                          className="absolute left-0 top-1 bottom-1 w-0.5 bg-primary rounded-full"
                          transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                        />
                      )}
                      <item.icon className={`w-5 h-5 shrink-0 transition-colors duration-150 ${isActive ? 'text-primary' : 'text-on-surface-variant group-hover:text-on-surface'}`} />
                      {!collapsed && (
                        <span className="truncate">{item.label}</span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-sm pt-md border-t border-outline-variant mt-auto">
        <button
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-center px-md py-sm rounded-lg text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface transition-all duration-150 gap-md"
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          {!collapsed && <span className="text-body-sm">Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

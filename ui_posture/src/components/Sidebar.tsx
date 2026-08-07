import { useState, useMemo } from 'react';
import { NavLink } from 'react-router';
import { LayoutDashboard, Radio, BarChart3, FileText, History, Settings, ChevronLeft, ChevronRight, Activity, Building2, Camera, ScrollText, Server, Clapperboard, Users, ClipboardList } from 'lucide-react';
import { motion } from 'motion/react';

const allNavItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/monitoring', label: 'Live Monitoring', icon: Radio, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/video-review', label: 'Video Review', icon: Clapperboard, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/reports', label: 'Reports', icon: FileText, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/sessions', label: 'Sessions', icon: History, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
  { to: '/workers', label: 'Workers', icon: Users, roles: ['supervisor', 'safety_mgr', 'admin'] },
  { to: '/cameras', label: 'Multi-Camera', icon: Camera, roles: ['supervisor', 'safety_mgr', 'admin'] },
  { to: '/manager', label: 'Manager', icon: Building2, roles: ['safety_mgr', 'admin'] },
  { to: '/deployment', label: 'Deployment', icon: Server, roles: ['admin'] },
  { to: '/audit', label: 'Audit Trail', icon: ScrollText, roles: ['safety_mgr', 'admin'] },
  { to: '/pilot-requests', label: 'Pilot Requests', icon: ClipboardList, roles: ['admin'] },
  { to: '/settings', label: 'Settings', icon: Settings, roles: ['operator', 'supervisor', 'safety_mgr', 'admin'] },
];

interface SidebarProps {
  role?: string;
  rolePaths?: Record<string, string[]>;
}

export default function Sidebar({ role = 'administrator', rolePaths }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  const navItems = useMemo(() => {
    return allNavItems.filter((item) => item.roles.includes(role));
  }, [role]);

  return (
    <aside className={`h-screen fixed left-0 top-0 flex flex-col py-md bg-surface-container-low border-r border-outline-variant z-50 transition-all duration-300 ease-out ${collapsed ? 'w-16' : 'w-64'}`}>
      <div className={`px-lg mb-xl transition-all duration-300 ${collapsed ? 'px-0 text-center' : ''}`}>
        {collapsed ? (
          <div className="w-10 h-10 mx-auto rounded-xl bg-primary/20 flex items-center justify-center">
            <Activity className="w-5 h-5 text-primary" />
          </div>
        ) : (
          <div className="transition-all duration-300">
            <h1 className="text-headline-md font-bold text-primary tracking-tight">ErgoVigilance</h1>
            <p className="font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest mt-xs opacity-70">Industrial Ergonomics</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 px-sm">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `w-full flex items-center gap-md px-md py-sm rounded-lg text-body-sm font-medium transition-all duration-150 relative group ${
                isActive
                  ? 'text-primary bg-primary/10 border border-primary/15 shadow-sm'
                  : 'text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface border border-transparent'
              } ${collapsed ? 'justify-center px-0 gap-0' : ''}`
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
      </nav>

      <div className="px-sm pt-md border-t border-outline-variant mt-auto">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center px-md py-sm rounded-lg text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface transition-all duration-150 gap-md"
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          {!collapsed && <span className="text-body-sm">Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

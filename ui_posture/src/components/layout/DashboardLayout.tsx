import type { ReactNode } from 'react';

interface DashboardLayoutProps {
  sidebar: ReactNode;
  header: ReactNode;
  children: ReactNode;
  /** True when the sidebar is collapsed (w-16) so content reflows to full width. */
  sidebarCollapsed?: boolean;
}

export function DashboardLayout({ sidebar, header, children, sidebarCollapsed = false }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface text-on-surface">
      {sidebar}
      <div className={`flex flex-col flex-1 min-w-0 transition-[margin] duration-300 ease-out ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        {header}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

import { useEffect, useMemo } from 'react';
import { Link } from 'react-router';
import { ArrowRight, Lock, ShieldCheck } from 'lucide-react';
import { useAuth, type Role } from '@/src/auth/AuthContext';
import { rolesAllowed } from '@/src/auth/capabilities';
import { rolePaths } from '@/src/auth/routes';
import { NAV_SECTIONS } from '@/src/components/Sidebar';
import { announce } from '@/src/utils/announce';

const ROLE_LABELS: Record<Role, string> = {
  operator: 'Operator',
  supervisor: 'Supervisor',
  safety_mgr: 'Safety manager',
  admin: 'Admin',
};

const ALL_ROLES: Role[] = ['operator', 'supervisor', 'safety_mgr', 'admin'];

/**
 * Rendered by Layout in place of <Outlet /> when the signed-in role is not
 * allowed on the current path (audit F-UX-02).
 *
 * The old behaviour was `<Navigate to="/dashboard" replace />`: clicking a
 * bookmarked or shared link silently teleported you somewhere else with no
 * explanation, which reads as a broken app. Now the page says what was
 * refused, which roles can open it, and what this role *can* do — and it keeps
 * the sidebar visible so the user can navigate away.
 */
export function AccessDenied({ pathname }: { pathname: string }) {
  const { user } = useAuth();
  const role = user?.role;

  const allowed = useMemo(() => {
    if (!role) return [];
    return NAV_SECTIONS.flatMap((section) =>
      section.items.filter((item) => rolePaths[role].includes(item.to)),
    ).slice(0, 8);
  }, [role]);

  const permittedRoles = useMemo(() => rolesAllowed(pathname, ALL_ROLES), [pathname]);

  useEffect(() => {
    announce(
      `Access denied. ${pathname} is not available to the ${role ? ROLE_LABELS[role] : 'current'} role.`,
    );
  }, [pathname, role]);

  return (
    <div className="mx-auto max-w-2xl p-lg" data-testid="access-denied">
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-lg space-y-md">
        <div className="flex items-start gap-md">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/15">
            <Lock className="h-5 w-5 text-amber-400" />
          </div>
          <div className="space-y-xs">
            <h1 className="text-title-lg font-bold text-on-surface">
              You don&rsquo;t have access to this page
            </h1>
            <p className="text-body-sm text-on-surface-variant">
              <code className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-[12px]">
                {pathname}
              </code>{' '}
              is restricted{role ? ` for the ${ROLE_LABELS[role]} role` : ''}
              {permittedRoles.length > 0 && (
                <>
                  {' '}
                  — it is available to{' '}
                  {permittedRoles.map((r) => ROLE_LABELS[r]).join(', ')}
                </>
              )}
              .
            </p>
            <p className="text-body-sm text-on-surface-variant">
              Nothing was changed and no monitoring was interrupted. If you need this page, ask an
              administrator to adjust your role.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-sm pt-xs">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-sm rounded-lg bg-primary px-md py-sm text-body-sm font-bold text-on-primary transition-colors hover:bg-primary/90"
          >
            Go to dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {allowed.length > 0 && (
        <div className="mt-lg space-y-sm">
          <h2 className="flex items-center gap-sm text-body-sm font-bold uppercase tracking-wider text-on-surface-variant">
            <ShieldCheck className="h-4 w-4" />
            Pages available to you
          </h2>
          <div className="flex flex-wrap gap-sm">
            {allowed.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="rounded-lg border border-outline-variant bg-surface-container px-md py-xs text-body-sm text-on-surface transition-colors hover:bg-surface-container-higher"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AccessDenied;

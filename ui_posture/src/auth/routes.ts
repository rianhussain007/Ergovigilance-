import type { Role } from './AuthContext';

/**
 * Routes each role is allowed to visit. This is the single source of truth
 * shared by Layout (redirect guard), the Sidebar, and the product tour
 * (a tour step whose route a role cannot reach would otherwise bounce and
 * hang in a redirect loop).
 */
export const rolePaths: Record<Role, string[]> = {
  operator: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/workers', '/settings'],
  supervisor: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/workers', '/settings'],
  safety_mgr: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/audit', '/manager', '/workers', '/consent', '/settings'],
  admin: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/sessions', '/cameras', '/cloud-cameras', '/cloud-settings', '/model-dashboard', '/yolo-demo', '/roi-analytics', '/system-health', '/onboarding', '/consent', '/audit', '/deployment', '/manager', '/workers', '/users', '/pilot-requests', '/api-docs', '/model-card', '/pilot-checklist', '/settings'],
};

/** Exact match for static routes; /replay/:sessionId allowed for roles with /sessions access. */
export function isPathAllowed(pathname: string, allowedPaths: string[]): boolean {
  if (allowedPaths.includes(pathname)) return true;
  if (pathname.startsWith('/replay/') && allowedPaths.includes('/sessions')) return true;
  return false;
}

import type { Role } from './AuthContext';

/**
 * Routes each role is allowed to visit. This is the single source of truth
 * shared by Layout (redirect guard), the Sidebar, and the product tour
 * (a tour step whose route a role cannot reach would otherwise bounce and
 * hang in a redirect loop).
 */
export const rolePaths: Record<Role, string[]> = {
  operator: ['/', '/dashboard', '/monitoring', '/my-posture', '/video-review', '/analytics', '/reports', '/trends', '/sessions', '/workers', '/webcam-demo', '/settings', '/setup'],
  supervisor: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/trends', '/sessions', '/cameras', '/cloud-cameras', '/workers', '/settings', '/setup'],
  safety_mgr: ['/', '/dashboard', '/monitoring', '/video-review', '/analytics', '/reports', '/trends', '/sessions', '/cameras', '/cloud-cameras', '/audit', '/manager', '/workers', '/consent', '/settings', '/model-card', '/pilot-checklist', '/yolo-demo', '/roi-analytics', '/setup'],
  admin: ['/', '/dashboard', '/monitoring', '/my-posture', '/video-review', '/analytics', '/reports', '/trends', '/sessions', '/cameras', '/cloud-cameras', '/cloud-settings', '/cloud-onboarding', '/model-dashboard', '/yolo-demo', '/roi-analytics', '/system-health', '/architecture', '/webcam-demo', '/onboarding', '/consent', '/audit', '/deployment', '/manager', '/workers', '/users', '/pilot-requests', '/api-docs', '/model-card', '/pilot-checklist', '/settings', '/setup'],
};

/** Exact match for static routes; /replay/:sessionId allowed for roles with /sessions access. */
export function isPathAllowed(pathname: string, allowedPaths: string[]): boolean {
  if (allowedPaths.includes(pathname)) return true;
  if (pathname.startsWith('/replay/') && allowedPaths.includes('/sessions')) return true;
  return false;
}

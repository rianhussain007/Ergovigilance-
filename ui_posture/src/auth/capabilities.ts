import type { Role } from './AuthContext';
import { isPathAllowed, rolePaths } from './routes';

/**
 * Capabilities — the semantic layer over the route permission table.
 *
 * Before this, "can this user do X?" was answered three different ways: the
 * Sidebar kept its own `roles: [...]` arrays per item, pages hard-coded role
 * checks, and Layout only knew paths. A page like /setup was reachable by
 * every role while its endpoint was supervisor+, so operators got 403s on a
 * 2-second poll.
 *
 * `rolePaths` stays the single source of truth; a capability is just a named
 * route that encodes the permission. `can()` answers with the same
 * `isPathAllowed` logic the router guard uses, so the UI and the guard can
 * never disagree (and a capability that no role can reach fails its test).
 */
export type Capability =
  | 'view_dashboard'
  | 'run_monitoring'
  | 'view_sessions'
  | 'view_reports'
  | 'view_analytics'
  | 'view_workers'
  | 'view_cameras'
  | 'configure_cloud'
  | 'view_audit_trail'
  | 'manage_users'
  | 'view_system_health'
  | 'view_roi'
  | 'view_model_card'
  | 'view_deployment'
  | 'handle_pilot_requests'
  | 'view_my_posture'
  | 'view_consent';

/** The route whose access rule *is* the capability. */
export const CAPABILITY_ROUTE: Record<Capability, string> = {
  view_dashboard: '/dashboard',
  run_monitoring: '/monitoring',
  view_sessions: '/sessions',
  view_reports: '/reports',
  view_analytics: '/analytics',
  view_workers: '/workers',
  view_cameras: '/cameras',
  configure_cloud: '/cloud-settings',
  view_audit_trail: '/audit',
  manage_users: '/users',
  view_system_health: '/system-health',
  view_roi: '/roi-analytics',
  view_model_card: '/model-card',
  view_deployment: '/deployment',
  handle_pilot_requests: '/pilot-requests',
  view_my_posture: '/my-posture',
  view_consent: '/consent',
};

export const ALL_CAPABILITIES = Object.keys(CAPABILITY_ROUTE) as Capability[];

export function can(role: Role | undefined | null, capability: Capability): boolean {
  if (!role) return false;
  return isPathAllowed(CAPABILITY_ROUTE[capability], rolePaths[role]);
}

export function capabilitiesFor(role: Role | undefined | null): Capability[] {
  if (!role) return [];
  return ALL_CAPABILITIES.filter((capability) => can(role, capability));
}

/**
 * Endpoints the UI calls from a page that a *different* role set may open.
 *
 * Some calls are not page-shaped: /reports is open to operators, but the risk
 * digest beside it is supervisor+ (GET) and safety-manager+ (POST). Rather
 * than letting the page 403 on mount, the role set is mirrored here and pinned
 * to the backend source by capabilities.test.ts — a role change on either side
 * fails the build.
 */
export type EndpointKey = 'GET /api/reports/digest' | 'POST /api/reports/digest/generate';

export const ENDPOINT_ROLES: Record<EndpointKey, Role[]> = {
  'GET /api/reports/digest': ['supervisor', 'safety_mgr', 'admin'],
  'POST /api/reports/digest/generate': ['safety_mgr', 'admin'],
};

export function canCallEndpoint(role: Role | undefined | null, endpoint: EndpointKey): boolean {
  if (!role) return false;
  return ENDPOINT_ROLES[endpoint].includes(role);
}

/** Roles that can open `pathname` — used to explain a denial ("available to: …"). */
export function rolesAllowed(pathname: string, roles: Role[]): Role[] {
  return roles.filter((role) => isPathAllowed(pathname, rolePaths[role]));
}

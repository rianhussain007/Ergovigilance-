/**
 * Capability layer coverage (audit F-UX-02 / F-UX-14).
 *
 * `rolePaths` is the router guard's source of truth. These tests pin the two
 * contracts that were previously unenforced:
 *   1. every named capability resolves through `isPathAllowed`, so a page
 *      cannot answer "can I?" differently from the guard, and
 *   2. nothing the UI advertises (sidebar sections, palette entries) points a
 *      role at a route that role cannot open — that mismatch is what produced
 *      the silent redirects and the operator 403 spikes.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  ALL_CAPABILITIES,
  CAPABILITY_ROUTE,
  ENDPOINT_ROLES,
  can,
  canCallEndpoint,
  capabilitiesFor,
  type EndpointKey,
} from '../auth/capabilities';
import { isPathAllowed, rolePaths } from '../auth/routes';
import type { Role } from '../auth/AuthContext';
import { NAV_SECTIONS } from '../components/Sidebar';
import { NAV_ITEMS } from '../components/common/SearchModal';

const ALL_ROLES: Role[] = ['operator', 'supervisor', 'safety_mgr', 'admin'];
/** The palette's real static entries (never a copy — a copy can drift). */
const PALETTE_ROUTES = NAV_ITEMS.map((item) => item.route);

describe('capabilities', () => {
  it('is derived from rolePaths — the guard and the UI cannot disagree', () => {
    for (const role of ALL_ROLES) {
      for (const capability of ALL_CAPABILITIES) {
        expect(can(role, capability)).toBe(
          isPathAllowed(CAPABILITY_ROUTE[capability], rolePaths[role]),
        );
      }
    }
  });

  it('refuses everything for a missing role', () => {
    for (const capability of ALL_CAPABILITIES) {
      expect(can(undefined, capability)).toBe(false);
      expect(can(null, capability)).toBe(false);
    }
  });

  it('gates the pages that used to leak to operators', () => {
    expect(can('operator', 'manage_users')).toBe(false);
    expect(can('operator', 'view_audit_trail')).toBe(false);
    expect(can('operator', 'view_system_health')).toBe(false);
    expect(can('operator', 'configure_cloud')).toBe(false);
    expect(can('operator', 'handle_pilot_requests')).toBe(false);

    expect(can('supervisor', 'view_audit_trail')).toBe(false);
    expect(can('safety_mgr', 'view_audit_trail')).toBe(true);

    expect(can('admin', 'manage_users')).toBe(true);
    expect(can('admin', 'view_system_health')).toBe(true);
    expect(can('admin', 'configure_cloud')).toBe(true);
  });

  it('keeps the core monitoring path open to every role', () => {
    for (const role of ALL_ROLES) {
      expect(can(role, 'view_dashboard')).toBe(true);
      expect(can(role, 'run_monitoring')).toBe(true);
      expect(can(role, 'view_sessions')).toBe(true);
    }
  });

  it('has no capability that no role can reach', () => {
    const reachable = new Set(ALL_ROLES.flatMap((role) => capabilitiesFor(role)));
    const orphans = ALL_CAPABILITIES.filter((capability) => !reachable.has(capability));
    expect(orphans).toEqual([]);
  });
});

describe('endpoint role matrix', () => {
  it('matches the backend require_roles() declarations', () => {
    // The digest endpoints are declared in the backend with require_roles(...).
    // If either side changes a role, this fails — that is what stops the page
    // from silently 403-polling again.
    const backend = readFileSync(
      path.resolve(process.cwd(), '../backend_api/app/api/report_digest.py'),
      'utf8',
    );
    const entries = [
      ...backend.matchAll(/@router\.(get|post|put|delete)\("([^"]+)"\)[\s\S]*?require_roles\(([^)]*)\)/g),
    ].map(([, verb, route, args]) => ({
      key: `${verb.toUpperCase()} /api${route}`,
      roles: args
        .split(',')
        .map((value) => value.trim().replace(/['"]/g, ''))
        .filter(Boolean),
    }));

    expect(entries.length).toBeGreaterThan(0);
    for (const entry of entries) {
      expect(
        ENDPOINT_ROLES[entry.key as EndpointKey],
        `${entry.key} is not mirrored in ENDPOINT_ROLES`,
      ).toEqual(entry.roles);
    }
  });

  it('refuses endpoint calls for roles the backend would 403', () => {
    expect(canCallEndpoint('operator', 'GET /api/reports/digest')).toBe(false);
    expect(canCallEndpoint('operator', 'POST /api/reports/digest/generate')).toBe(false);
    expect(canCallEndpoint('supervisor', 'GET /api/reports/digest')).toBe(true);
    expect(canCallEndpoint('supervisor', 'POST /api/reports/digest/generate')).toBe(false);
    expect(canCallEndpoint('safety_mgr', 'POST /api/reports/digest/generate')).toBe(true);
    expect(canCallEndpoint(undefined, 'GET /api/reports/digest')).toBe(false);
  });
});

describe('navigation surfaces', () => {
  it('never advertises a sidebar item to a role that cannot open it', () => {
    // One-directional on purpose: a route may be reachable but deliberately
    // hidden from the sidebar (e.g. /my-posture for admins). The dangerous
    // direction is advertising a link the guard then refuses.
    for (const section of NAV_SECTIONS) {
      for (const item of section.items) {
        for (const role of item.roles) {
          expect(
            isPathAllowed(item.to, rolePaths[role]),
            `${item.to} is advertised to ${role} but the guard refuses it`,
          ).toBe(true);
        }
      }
    }
  });

  it('keeps admin-only pages out of the operator palette', () => {
    // The palette lists every route for every role, so its static entries are
    // exactly where a role leak shows up (Ctrl+K → Audit as an operator would
    // have bounced to /dashboard). The runtime filter must have real work to
    // do: these routes are restricted, so operators must not be offered them.
    const restrictedForOperator = PALETTE_ROUTES.filter(
      (route) => !isPathAllowed(route, rolePaths.operator),
    );
    expect(restrictedForOperator).toEqual(
      expect.arrayContaining(['/audit', '/system-health', '/cloud-settings', '/model-dashboard']),
    );
    for (const route of restrictedForOperator) {
      expect(isPathAllowed(route, rolePaths.admin)).toBe(true);
    }
  });

  it('offers every role at least a handful of palette destinations', () => {
    for (const role of ALL_ROLES) {
      const reachable = PALETTE_ROUTES.filter((route) => isPathAllowed(route, rolePaths[role]));
      expect(reachable.length, `${role} has nothing to search for`).toBeGreaterThan(3);
    }
  });
});

import { describe, expect, it } from 'vitest';
import { NAV_SECTIONS } from '../components/Sidebar';
import { isPathAllowed, rolePaths } from '../auth/routes';

/**
 * Route/guard consistency (sell-readiness QA: the redirect-to-dashboard bug).
 *
 * The Layout guard bounces any path missing from rolePaths — while the
 * Sidebar shows items from its own per-item role lists. If the two drift,
 * users see a link that instantly redirects. This test fails loudly on any
 * drift: every sidebar destination must be allowed for every role shown it.
 */
describe('sidebar destinations are reachable for their roles', () => {
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      for (const role of item.roles) {
        it(`${item.to} allowed for ${role}`, () => {
          const allowed = (rolePaths as Record<string, string[]>)[role] ?? [];
          expect(isPathAllowed(item.to, allowed)).toBe(true);
        });
      }
    }
  }
});

describe('isPathAllowed', () => {
  it('allows replay subpaths for roles with /sessions access', () => {
    expect(isPathAllowed('/replay/abc123', ['/sessions'])).toBe(true);
  });

  it('rejects unknown paths', () => {
    expect(isPathAllowed('/nope', ['/dashboard'])).toBe(false);
  });

  it('requires exact match otherwise', () => {
    expect(isPathAllowed('/dashboard/extra', ['/dashboard'])).toBe(false);
  });
});

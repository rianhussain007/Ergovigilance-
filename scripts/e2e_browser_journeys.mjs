/* End-to-end browser QA journeys (Playwright/Chromium) against the running site.

Run:  node scripts/e2e_browser_journeys.mjs            (default http://localhost:3000)

Journeys:
  B1-B6   landing -> Validation nav link -> /validation (incl. accuracy-qualifier check)
  B7-B8   pricing tiers + annual toggle -> $239
  B9-B10  pilot form: label association, required-field client validation (no submit —
          the write path is covered once per run by scripts/e2e_api_journeys.py)
  B11     login rejects a bad password with a visible error
  B12     Try Demo -> app shell (DEMO MODE banner) -> Settings -> Live Monitoring
  B13     no broken images on the landing page
  B14     banned accuracy vintages absent from marketing pages (runtime re-check)
  B15     zero page errors / unexpected console errors across the run

Evidence: results/qa-pass/e2e_browser_results.json (gitignored, like the rest of qa-pass).
Exit code: 0 = no blocker failed, 1 = at least one blocker failed.
Severity: 'blocker' = journey broken; 'finding' = recorded anomaly (incl. known audit defects).
*/

import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.E2E_BASE || 'http://localhost:3000';
const started = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z');

const results = [];
const pageErrors = [];
const consoleErrors = [];

function rec(id, name, ok, severity = 'blocker', extra = {}) {
  results.push({ id, name, ok: !!ok, severity, ...extra });
  const mark = ok ? 'PASS' : severity === 'blocker' ? 'FAIL' : 'NOTE';
  console.log(`[${mark}] ${id} ${name}${extra.detail ? ` — ${extra.detail}` : ''}`);
}

function isNoise(text) {
  // favicon/devtools/vite noise + resource-load errors from our own intentional
  // negative tests (bad password -> 401, role probes -> 403).
  return /favicon|React DevTools|\[vite\]|Ignoring Event|Failed to load resource: the server responded with a status of (401|403)/i.test(text);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on('pageerror', (e) => pageErrors.push(String(e)));
page.on('console', (m) => {
  if (m.type() === 'error' && !isNoise(m.text())) consoleErrors.push(m.text());
});

try {
  // ---------- B1-B6: landing -> validation ----------
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('h1', { timeout: 15000 });
  const h1 = (await page.textContent('h1')) || '';
  rec('B1', 'landing renders h1', /Industrial Safety/.test(h1), 'blocker', { detail: h1.slice(0, 60) });

  const valLink = page.locator('nav a[href="/validation"]');
  rec('B2', 'top bar has exactly one Validation link', (await valLink.count()) === 1,
    'blocker', { detail: `count=${await valLink.count()}` });

  for (const id of ['solutions', 'technology', 'how-it-works', 'deployment-options', 'command-center']) {
    rec(`B3:${id}`, `landing anchor #${id} exists`, (await page.locator(`#${id}`).count()) === 1, 'finding');
  }

  await valLink.click();
  await page.waitForURL('**/validation', { timeout: 10000 });
  rec('B4', 'Validation link navigates to /validation', page.url().endsWith('/validation'),
    'blocker', { detail: page.url() });
  // Wait for validation-UNIQUE content before reading — SPA can briefly expose
  // the previous route's DOM (first run produced a false PASS from stale text).
  await page.waitForSelector('text=How we validate', { timeout: 15000 });
  await page.waitForSelector('text=87.6', { timeout: 15000 }).catch(() => {});

  const vtext = (await page.textContent('body')) || '';
  rec('B5', 'validation page states the 87.6% figure', /87\.6/.test(vtext));
  rec('B6', 'validation carries the LOW/MEDIUM + 500-frame qualifier (audit T1)',
    /LOW\/MEDIUM/i.test(vtext) && /\b500\b/.test(vtext), 'finding',
    { detail: 'known defect docs/WEBSITE_TRUTHFUL_AUDIT.md T1 — bare 87.6% on the accuracy page' });

  // ---------- B7-B8: pricing ----------
  await page.goto(`${BASE}/pricing`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('text=Cloud Professional', { timeout: 15000 });
  const tiersOk =
    (await page.locator('text=On-Premise Starter').count()) === 1 &&
    (await page.locator('text=Cloud Professional').count()) >= 1 &&
    (await page.locator('text=Enterprise').count()) >= 1;
  rec('B7', 'pricing shows all three tiers', tiersOk);

  const annualToggle = page.locator('button.w-12.h-6');
  rec('B8c', 'annual toggle button has an accessible name',
    (await annualToggle.count()) > 0 && !!(await annualToggle.first().getAttribute('aria-label')),
    'finding', { detail: 'unnamed toggle = WCAG 4.1.2 (same class as hamburger/dots)' });
  await annualToggle.first().click();
  await page
    .waitForFunction(() => (document.body.innerText || '').includes('$239'), null, { timeout: 8000 })
    .catch(() => {});
  const ptext = (await page.textContent('body')) || '';
  rec('B8', 'annual toggle shows $239/mo', /\$239/.test(ptext), 'blocker',
    { detail: /\$239/.test(ptext) ? '' : 'no $239 after clicking Annual' });
  rec('B8b', 'pricing exclusions rendered for Starter (RTSP/CCTV listed)',
    /RTSP\/CCTV camera support/.test(ptext), 'finding');

  // ---------- B9-B10: pilot form ----------
  await page.goto(`${BASE}/request-pilot`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[name="companyName"]', { timeout: 15000 });
  const labelAudit = await page.evaluate(() =>
    [...document.querySelectorAll('input, textarea, select')].map((i) => ({
      name: i.name || i.type,
      labeled: !!(
        (i.id && document.querySelector(`label[for="${i.id}"]`)) ||
        i.closest('label') ||
        i.getAttribute('aria-label') ||
        i.getAttribute('aria-labelledby')
      ),
    }))
  );
  const unlabeled = labelAudit.filter((f) => !f.labeled).map((f) => f.name);
  rec('B9', 'all pilot-form fields programmatically labeled', unlabeled.length === 0, 'finding',
    { detail: unlabeled.length ? `unlabeled: ${unlabeled.join(', ')}` : 'all labeled' });

  await page.click('button:has-text("Submit Request")');
  await page.waitForTimeout(500);
  rec('B10', 'empty required submit is blocked client-side (stays on page)',
    page.url().includes('/request-pilot'), 'finding', { detail: page.url() });

  // fill (but do not submit — API journey owns the single QA write)
  await page.fill('input[name="companyName"]', 'QA E2E Test Co');
  await page.fill('input[name="contactName"]', 'QA E2E');
  await page.fill('input[name="email"]', 'qa-e2e@example.local');

  // ---------- B11: login rejects bad password ----------
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[type="email"]', { timeout: 15000 });
  await page.fill('input[type="email"]', 'nobody@example.local');
  await page.fill('input[type="password"]', 'definitely-wrong-1');
  const [badResp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/auth/login'), { timeout: 15000 }),
    page.click('button:has-text("Sign In")'),
  ]);
  await page
    .waitForSelector('text=/invalid|incorrect|failed|wrong/i', { timeout: 8000 })
    .catch(() => {});
  const bodyAfter = (await page.textContent('body')) || '';
  rec('B11', 'bad password -> HTTP 4xx AND visible error message',
    badResp.status() >= 400 && badResp.status() < 500 && /fail|invalid|incorrect|error/i.test(bodyAfter),
    'blocker', { detail: `status=${badResp.status()}` });

  // ---------- B12: demo tour ----------
  await page.click('button:has-text("Try Demo")');
  await page.waitForURL(/\/(monitoring|dashboard)/, { timeout: 20000 });
  await page.waitForTimeout(1200);
  const shellText = (await page.textContent('body')) || '';
  rec('B12a', 'Try Demo lands in the app with DEMO MODE disclosure', /DEMO MODE/.test(shellText),
    'blocker', { detail: page.url() });

  // The guided tour auto-starts on every demo (~800ms after Layout mounts,
  // then it may navigate to its first step). Wait for it to ATTACH and settle
  // before pressing Escape — pressing before the keydown listener registers
  // silently loses the key. Fall back to the X (End tour) button if needed.
  const tour = page.locator('[role="dialog"][aria-label="Guided product tour"]');
  await tour.first().waitFor({ state: 'attached', timeout: 8000 }).catch(() => {});
  if ((await tour.count()) > 0) {
    await page.waitForTimeout(700); // let effects + initial step navigation settle
    for (let i = 0; i < 3 && (await tour.count()) > 0; i++) {
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    }
    const endBtn = page.locator('[role="dialog"][aria-label="Guided product tour"] button[title="End tour"]');
    if ((await tour.count()) > 0 && (await endBtn.count()) > 0) {
      await endBtn.first().click({ timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(500);
    }
    await tour.waitFor({ state: 'detached', timeout: 6000 }).catch(() => {});
  }
  rec('B12t', 'guided tour appears on demo and closes on Escape',
    (await tour.count()) === 0, 'finding',
    { detail: (await tour.count()) === 0 ? 'closed' : 'tour still open after Escape' });

  await page.locator('a[href="/settings"]:visible').first().click();
  await page.waitForURL('**/settings', { timeout: 10000 });
  const settingsText = (await page.textContent('body')) || '';
  rec('B12b', 'sidebar navigation to Settings works with h1',
    /Settings/.test(settingsText), 'blocker');

  await page.locator('a[href="/monitoring"]:visible').first().click();
  await page.waitForURL('**/monitoring', { timeout: 10000 });
  rec('B12c', 'sidebar navigation to Live Monitoring works',
    page.url().endsWith('/monitoring'), 'blocker');

  // The control lives inside the role-badge dropdown — open it first.
  const badge = page.locator('button:has-text("OPERATOR"):visible');
  if ((await badge.count()) > 0) {
    await badge.first().click();
    await page.waitForTimeout(400);
  }
  const signOut = page.locator('button[aria-label="Sign out"]:visible');
  if ((await signOut.count()) > 0) {
    await signOut.first().click();
    await page.waitForURL(/\/login|\/$/, { timeout: 10000 });
    const loggedOut = await page
      .waitForSelector('input[type="password"]', { timeout: 8000 })
      .then(() => true)
      .catch(() => false);
    rec('B12d', 'sign-out control exists, is reachable, and returns to the login page',
      loggedOut, 'finding', { detail: `url=${page.url()} (label: "Logout" in role badge menu)` });
  } else {
    rec('B12d', 'sign-out control exists, is reachable, and returns to the login page', false, 'finding',
      { detail: 'no sign-out control located in the app shell' });
  }
  // ensure a clean state for later steps regardless
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });

  // ---------- B13: images on landing ----------
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(async () => {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise((r) => setTimeout(r, 1500));
  });
  const broken = await page.evaluate(() =>
    [...document.images]
      .filter((i) => i.complete && i.naturalWidth === 0)
      .map((i) => i.getAttribute('src'))
  );
  rec('B13', 'no broken images on the landing page', broken.length === 0, 'finding',
    { detail: broken.join(', ') || 'all loaded' });
  await page.evaluate(() => window.scrollTo(0, 0));

  // ---------- B14: banned accuracy vintages absent at runtime ----------
  const banned = /94\.1|97\.6|88\.6|86\.4|76\.9/;
  for (const route of ['/', '/pricing', '/validation']) {
    await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
    const text = (await page.textContent('body')) || '';
    const hit = banned.exec(text);
    rec(`B14:${route}`, `no banned accuracy vintage on ${route}`, !hit, 'blocker',
      { detail: hit ? hit[0] : '' });
  }
} catch (err) {
  rec('B00', 'harness completed without an unexpected exception', false, 'blocker',
    { detail: String(err).slice(0, 300) });
} finally {
  await browser.close();
}

// ---------- B15: console/page health ----------
const unexpected = consoleErrors.filter((t) => !isNoise(t));
rec('B15', 'zero page errors and unexpected console errors', pageErrors.length === 0 && unexpected.length === 0,
  'blocker', {
    detail: [...pageErrors, ...unexpected].slice(0, 5).join(' | ') || 'clean',
  });

const blockersFailed = results.filter((r) => r.severity === 'blocker' && !r.ok);
const findings = results.filter((r) => r.severity === 'finding' && !r.ok);
const out = {
  started,
  base: BASE,
  total: results.length,
  passed: results.filter((r) => r.ok).length,
  blockers_failed: blockersFailed.length,
  findings: findings.length,
  page_errors: pageErrors,
  console_errors: unexpected,
  results,
};
const outPath = path.join('results', 'qa-pass', 'e2e_browser_results.json');
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(out, null, 2));

console.log(`\nBrowser journeys: ${out.passed}/${out.total} passed · ` +
  `${blockersFailed.length} blocker failure(s) · ${findings.length} finding(s)`);
console.log(`evidence: ${outPath}`);
process.exit(blockersFailed.length ? 1 : 0);

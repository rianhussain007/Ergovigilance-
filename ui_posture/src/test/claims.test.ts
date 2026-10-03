/**
 * Claim hygiene (audit F-UX-15 / trust workstream).
 *
 * The public pages carry accuracy and cost claims. Two things must never
 * regress: (1) retired or unqualified accuracy figures reappearing in the UI,
 * and (2) money claims being shown from a dataset too small to support them.
 * These are source-level guards — they fail the build in CI before a claim can
 * reach a buyer.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { MIN_HOURS_FOR_ROI, MIN_SESSIONS_FOR_ROI, hasEnoughRoiData } from '../pages/ROIAnalyticsPage';

const SRC = path.resolve(process.cwd(), 'src');

/** Figures that must never be quoted in the product UI (retired evaluations). */
const BANNED_NUMBERS = ['94.1', '97.6', '88.6', '86.4', '76.9'];

/** The one accuracy figure we do publish, and the qualifier it must carry. */
const PUBLISHED_FIGURE = '87.6';
const REQUIRED_QUALIFIER = /LOW\/MEDIUM/i;

function sourceFiles(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      sourceFiles(full, files);
    } else if (/\.(ts|tsx)$/.test(entry)) {
      files.push(full);
    }
  }
  return files;
}

const FILES = sourceFiles(SRC);

function relative(file: string) {
  return path.relative(process.cwd(), file).replace(/\\/g, '/');
}

describe('accuracy claims', () => {
  it('never quotes a retired accuracy figure', () => {
    const offenders: string[] = [];
    for (const file of FILES) {
      // Test files and this guard itself legitimately mention the numbers.
      if (relative(file).startsWith('src/test/')) continue;
      const text = readFileSync(file, 'utf8');
      const lines = text.split('\n');
      lines.forEach((line, index) => {
        for (const banned of BANNED_NUMBERS) {
          if (line.includes(banned)) offenders.push(`${relative(file)}:${index + 1} → ${line.trim()}`);
        }
      });
    }
    expect(offenders, 'banned accuracy figures found in shipped UI code').toEqual([]);
  });

  it('qualifies every published 87.6% figure with its evaluation scope', () => {
    const published = FILES.filter(
      (file) => !relative(file).startsWith('src/test/') && readFileSync(file, 'utf8').includes(PUBLISHED_FIGURE),
    );
    expect(published.length, 'the published figure vanished — update this test').toBeGreaterThan(0);

    for (const file of published) {
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, index) => {
        if (!line.includes(PUBLISHED_FIGURE)) return;
        // The qualifier may sit on the same line or wrap onto the next one.
        const window = lines.slice(index, index + 3).join(' ');
        expect(
          REQUIRED_QUALIFIER.test(window),
          `${relative(file)}:${index + 1} quotes ${PUBLISHED_FIGURE}% without a LOW/MEDIUM qualifier`,
        ).toBe(true);
      });
    }
  });

  it('qualifies the dynamically rendered accuracy headline on ValidationPage', () => {
    // ValidationPage builds "87.6%" at runtime from ground_truth_evaluation.json,
    // so the source-level figure scan above never sees it. The rendered copy must
    // still carry the evaluation scope next to the headline.
    const text = readFileSync(path.resolve(process.cwd(), 'src/pages/ValidationPage.tsx'), 'utf8');
    expect(text, 'ValidationPage lost its scope qualifier').toMatch(/LOW\/MEDIUM risk only/);
    expect(text, 'ValidationPage no longer frames the number as agreement').toContain(
      'agreement with human assessors on',
    );
    expect(text, 'ValidationPage must not call the raw figure overall accuracy').not.toContain(
      'overall accuracy on human-labeled',
    );
    expect(text).toContain('not yet validated');
    expect(text).toContain('Single-site');
  });

  it('keeps the "screening aid, not a medical device" framing on claim surfaces', () => {
    for (const file of ['src/pages/PricingPage.tsx', 'src/pages/ModelCardPage.tsx', 'src/pages/LandingPage.tsx']) {
      const text = readFileSync(path.resolve(process.cwd(), file), 'utf8');
      expect(text.toLowerCase(), `${file} lost its disclaimer`).toContain('screening aid');
    }
  });
});

describe('ROI data gate', () => {
  it('refuses a savings estimate below the documented minimum dataset', () => {
    expect(hasEnoughRoiData({ total_sessions: 0, total_hours: 0 })).toBe(false);
    expect(hasEnoughRoiData({ total_sessions: MIN_SESSIONS_FOR_ROI - 1, total_hours: 500 })).toBe(false);
    expect(hasEnoughRoiData({ total_sessions: 500, total_hours: MIN_HOURS_FOR_ROI - 1 })).toBe(false);
  });

  it('allows it at the threshold', () => {
    expect(hasEnoughRoiData({ total_sessions: MIN_SESSIONS_FOR_ROI, total_hours: MIN_HOURS_FOR_ROI })).toBe(true);
    expect(hasEnoughRoiData({ total_sessions: 400, total_hours: 900 })).toBe(true);
  });

  it('renders no dollar amount when the gate is closed', () => {
    const text = readFileSync(path.resolve(process.cwd(), 'src/pages/ROIAnalyticsPage.tsx'), 'utf8');
    expect(text).toContain('hasEnoughRoiData(metrics)');
    expect(text).toContain('Not enough data for a savings estimate');
    // The savings cards and business case must be behind the gate.
    expect(text.match(/\{roiReady && \(/g)?.length ?? 0).toBeGreaterThanOrEqual(3);
  });
});

describe('legal surfaces', () => {
  it('serves the /legal route the signup form links to', () => {
    const app = readFileSync(path.resolve(process.cwd(), 'src/App.tsx'), 'utf8');
    expect(app).toMatch(/<Route\s+path="\/legal"/);

    const signup = readFileSync(path.resolve(process.cwd(), 'src/pages/SignupPage.tsx'), 'utf8');
    expect(signup).toContain('to="/legal"');
  });

  it('marks the legal copy as a draft and refuses to claim certifications', () => {
    const legal = readFileSync(path.resolve(process.cwd(), 'src/pages/LegalPage.tsx'), 'utf8');
    expect(legal).toMatch(/Draft — pending legal review/);
    expect(legal).toMatch(/not a medical device/);
    // No certification claims we have not earned.
    expect(legal).not.toMatch(/\bSOC 2 certified\b|\bISO 27001 certified\b/i);
  });
});

describe('pilot entitlement copy', () => {
  it('matches the backend pilot camera allowance', () => {
    const backend = readFileSync(
      path.resolve(process.cwd(), '../backend_api/app/api/signup.py'),
      'utf8',
    );
    // The entitlement the signup response advertises, e.g. "max_cameras": 4
    const match = backend.match(/"max_cameras"\s*:\s*(\d+)/);
    expect(match, 'the signup response no longer declares max_cameras').not.toBeNull();
    const entitlement = match![1];

    const signup = readFileSync(path.resolve(process.cwd(), 'src/pages/SignupPage.tsx'), 'utf8');
    const cameraClaims = [...signup.matchAll(/(\d+)\s+cameras/g)].map((m) => m[1]);
    expect(cameraClaims.length).toBeGreaterThan(0);
    for (const claim of cameraClaims) {
      expect(claim, 'signup copy disagrees with the pilot entitlement').toBe(entitlement);
    }
  });
});

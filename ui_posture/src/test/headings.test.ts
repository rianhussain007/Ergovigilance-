/**
 * Heading outline (audit F-UX-11).
 *
 * A page with no `<h1>` (Live monitoring, Workers, Users, the two setup
 * screens) gave screen readers nothing to announce and left the document title
 * meaningless; a page that opens with six `<h1>`s gives them six answers to
 * "what is this page?". This rule keeps exactly one top-level heading per
 * page-level file, with an explicit allowlist for files that render several
 * alternative views (early-return states you never see two of at once).
 */
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const PAGES_DIR = path.resolve(process.cwd(), 'src/pages');

/**
 * Files whose `<h1>`s come from mutually exclusive branches — a loading state,
 * an error state and the page itself — or from genuinely different documents
 * rendered in place of one another. Each render shows one.
 */
const ALTERNATIVE_VIEWS = new Set([
  'ConsentPage.tsx',
  'DeploymentCenter.tsx',
  'ReplayPage.tsx',
  'ReportsPage.tsx',
]);

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

function countTopLevelHeadings(source: string): number {
  const code = stripComments(source);
  const literalH1 = code.match(/<h1[\s>]/g)?.length ?? 0;
  // <SectionHeader title="…" as="h1" /> renders an <h1> too.
  const sectionHeaderH1 = code.match(/<SectionHeader[^>]*as="h1"/g)?.length ?? 0;
  return literalH1 + sectionHeaderH1;
}

describe('one top-level heading per page', () => {
  const files = readdirSync(PAGES_DIR).filter((file) => file.endsWith('.tsx'));

  it('covers every page file', () => {
    expect(files.length).toBeGreaterThan(30);
  });

  for (const file of files) {
    const source = readFileSync(path.join(PAGES_DIR, file), 'utf8');
    const headings = countTopLevelHeadings(source);

    if (ALTERNATIVE_VIEWS.has(file)) {
      it(`${file} renders a heading in every alternative view`, () => {
        expect(headings).toBeGreaterThanOrEqual(2);
      });
    } else {
      it(`${file} has exactly one top-level heading`, () => {
        expect(headings, `${file} should render exactly one <h1>`).toBe(1);
      });
    }
  }
});

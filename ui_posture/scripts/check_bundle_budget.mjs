#!/usr/bin/env node
/**
 * Bundle budget gate (docs/UX_SCORE_8_PROGRAM.md §W6).
 *
 * Performance was scored 5.5 partly on evidence: one 521 kB entry chunk that
 * Vite warned about, plus an unbounded chart chunk. This gate makes the numbers
 * visible in CI and fails when they grow:
 *
 *   - no single JS chunk may exceed `maxChunkKb` raw (the Vite 500 kB warning
 *     as a hard failure),
 *   - the entry chunk stays under `entryGzipKb` gzipped,
 *   - the whole build stays under `totalGzipKb` gzipped.
 *
 * Budgets live in scripts/bundle_budget.json so raising one is a reviewable
 * change rather than a silent regression.
 *
 * Usage: node scripts/check_bundle_budget.mjs   (run `npm run build` first)
 */
import { gzipSync } from 'node:zlib';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DIST = path.join(ROOT, 'dist');
const BUDGET = JSON.parse(readFileSync(path.join(HERE, 'bundle_budget.json'), 'utf8'));
const kb = (bytes) => bytes / 1024;

function walk(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else files.push(full);
  }
  return files;
}

let assets;
try {
  assets = walk(DIST);
} catch {
  console.error('check_bundle_budget: no dist/ directory — run `npm run build` first.');
  process.exit(1);
}

const budgets = BUDGET.budgets;
const js = assets.filter((file) => file.endsWith('.js'));
if (js.length === 0) {
  console.error('check_bundle_budget: dist/ has no JS assets — did the build run?');
  process.exit(1);
}

const measured = js
  .map((file) => {
    const raw = readFileSync(file);
    return {
      name: path.relative(DIST, file).replace(/\\/g, '/'),
      rawKb: kb(raw.length),
      gzipKb: kb(gzipSync(raw, { level: 9 }).length),
    };
  })
  .sort((a, b) => b.gzipKb - a.gzipKb);

const entry = measured.find((chunk) => /assets\/index-.*\.js$/.test(chunk.name)) ?? measured[0];
const totalGzipKb = measured.reduce((sum, chunk) => sum + chunk.gzipKb, 0);
const totalRawKb = measured.reduce((sum, chunk) => sum + chunk.rawKb, 0);

const failures = [];
for (const chunk of measured) {
  if (chunk.rawKb > budgets.maxChunkKb) {
    failures.push(`${chunk.name} is ${chunk.rawKb.toFixed(0)} kB raw (limit ${budgets.maxChunkKb} kB)`);
  }
}
if (entry.gzipKb > budgets.entryGzipKb) {
  failures.push(`entry ${entry.name} is ${entry.gzipKb.toFixed(0)} kB gzip (limit ${budgets.entryGzipKb} kB)`);
}
if (totalGzipKb > budgets.totalGzipKb) {
  failures.push(`build total is ${totalGzipKb.toFixed(0)} kB gzip (limit ${budgets.totalGzipKb} kB)`);
}

const head = BUDGET.report
  ? `check_bundle_budget: ${measured.length} JS chunks, ${totalRawKb.toFixed(0)} kB raw / ${totalGzipKb.toFixed(0)} kB gzip · entry ${entry.gzipKb.toFixed(0)} kB gzip`
  : 'check_bundle_budget';

if (failures.length === 0) {
  console.log(`${head} — within budget`);
  const top = measured.slice(0, 5).map((c) => `${c.name} ${c.gzipKb.toFixed(1)} kB gz`).join(' · ');
  console.log(`  largest: ${top}`);
  process.exit(0);
}

console.error(`${head} — over budget\n`);
for (const failure of failures) console.error(`  ${failure}`);
console.error('\nReduce the chunk (dynamic import / manualChunks) or raise the budget in scripts/bundle_budget.json with a reason.');
process.exit(1);

#!/usr/bin/env node
/**
 * UX guard rails (docs/UX_SCORE_8_PROGRAM.md §W5).
 *
 * Zero-dependency static checks that encode the rules the audit found broken at
 * least once. Everything here is a "must not come back" rule, so the gate runs
 * on source, not on a running app:
 *
 *   1. banned-claims        retired accuracy figures (94.1/97.6/88.6/86.4/76.9)
 *   2. confirm-dialog       window.confirm in product code (use a Dialog)
 *   3. full-reload          window.location.reload (use a refetch/state reset)
 *   4. raw-hex              hex colours outside the token system — ratcheted
 *   5. token-in-url         bearer tokens in query strings (logged as debt)
 *   6. img-alt              <img> without alt
 *   7. dialog-aria-modal    role="dialog" without aria-modal
 *   8. interval-helper      setInterval outside the shared polling helper
 *
 * Debt that exists today is recorded in ux_guards_allowlist.json with a reason
 * and (for counts) a ceiling. The ceiling may only go down: a PR that adds a
 * raw hex colour or another raw setInterval fails until it lowers the number.
 *
 * Usage: node scripts/ux_guards.mjs [--json]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const SRC = path.join(ROOT, 'src');
const ALLOWLIST = JSON.parse(readFileSync(path.join(HERE, 'ux_guards_allowlist.json'), 'utf8'));
const regex = ALLOWLIST.allowlist?.rules ?? {};

function walk(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else if (/\.(ts|tsx)$/.test(entry)) files.push(full);
  }
  return files;
}

const rel = (file) => path.relative(ROOT, file).replace(/\\/g, '/');
const isTest = (file) => rel(file).startsWith('src/test/');
const allowed = (rule, file) => (regex[rule] ?? []).some((entry) => rel(file) === entry);

const FILES = walk(SRC).filter((file) => !isTest(file));
const violations = [];
const fail = (rule, file, line, detail) =>
  violations.push({ rule, file: rel(file), line, detail });

function linesOf(file) {
  return readFileSync(file, 'utf8').split('\n');
}

/* ── 1. banned claims ───────────────────────────────────────────────── */
const BANNED = /(94\.1|97\.6|88\.6|86\.4|76\.9)/;
for (const file of FILES) {
  linesOf(file).forEach((line, index) => {
    if (BANNED.test(line)) fail('banned-claims', file, index + 1, line.trim());
  });
}

/* ── 2/3. confirm + full reload ─────────────────────────────────────── */
for (const file of FILES) {
  if (allowed('confirm-dialog', file) && allowed('full-reload', file)) continue;
  linesOf(file).forEach((line, index) => {
    if (!allowed('confirm-dialog', file) && /window\.confirm\(|(?<!\.)\bconfirm\(/.test(line)) {
      fail('confirm-dialog', file, index + 1, line.trim());
    }
    if (!allowed('full-reload', file) && /location\.reload\(/.test(line)) {
      fail('full-reload', file, index + 1, line.trim());
    }
  });
}

/* ── 4. raw hex colours, ratcheted per file ─────────────────────────── */
const hexCeilings = ALLOWLIST.allowlist?.hexColors ?? {};
for (const file of FILES) {
  const key = rel(file);
  const hits = linesOf(file).filter((line) => /#[0-9a-fA-F]{6}\b/.test(line)).length;
  const ceiling = hexCeilings[key];
  if (ceiling === undefined) {
    if (hits > 0) fail('raw-hex', file, 0, `${hits} hex colour literal(s) outside the token system`);
  } else if (hits > ceiling) {
    fail('raw-hex', file, 0, `${hits} hex literals, ceiling is ${ceiling} — lower the ceiling, don't raise it`);
  }
}

/* ── 5. tokens in query strings ─────────────────────────────────────── */
for (const file of FILES) {
  if (allowed('token-in-url', file)) continue;
  linesOf(file).forEach((line, index) => {
    if (/\?token=|&token=/.test(line)) fail('token-in-url', file, index + 1, line.trim());
  });
}

/* ── 6. <img> without alt ───────────────────────────────────────────── */
for (const file of FILES) {
  if (allowed('img-alt', file)) continue;
  const lines = linesOf(file);
  lines.forEach((line, index) => {
    if (/^\s*(\/\/|\*|\/\*)/.test(line)) return; // comments mention <img> freely
    if (!/<img\b/.test(line)) return;
    if (/<img\b[^>]*\balt=/.test(line)) return;
    // alt may be on a following line of the same element
    const window = lines.slice(index, index + 8).join(' ');
    if (!/\balt=/.test(window)) fail('img-alt', file, index + 1, '<img> without alt');
  });
}

/* ── 7. dialog semantics ────────────────────────────────────────────── */
for (const file of FILES) {
  const source = readFileSync(file, 'utf8');
  const dialogCount = (source.match(/role="dialog"/g) ?? []).length;
  if (dialogCount === 0) continue;
  const ariaModal = (source.match(/aria-modal/g) ?? []).length;
  if (ariaModal < dialogCount) {
    fail('dialog-aria-modal', file, 0, `${dialogCount} role="dialog", only ${ariaModal} aria-modal`);
  }
}

/* ── 8. setInterval outside the helper ──────────────────────────────── */
for (const file of FILES) {
  if (allowed('interval-helper', file)) continue;
  linesOf(file).forEach((line, index) => {
    if (/\bsetInterval\(/.test(line) && !/^\s*(\/\/|\*|\/\*)/.test(line)) {
      fail('interval-helper', file, index + 1, line.trim());
    }
  });
}

/* ── report ─────────────────────────────────────────────────────────── */
const json = process.argv.includes('--json');
if (json) {
  console.log(JSON.stringify({ violations }, null, 2));
} else if (violations.length === 0) {
  console.log(`ux_guards: OK — ${FILES.length} source files checked, 0 violations`);
} else {
  console.error(`ux_guards: ${violations.length} violation(s)\n`);
  for (const v of violations) {
    console.error(`  ${v.rule}  ${v.file}${v.line ? `:${v.line}` : ''}  ${v.detail}`);
  }
  console.error('\nFix the code, or record the debt in scripts/ux_guards_allowlist.json with a reason.');
}

process.exit(violations.length === 0 ? 0 : 1);

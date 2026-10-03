/**
 * One activation model (audit F-UX-17) + localisation coverage (audit F-UX-18).
 *
 * Activation used to be three flags in three places, so completing one journey
 * could still leave another prompting the user. These tests pin the single
 * store's behaviour, including the legacy-key migration that keeps existing
 * installs from being re-onboarded.
 */
import { afterEach, describe, expect, it } from 'vitest';
import {
  ACTIVATION_KEY,
  activationProgress,
  completeActivation,
  isActivationComplete,
  markActivationStep,
  readActivation,
  resetActivation,
} from '../services/activation';
import en from '../i18n/en.json';
import hi from '../i18n/hi.json';
import zh from '../i18n/zh.json';

const LEGACY_KEY = 'ergovigilance_onboarded';

afterEach(() => localStorage.clear());

function flatten(value: unknown, prefix = ''): string[] {
  if (!value || typeof value !== 'object') return [prefix];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    flatten(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe('activation store', () => {
  it('starts empty for a fresh browser', () => {
    expect(readActivation().stage).toBe('not_started');
    expect(isActivationComplete()).toBe(false);
    expect(activationProgress()).toEqual({ done: 0, total: 4 });
  });

  it('moves through in_progress to complete as steps land', () => {
    markActivationStep('camera');
    expect(readActivation().stage).toBe('in_progress');

    markActivationStep('worker');
    markActivationStep('session');
    markActivationStep('report');
    expect(readActivation().stage).toBe('complete');
    expect(isActivationComplete()).toBe(true);
    expect(activationProgress()).toEqual({ done: 4, total: 4 });
  });

  it('writes the legacy flag alongside the new state so nothing re-onboards', () => {
    completeActivation();
    expect(localStorage.getItem(ACTIVATION_KEY)).not.toBeNull();
    expect(localStorage.getItem(LEGACY_KEY)).toBe('true');
    expect(isActivationComplete()).toBe(true);
  });

  it('migrates an install that only has the legacy flag', () => {
    localStorage.setItem(LEGACY_KEY, 'true');
    expect(isActivationComplete()).toBe(true);
    // Migration persists, so a cleared legacy key cannot resurrect the modal.
    localStorage.removeItem(LEGACY_KEY);
    expect(isActivationComplete()).toBe(true);
  });

  it('resets both keys for a new signup', () => {
    completeActivation();
    resetActivation();
    expect(localStorage.getItem(ACTIVATION_KEY)).toBeNull();
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
    expect(isActivationComplete()).toBe(false);
  });

  it('survives corrupted state instead of throwing', () => {
    localStorage.setItem(ACTIVATION_KEY, '{not json');
    expect(readActivation().stage).toBe('not_started');
  });
});

describe('localisation coverage', () => {
  it('ships the same string set in every locale', () => {
    const expected = flatten(en).sort();
    expect(flatten(hi).sort()).toEqual(expected);
    expect(flatten(zh).sort()).toEqual(expected);
    expect(expected.length).toBeGreaterThan(50);
  });

  it('has no empty translations', () => {
    for (const [name, bundle] of Object.entries({ hi, zh })) {
      const empties = flatten(bundle).filter((key) => !key);
      expect(empties, `${name} has empty keys`).toEqual([]);
    }
  });
});

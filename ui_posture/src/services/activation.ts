/**
 * One activation model (audit F-UX-17).
 *
 * Three surfaces used to track "has this org got going yet?" three different
 * ways: the first-login modal wrote `ergovigilance_onboarded`, the /onboarding
 * checklist wrote the same key, and the dashboard's Getting-started card kept
 * its own counts. A user could complete the checklist and still be shown the
 * modal, or dismiss the modal and never see the checklist again.
 *
 * This module is the single persisted state. It stores only stage/step flags —
 * no personal data — and reads legacy keys once so existing users are not
 * re-onboarded.
 */
export const ACTIVATION_KEY = 'ergovigilance_activation';
const LEGACY_ONBOARDED_KEY = 'ergovigilance_onboarded';

export type ActivationStep = 'camera' | 'worker' | 'session' | 'report';

export interface ActivationState {
  /** not_started → in_progress → complete */
  stage: 'not_started' | 'in_progress' | 'complete';
  steps: Record<ActivationStep, boolean>;
  updatedAt: string;
}

const EMPTY: ActivationState = {
  stage: 'not_started',
  steps: { camera: false, worker: false, session: false, report: false },
  updatedAt: '',
};

function migrateLegacy(): ActivationState | null {
  if (localStorage.getItem(LEGACY_ONBOARDED_KEY) !== 'true') return null;
  // A user who finished the old flow is complete here too — and keeps the
  // legacy key so anything still reading it stays consistent.
  return { ...EMPTY, stage: 'complete', updatedAt: new Date().toISOString() };
}

export function readActivation(): ActivationState {
  try {
    const raw = localStorage.getItem(ACTIVATION_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ActivationState>;
      return {
        stage: parsed.stage ?? 'not_started',
        steps: { ...EMPTY.steps, ...(parsed.steps ?? {}) },
        updatedAt: parsed.updatedAt ?? '',
      };
    }
    const migrated = migrateLegacy();
    if (migrated) {
      localStorage.setItem(ACTIVATION_KEY, JSON.stringify(migrated));
      return migrated;
    }
    return EMPTY;
  } catch {
    return EMPTY;
  }
}

export function writeActivation(patch: Partial<ActivationState>): ActivationState {
  const current = readActivation();
  const next: ActivationState = {
    ...current,
    ...patch,
    steps: { ...current.steps, ...(patch.steps ?? {}) },
    updatedAt: new Date().toISOString(),
  };
  localStorage.setItem(ACTIVATION_KEY, JSON.stringify(next));
  if (next.stage === 'complete') {
    // Keep the legacy flag in sync for anything that still reads it.
    localStorage.setItem(LEGACY_ONBOARDED_KEY, 'true');
  }
  return next;
}

export function markActivationStep(step: ActivationStep, done = true): ActivationState {
  const current = readActivation();
  const steps = { ...current.steps, [step]: done };
  const anyDone = Object.values(steps).some(Boolean);
  const allDone = Object.values(steps).every(Boolean);
  return writeActivation({
    steps,
    stage: allDone ? 'complete' : anyDone ? 'in_progress' : 'not_started',
  });
}

/** Has the org been through activation? Used to gate the first-login modal. */
export function isActivationComplete(): boolean {
  return readActivation().stage === 'complete';
}

export function completeActivation(): ActivationState {
  return writeActivation({
    stage: 'complete',
    steps: { camera: true, worker: true, session: true, report: true },
  });
}

/** Called on signup so a brand-new org is not considered activated. */
export function resetActivation(): void {
  localStorage.removeItem(ACTIVATION_KEY);
  localStorage.removeItem(LEGACY_ONBOARDED_KEY);
}

export function activationProgress(): { done: number; total: number } {
  const { steps } = readActivation();
  const values = Object.values(steps);
  return { done: values.filter(Boolean).length, total: values.length };
}

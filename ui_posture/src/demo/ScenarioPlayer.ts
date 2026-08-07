import type { DemoScenario, ContextAwareRiskData, SystemPerformanceData } from './types';
import { computeAll } from './ScenarioEngine';
import type { DemoAction, DemoState } from './types';
import { scenarios } from './scenarios';

const TICK_MS = 250;

export function createInitialState(): DemoState {
  const scenario = scenarios[0];
  const result = computeAll(scenario, 0);
  return {
    active: false,
    playing: false,
    speed: 1,
    elapsed: 0,
    scenarioIndex: 0,
    dashboard: result.dashboard,
    sessions: result.sessions,
    aiMessages: result.aiMessages,
    contextAwareRisk: result.contextAwareRisk,
    alertEngine: result.alertEngine,
    systemPerformance: result.systemPerformance,
    executiveDashboard: result.executiveDashboard,
    presentationMode: false,
  };
}

export function demoReducer(state: DemoState, action: DemoAction): DemoState {
  switch (action.type) {
    case 'TOGGLE_DEMO': {
      if (state.active) {
        return { ...createInitialState(), active: false, presentationMode: state.presentationMode };
      }
      const scenario = scenarios[state.scenarioIndex];
      const result = computeAll(scenario, 0);
      return { ...state, active: true, playing: true, elapsed: 0, ...result };
    }
    case 'TOGGLE_PLAY': {
      return { ...state, playing: !state.playing };
    }
    case 'RESTART': {
      const scenario = scenarios[state.scenarioIndex];
      const result = computeAll(scenario, 0);
      return { ...state, playing: true, elapsed: 0, ...result };
    }
    case 'NEXT_SCENARIO': {
      const nextIdx = (state.scenarioIndex + 1) % scenarios.length;
      const scenario = scenarios[nextIdx];
      const result = computeAll(scenario, 0);
      return { ...state, playing: true, elapsed: 0, scenarioIndex: nextIdx, ...result };
    }
    case 'SET_SCENARIO': {
      const scenario = scenarios[action.index];
      const result = computeAll(scenario, 0);
      return { ...state, playing: true, elapsed: 0, scenarioIndex: action.index, ...result };
    }
    case 'SET_SPEED': {
      return { ...state, speed: action.speed };
    }
    case 'TICK': {
      if (!state.playing || !state.active) return state;
      const newElapsed = state.elapsed + action.delta;
      const scenario = scenarios[state.scenarioIndex];
      const maxTime = scenario.events.length > 0 ? scenario.events[scenario.events.length - 1].time + 10 : 120;
      if (newElapsed >= maxTime) {
        // Auto-advance to next scenario
        const nextIdx = (state.scenarioIndex + 1) % scenarios.length;
        const nextScenario = scenarios[nextIdx];
        const result = computeAll(nextScenario, 0);
        return { ...state, elapsed: 0, scenarioIndex: nextIdx, ...result };
      }
      const result = computeAll(scenario, newElapsed);
      return { ...state, elapsed: newElapsed, ...result };
    }
    case 'TOGGLE_PRESENTATION': {
      return { ...state, presentationMode: !state.presentationMode };
    }
    case 'STOP_DEMO': {
      return { ...createInitialState(), active: false, presentationMode: state.presentationMode };
    }
    case 'ACKNOWLEDGE_ALERT': {
      const history = state.alertEngine.history.map((a) =>
        a.id === action.alertId ? { ...a, acknowledged: true } : a
      );
      return { ...state, alertEngine: { ...state.alertEngine, history } };
    }
    default:
      return state;
  }
}

export function computeTickDelta(speed: number): number {
  return (TICK_MS / 1000) * speed;
}

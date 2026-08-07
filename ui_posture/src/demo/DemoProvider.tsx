import React, { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react';
import type { DemoAction, DemoState } from './types';
import { createInitialState, demoReducer, computeTickDelta } from './ScenarioPlayer';
import { scenarios } from './scenarios';
import { useToast } from '@/src/hooks/useToast';

interface DemoContextValue {
  state: DemoState;
  dispatch: React.Dispatch<DemoAction>;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  restart: () => void;
  nextScenario: () => void;
  setScenario: (index: number) => void;
  setSpeed: (speed: number) => void;
  toggleDemo: () => void;
  togglePresentation: () => void;
  stopDemo: () => void;
}

const DemoContext = createContext<DemoContextValue | null>(null);

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(demoReducer, undefined, createInitialState);
  const { addToast } = useToast();
  const lastToastTime = useRef<Set<number>>(new Set());

  const toggleDemo = useCallback(() => {
    dispatch({ type: 'TOGGLE_DEMO' });
    lastToastTime.current = new Set();
  }, []);

  const value: DemoContextValue = {
    state,
    dispatch,
    play: () => dispatch({ type: 'PLAY' }),
    pause: () => dispatch({ type: 'PAUSE' }),
    togglePlay: () => dispatch({ type: 'TOGGLE_PLAY' }),
    restart: () => {
      dispatch({ type: 'RESTART' });
      lastToastTime.current = new Set();
    },
    nextScenario: () => {
      dispatch({ type: 'NEXT_SCENARIO' });
      lastToastTime.current = new Set();
    },
    setScenario: (index: number) => {
      dispatch({ type: 'SET_SCENARIO', index });
      lastToastTime.current = new Set();
    },
    setSpeed: (speed: number) => dispatch({ type: 'SET_SPEED', speed }),
    toggleDemo,
    togglePresentation: () => dispatch({ type: 'TOGGLE_PRESENTATION' }),
    stopDemo: () => {
      dispatch({ type: 'STOP_DEMO' });
      lastToastTime.current = new Set();
    },
  };

  useEffect(() => {
    if (!state.active || !state.playing) return;
    const interval = setInterval(() => {
      const delta = computeTickDelta(state.speed);
      dispatch({ type: 'TICK', delta });
    }, 250);
    return () => clearInterval(interval);
  }, [state.active, state.playing, state.speed]);

  useEffect(() => {
    if (!state.active || !state.playing) return;
    const scenario = scenarios[state.scenarioIndex];
    if (!scenario) return;

    for (const event of scenario.events) {
      if (event.toast && event.time <= state.elapsed && !lastToastTime.current.has(event.time)) {
        lastToastTime.current.add(event.time);
        addToast(event.toast.type, event.toast.title);
      }
    }
  }, [state.elapsed, state.active, state.playing, state.scenarioIndex, addToast]);

  return (
    <DemoContext.Provider value={value}>
      {children}
    </DemoContext.Provider>
  );
}

export function useDemo(): DemoContextValue {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error('useDemo must be used within a DemoProvider');
  return ctx;
}

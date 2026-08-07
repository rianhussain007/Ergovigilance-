# ErgoVigilance — Demo Mode

## Overview

Demo Mode transforms the static dashboard into a living, breathing AI ergonomic monitoring platform. With a single click, the entire application begins to evolve automatically — worker statuses change, risk levels rise and fall, charts animate, notifications appear, and the AI Safety Assistant provides real-time commentary.

No backend required. No API keys. No real cameras.

## How to Start Demo Mode

1. Run the application: `npm run dev`
2. Locate the **Demo Controls** toolbar at the top of every page
3. Click the **"Demo Mode"** button (Play icon)
4. The dashboard immediately starts evolving through a pre-built scenario

## Controls

| Control | Action |
|---------|--------|
| ▶ Demo Mode | Toggle demo mode on/off |
| ▶ / ⏸ Play/Pause | Pause or resume the demo timeline |
| ↺ Restart | Restart the current scenario from the beginning |
| ⏭ Next Scenario | Skip to the next scenario |
| Scenario Selector (dropdown) | Choose any scenario directly |
| 1x / 2x / 5x Speed | Control how fast the scenario plays |
| 🎙 AI Assistant | Open the AI Safety Assistant side panel |
| 📽 Presentation Mode | Hide all mock/debug labels (clean production UI) |

## Scenarios

Five realistic workplace scenarios are included:

| Scenario | Worker | Key Risks | Duration (1x) |
|----------|--------|-----------|---------------|
| **Office Worker** | Elena Rodriguez | Neck flexion, shoulder tension from desk work | ~100s |
| **Assembly Line Worker** | Marcus Thorne | Neck flexion, trunk asymmetry, shoulder elevation | ~95s |
| **Warehouse Worker** | James Kowalski | Deep trunk flexion, knee angle stress, heavy lifting | ~85s |
| **Machine Operator** | Chen Wei | Sustained neck flexion, shoulder elevation, static stance | ~68s |
| **Inspection Worker** | Priya Sharma | Prolonged trunk flexion, neck strain from leaning | ~82s |

Each scenario follows a realistic arc:
- **Beginning**: Baseline posture metrics
- **Middle**: Risk factors emerge (issues detected, toasts fired)
- **Climax**: Highest risk level reached (AI intervention triggered)
- **Resolution**: Worker corrects posture, risk decreases
- **End**: Scenario auto-advances to the next one

## AI Safety Assistant

Open the AI Safety Assistant panel (🎙 button) to see deterministic, context-aware messages such as:

- *"Neck flexion at 32° for 10+ seconds. Risk of cervical strain if sustained."*
- *"Worker corrected posture. Neck flexion reduced from 28° to 16°."*
- *"Risk level stabilising. Worker is adapting to ergonomic cues."*
- *"Trunk flexion at 38° and knee angle at 62°. High biomechanical load."*

Messages are generated per-event — no random / LLM content.

## Camera Playback

When Demo Mode is active, the static camera placeholder is replaced with an animated SVG-based posture visualization showing:

- Stick figure in different poses (good posture, neck flexion, trunk flexion, shoulder elevation, recovery)
- Rotates to match the current scenario state
- FPS counter, resolution badge, REC indicator
- Live risk level overlay
- Fullscreen toggle (/)

## Presentation Mode

Click the Presentation Mode button in the Demo Controls toolbar to hide:

- Mock data labels
- Debug information
- Loading states
- Any UI element that signals this is a demo / prototype

Only the clean production interface remains visible. Perfect for demos to faculty, recruiters, or clients.

## Architecture

```
src/demo/
├── types.ts              # Type definitions (DemoScenario, DemoEvent, DemoState)
├── scenarios.ts          # 5 predefined scenarios with full data + event timelines
├── ScenarioEngine.ts     # Computes dashboard state from scenario + elapsed time
├── ScenarioPlayer.ts     # Timer management (play/pause/speed/reducer)
├── DemoProvider.tsx       # React context provider + useDemo hook

src/hooks/
├── useDashboard.ts              # Original hook (unchanged)
├── useDashboardWithDemo.ts      # Drop-in replacement that checks demo context

src/components/demo/
├── DemoControls.tsx       # Compact toolbar (play/pause/speed/scenario selector)
├── KpiRow.tsx             # Summary metrics row (workers, compliance, alerts...)
├── AIAssistantPanel.tsx   # Side panel with AI insight messages
├── CameraPlayback.tsx     # Animated SVG posture camera
└── index.ts               # Barrel exports
```

### Data Flow

```
DemoProvider (React Context)
  ↓
useDashboardWithDemo() hook
  ├── Demo active?  → returns demo state from DemoProvider
  └── Demo inactive? → calls original useDashboard() (mock JSON or real API)
    ↓
All existing pages / components consume identical data shapes
    ↓
Switching demo off instantly reverts to real mock/API data
```

## Future Backend Integration

When the real FastAPI backend is connected (via `ApiDashboardRepository`):

1. The Demo Engine becomes entirely optional
2. With demo mode off, all pages use real API data via `useDashboardWithDemo()` → `useDashboard()` → `getDashboardData()` → `ApiDashboardRepository`
3. The scenario engine can be used for training, onboarding, and UI testing
4. The `useDashboardWithDemo()` hook requires zero changes — it delegates to the real hook when `state.active === false`

No modifications to the demo engine are needed. The abstraction layer ensures a clean swap.

## Tips

- Use **5x speed** for quick walkthroughs
- Switch scenarios mid-play to demonstrate different ergonomic risks
- Open the **AI Assistant** panel before pressing Play for the full experience
- Use **Presentation Mode** during client demos
- The demo respects your existing theme (dark/light/system)

# ErgoVigilance Pro — Frontend Architecture

## Folder Structure

```
src/
  components/
    cards/              Reusable card components (StatusCard, FeatureCard, IssueCard, etc.)
    charts/             Chart components (RiskHistoryChart, CameraPanel)
    common/             Shared UI primitives (LoadingCard, ErrorCard, EmptyState, SectionHeader, StatusBadge, ReportButton)
    layout/             App chrome (Header, DashboardLayout)
    Layout.tsx          Root layout wiring
    Sidebar.tsx         Navigation sidebar
  hooks/
    useDashboard.ts     Data-fetching hook (orchestrates repository + polling)
    usePolling.ts       Polling abstraction (disabled when config.AUTO_REFRESH=false)
  services/
    dashboardService.ts Facade that selects repository based on config.USE_MOCK
    WebSocketClient.ts  Future WebSocket client (empty implementation)
  repositories/
    DashboardRepository.ts     Repository interface (the contract)
    MockDashboardRepository.ts In-memory mock implementation (serves JSON)
    ApiDashboardRepository.ts  Future FastAPI implementation (TODO stubs)
  types/
    api.ts               Centralized TypeScript interfaces — single source of truth
    dashboard.ts         Re-exports from api.ts for backward compatibility
  config/
    index.ts             Application configuration (USE_MOCK, REFRESH_INTERVAL, API_BASE_URL, WS_URL)
  mock/
    dashboard.json       Mock dashboard response
    sessions.json        Mock session list
    trends.json          Mock trend analysis data
  screens/               Page-level screen components
  assets/                Static assets
```

## Repository Pattern

```
┌─────────────────────────────────────────────────────┐
│                   UI Components                      │
│  (Dashboard, StatusCard, FeatureCard, etc.)          │
└────────────────┬────────────────────────────────────┘
                 │ calls
                 ▼
┌─────────────────────────────────────────────────────┐
│               useDashboard (hook)                    │
│  Manages loading / error / data state                │
└────────────────┬────────────────────────────────────┘
                 │ calls
                 ▼
┌─────────────────────────────────────────────────────┐
│           dashboardService (facade)                  │
│  Selects repository based on config.USE_MOCK          │
└────────────────┬────────────────────────────────────┘
                 │ delegates to
                 ▼
┌─────────────────────────────────────────────────────┐
│          DashboardRepository (interface)             │
│  getDashboard() | getSessions() | getTrend()         │
├─────────────────────┬───────────────────────────────┤
│  MockDashboardRepo  │  ApiDashboardRepo (TODO)       │
│  (returns JSON)     │  (will call FastAPI)            │
└─────────────────────┴───────────────────────────────┘
```

### Switching from Mock to Real API

1. Open `src/config/index.ts`
2. Set `USE_MOCK: false`
3. Implement `ApiDashboardRepository` methods with `fetch()` calls
4. No UI component changes required

## Data Flow

```
MockDashboardRepository ──► dashboardService ──► useDashboard ──► Components
       │                         │
  Reads JSON files         Returns typed           Manages loading,
  from src/mock/           DashboardResponse       error, empty states
```

## Polling Layer

Located in `src/hooks/usePolling.ts`.

- **Disabled by default** (`config.AUTO_REFRESH = false`)
- Enable by setting `config.AUTO_REFRESH = true` and implementing the backend
- The `useDashboard` hook already integrates `usePolling` — no wiring needed

## Future WebSocket Integration

`src/services/WebSocketClient.ts` contains an empty singleton with:

- `connect()` / `disconnect()`
- `subscribe(channel, handler)` / `unsubscribe(channel, handler)`
- `send(data)`

When the FastAPI WebSocket endpoint is ready, implement these methods to push real-time updates to the dashboard.

## Configuration

All app-wide settings live in `src/config/index.ts`:

| Key              | Default             | Description                              |
|------------------|---------------------|------------------------------------------|
| `USE_MOCK`       | `true`              | Use mock JSON instead of real API         |
| `AUTO_REFRESH`   | `false`             | Enable periodic polling                   |
| `REFRESH_INTERVAL` | `30_000`          | Polling interval in milliseconds          |
| `API_BASE_URL`   | `'/api'`            | Base path for REST endpoints              |
| `WS_URL`         | `'ws://localhost:8000/ws'` | WebSocket server URL            |

## Type Contracts

All API contracts are defined in `src/types/api.ts`. This is the single source of truth for:

- `DashboardResponse` — full dashboard payload
- `SessionRecord` — a single session row
- `TrendResponse` — weekly + feature trend data
- Sub-types: `LiveStatus`, `ErgonomicFeature`, `Issue`, `Recommendations`, `SessionAnalytics`, `RiskDataPoint`, `TrendAnalysis`

## Loading / Error / Empty States

Reusable components in `src/components/common/`:

- **LoadingCard** — skeleton placeholder (configurable lines and height)
- **ErrorCard** — error display with optional retry button
- **EmptyState** — "no data" placeholder with icon and message
- **SectionHeader** — consistent section title bar
- **StatusBadge** — colored status pill (Active / Completed / Interrupted)
- **ReportButton** — consistent action button with color variants

All screens handle all four states (loading → empty → error → success) using these primitives.

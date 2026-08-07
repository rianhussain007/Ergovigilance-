# ErgoVigilance Pro - Ergonomic Posture Analysis Dashboard

A production-grade React dashboard for industrial ergonomic monitoring. Built with React 19, Vite, TailwindCSS 4, Recharts, and React Router.

## Features

- **Live Monitoring** — Real-time risk tracking with camera panel, ergonomic features, issue detection, and analytics
- **Analytics** — Weekly risk trends, pie chart distribution, issue frequency bar chart, neck/trunk area charts
- **Trend Analysis** — Risk vs baseline comparison, improvement by category, individual feature trends
- **Session History** — Searchable, filterable, sortable session table with detail drawer
- **Reports Center** — Generate/download buttons, searchable report history
- **Settings** — Theme (dark/light/system), camera selection, refresh interval, mock API toggle, notifications
- **Toast Notifications** — Success, error, info, warning toasts
- **Global Search** — Ctrl+K search modal across sessions, workers, pages
- **Collapsible Sidebar** — Navigation with active page indicator
- **Responsive** — Tablet, laptop, desktop

## Tech Stack

React 19 · Vite 6 · TailwindCSS 4 · TypeScript · React Router 7 · Recharts · Lucide React · Motion

## Getting Started

```bash
npm install
npm run dev
```

Opens at `http://localhost:3000`.

## Project Structure

```
src/
  components/
    cards/        StatusCard, FeatureCard, IssueCard, AnalyticCard, TrendCard
    charts/       RiskHistoryChart (Recharts), CameraPanel
    common/       LoadingCard, ErrorCard, EmptyState, SectionHeader, StatusBadge, ReportButton, Drawer, SearchModal
    layout/       Header
    Layout.tsx    Root layout with sidebar + header + outlet
    Sidebar.tsx   Collapsible nav with React Router links
  pages/
    LiveMonitoring.tsx     Dashboard at /
    AnalyticsPage.tsx      Analytics at /analytics
    SessionHistory.tsx     Sessions at /sessions
    TrendAnalysisPage.tsx  Trends at /trends
    ReportsPage.tsx        Reports at /reports
    SettingsPage.tsx       Settings at /settings
  hooks/          useDashboard, usePolling, useTheme, useToast
  services/       dashboardService, WebSocketClient
  repositories/   DashboardRepository interface + Mock + Api stubs
  types/          api.ts — centralized data contracts
  config/         USE_MOCK, AUTO_REFRESH, API_BASE_URL, WS_URL
  mock/           dashboard.json, sessions.json, trends.json
```

## Routes

| Path        | Page              |
|-------------|-------------------|
| `/`         | Live Monitoring   |
| `/analytics`| Analytics         |
| `/sessions` | Session History   |
| `/trends`   | Trend Analysis    |
| `/reports`  | Reports           |
| `/settings` | Settings          |

## Scripts

- `npm run dev` — Start development server
- `npm run build` — Production build
- `npm run preview` — Preview production build
- `npm run lint` — TypeScript type checking

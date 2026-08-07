# Frontend Asset Audit — `ui_posture/`

---

## 1. Is It a Complete React Project?

**Yes.** Fully scaffolded with:

- `package.json` — dependencies declared
- `vite.config.ts` — Vite build config with React + Tailwind plugins
- `tsconfig.json` — TypeScript strict mode with `@/` path alias
- `index.html` — HTML entry point
- `src/main.tsx` — React root mount
- `src/App.tsx` — Application root with tab-based routing
- `src/components/` — Layout shell (Sidebar, Header)
- `src/screens/` — 6 page-level screen components
- `node_modules/` — installed (package-lock.json present)
- `dist/` — previously built output exists

---

## 2. Technology Stack Audit

| Technology | Present? | Details |
|---|---|---|
| **React** | ✅ Yes | React 19.0.1 (latest stable) |
| **Vite** | ✅ Yes | Vite 6.2.3 |
| **TypeScript** | ✅ Yes | Strict mode, `@/` path alias |
| **Tailwind CSS** | ✅ Yes | Tailwind v4 via `@tailwindcss/vite` plugin |
| **Framer Motion** | ✅ Yes | `motion` package v12 (used for tab transitions + sidebar indicator) |
| **Lucide Icons** | ✅ Yes | v0.546 (used in all screens) |
| **React Router** | ❌ No | Uses `useState<TabId>` with `AnimatePresence` instead |
| **Shadcn/ui** | ❌ No | No shadcn dependency or components directory |
| **Next.js** | ❌ No | Pure Vite SPA |
| **State Management** | ❌ None | No Zustand, Redux, or Context API |
| **Data Fetching** | ❌ None | No React Query, SWR, or fetch calls |
| **WebSocket** | ❌ None | No WS client library |
| **Testing** | ❌ None | No vitest, jest, or cypress config |
| **Styling System** | ✅ Partial | Custom `cn()` utility via `clsx` + `tailwind-merge` (declared but unused) |

### Notable extras
- `@google/genai` — Gemini AI SDK dependency (unused in screens)
- `express` + `@types/express` — server dependency (possibly for SSR/proxy)
- Custom design token system in `index.css` (M3-inspired dark theme)

---

## 3. Which Pages Already Exist?

| Page | Path (tab id) | File | Lines | Status |
|---|---|---|---|---|
| **Dashboard** | `dashboard` | `src/screens/Dashboard.tsx` | 282 | Mock UI complete |
| **Monitoring** | `monitoring` | `src/screens/Monitoring.tsx` | 215 | Mock UI complete |
| **Image Analysis** | `image_analysis` | `src/screens/ImageAnalysis.tsx` | 222 | Mock UI complete |
| **Video Review** | `video_review` | `src/screens/VideoReview.tsx` | 264 | Mock UI complete |
| **Analytics** | `analytics` | `src/screens/Analytics.tsx` | 206 | Mock UI complete |
| **Workers** | `workers` | `src/screens/Workers.tsx` | 268 | Mock UI complete |
| **Task Recognition** | `task_recognition` | Falls back to `Dashboard` | — | Placeholder |

### Navigation map
```
Sidebar tabs (7):
  dashboard       → Dashboard.tsx      ✅ Active
  monitoring      → Monitoring.tsx      ✅ Active
  image_analysis  → ImageAnalysis.tsx   ✅ Active
  video_review    → VideoReview.tsx     ✅ Active
  analytics       → Analytics.tsx       ✅ Active
  workers         → Workers.tsx         ✅ Active
  task_recognition→ Dashboard.tsx       ⚠️ Disabled + "Soon" badge
```

All navigation is handled via `useState<TabId>` in `App.tsx` with Framer Motion `AnimatePresence` transitions — no URL-based routing.

---

## 4. Which Pages Are Static Only?

**All 6 pages are 100% static.** Every number, chart bar, alert message, worker profile, image URL, and risk score is hardcoded.

| Page | Static Content | Dynamic Content |
|---|---|---|
| **Dashboard** | 142 workers, 12 alerts, 24.5 risk score, 99.2% accuracy, bar chart heights, alert feed items, body part intensities, AI insight text | `activeRisk` counter (random walk ±1 every 5s for demo effect) |
| **Monitoring** | Live feed image, SVG skeleton overlay, risk index 18 ("LOW"), joint angles (15°, 5°, 45°, 12°), event timeline bars, toast warning | `showToast` state (appears after 3s timeout) |
| **Image Analysis** | Trunk flexion 42°, neck extension 18°, shoulder abd 15°, RULA 7/7, REBA 10/15, violation list, AI recommendations, workspace optimization | None whatsoever |
| **Video Review** | Video thumbnail, SVG skeleton, risk graph path, 4 filmstrip frame cards, task recognition panel, joint strain analysis, environmental data | None whatsoever |
| **Analytics** | Aggregate risk 14.2, 24 violations, 182s duration, 98.2% compliance, trend chart SVG, export hub placeholders, facility heatmap, scatter plot | None whatsoever |
| **Workers** | 5 worker directory entries, Marcus Thorne profile, historical trend chart, training status, AI diagnosis, intervention log, live overlay | None whatsoever |

**External image URLs:** All screens use Google-hosted placeholder images (`lh3.googleusercontent.com/aida-public/...`) which may or may not resolve at runtime.

---

## 5. Which Components Are Reusable?

### Currently reusable (in `src/components/`)

| Component | File | Usage | Notes |
|---|---|---|---|
| `Layout` | `Layout.tsx` | App shell | Wraps all content, composes Sidebar + Header |
| `Sidebar` | `Sidebar.tsx` | Navigation | 7 tabs, active state via `layoutId` animation, disabled task_recognition |
| `Header` | `Header.tsx` | Top bar | Search input, live status badge, notification/help buttons, user profile |

### NOT reusable — inlined in screens

These should be extracted into `src/components/` for a production app:

| Concept | Currently Inlined In | Candidate Component Name |
|---|---|---|
| Risk badge (colored pill) | Sidebar, Monitoring, Dashboard, Workers | `<RiskBadge>` |
| Circular gauge/progress | Dashboard (donut), Monitoring (risk ring) | `<RiskGauge>` |
| KPI stat card | Dashboard, Analytics, ImageAnalysis | `<StatCard>` |
| Progress bar | Monitoring, VideoReview | `<ProgressBar>` |
| Glass panel card | All screens (via `glass-panel` CSS class) | `<Panel>` or `<Card>` |
| Bar chart (inline divs) | Dashboard, VideoReview | `<ChartBar>` |
| SVG skeleton overlay | Monitoring, ImageAnalysis, VideoReview, Workers | `<SkeletonOverlay>` |
| Button variants | All screens (multiple inline styles) | `<Button>` |
| Toast/notification | Monitoring | `<Toast>` |
| Alert feed item | Dashboard | `<AlertItem>` |
| Worker card | Workers | `<WorkerCard>` |
| Feature gauge bar | Monitoring (joint angles) | `<FeatureGauge>` |

### Utility library (`src/lib/`)

| File | Contents | Status |
|---|---|---|
| `types.ts` | `TabId` type union — 27 characters | ✅ Minimal but complete |

---

## 6. Completion Estimate

### Breakdown by layer

| Layer | What's Done | What's Missing | Completion % |
|---|---|---|---|
| **Project scaffold** | Vite + React + TS + Tailwind + Framer Motion | React Router, shadcn, state management, testing | 90% |
| **Layout & navigation** | Sidebar, Header, tab switching with animations | URL-based routing (deep linking, browser back/forward) | 80% |
| **Page layout & styling** | All 6 pages have polished dark-theme layouts | Responsive breakpoints untested, mobile layout unknown | 70% |
| **Static mock content** | Every screen has realistic-looking hardcoded data | No tolerance for empty/loading/error states | 60% |
| **API integration layer** | None | ~20 API calls needed (predict, sessions, workers, analytics, history) | 0% |
| **Data fetching** | None | React Query or fetch wrapper, loading spinners, error handling | 0% |
| **State management** | None | Session state, worker list, analysis results, UI state | 0% |
| **Real-time WebSocket** | None | Live monitoring frame streaming | 0% |
| **Image upload + analysis** | Upload zone UI exists | File handling, preview, submit to API, display results | 10% |
| **Video upload + analysis** | Player UI + filmstrip exists | File handling, progress tracking, API polling/WS | 10% |
| **Live camera monitoring** | Mock feed with static SVG skeleton exists | `getUserMedia()`, WebSocket frame streaming, real skeleton | 15% |
| **Worker management** | Directory + profile UI exists | CRUD API integration, search/filter, real data | 15% |
| **Analytics** | Charts and export hub UI exists | Real API data, interactive charts library, CSV/PDF export | 10% |
| **PDF report generation** | None | Server-side report generation API needed | 0% |
| **Authentication** | Mock "Admin Root" user in sidebar | Login flow, JWT, role-based access | 0% |
| **Error boundaries** | None | Graceful error handling per page | 0% |

### Overall completion

| Metric | Value |
|---|---|
| **Visual/UI polish** | ~75% complete |
| **Functionality / data integration** | ~5% complete |
| **Overall frontend** | **~18% complete** |

### What this means for the migration plan

| Item | Value |
|---|---|
| **Estimated time saved vs. building from scratch** | ~2 weeks (UI scaffolding, design system, page layouts) |
| **Remaining work** | ~12-14 weeks (API integration, state management, real-time, testing) |
| **Most valuable pre-built assets** | Sidebar navigation, Layout shell, page grid structures, design tokens |
| **Least valuable** | All hardcoded mock data (will be 100% replaced) |
| **Can be directly reused** | `Layout.tsx`, `Sidebar.tsx`, `Header.tsx`, `App.tsx`, `index.css` (design tokens), `vite.config.ts` |
| **Should be refactored** | Every screen — extract inlined UI into reusable components |

### Estimated effort to make it production-ready

| Phase | Focus | Effort |
|---|---|---|
| **Phase A** | Extract shared components, add React Router, set up API client | 2 weeks |
| **Phase B** | Integrate Image Analysis + Video Review with backend APIs | 3 weeks |
| **Phase C** | Build real-time Monitoring with WebSocket + getUserMedia | 3 weeks |
| **Phase D** | Integrate Workers + Analytics with database-backed endpoints | 3 weeks |
| **Phase E** | Authentication, error handling, responsive polish, testing | 3 weeks |
| **Total** | | **14 weeks** (1 developer) |

---

## Key Gaps vs. Migration Plan Requirements

| Requirement from Migration Plan | Status in `ui_posture/` | Gap |
|---|---|---|
| React Router (URL-based routing) | ❌ Missing | Tab state only — no `/dashboard`, `/monitor` URLs |
| Shared component library | ❌ Missing | Everything inlined — no `<Button>`, `<Card>`, `<Badge>` |
| API client layer | ❌ Missing | No fetch/axios, no React Query |
| WebSocket client | ❌ Missing | No WS support |
| Image upload → API flow | ❌ Missing | Dropzone UI exists, no file handling |
| Video upload → API flow | ❌ Missing | Player UI exists, no upload/progress |
| getUserMedia integration | ❌ Missing | Static image in place of real camera feed |
| Live skeleton overlay from keypoints | ⚠️ Partial | SVG skeletons exist but are hardcoded — need dynamic rendering from MediaPipe data |
| PDF report generation | ❌ Missing | Not started |
| Authentication | ⚠️ Partial | Mock user in sidebar only |
| Chart library (Recharts/Chart.js) | ❌ Missing | All charts are hand-drawn SVGs |
| `cn()` utility | ✅ Present but unused | `clsx` + `tailwind-merge` installed but never imported |

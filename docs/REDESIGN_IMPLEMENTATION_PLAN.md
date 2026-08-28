# ErgoVigilance Redesign — Implementation Plan
**Date:** August 28, 2026  
**Goal:** Match the presentation vision (terminal-style aesthetic, full feature parity)

---

## Architecture Alignment: Presentation vs Current

### What Already Works (No Changes Needed)
| Section | Status | Evidence |
|---------|--------|----------|
| Tech Engine (Pose → RULA/REBA → Risk) | ✅ Complete | pose_engine.py, reba_scoring.py, task_recognition.py |
| Triage Dashboard (Alert Center, Risk Distribution) | ✅ Complete | AlertCenter.tsx, DashboardPage.tsx |
| Live Monitoring (Skeleton toggle) | ✅ Complete | LiveMonitoring.tsx with Raw/Skel toggle |
| Incident Replay (Timeline, Summary) | ✅ Complete | ReplayPage.tsx (393 lines) |
| PDF Export (Watermarked) | ✅ Complete | report_pdf.py with watermark CSS |
| AI Assistant (Ollama) | ✅ Complete | assistant.py + AIAssistantPanel.tsx |
| Worker Module (Self-view, Face, Badge) | ✅ Complete | WorkerSelfView.tsx, worker_faces.py |

### What Needs Redesign (Priority Order)

#### 1. Deployment Center — MAJOR REWRITE
**Current:** Simple metric cards (261 lines)  
**Target:** Terminal-style 4-panel layout matching presentation

**Panels to build:**
1. **Multi-Cam Engine** — Live camera status with terminal-style output:
   ```
   CAM01 [ACTIVE]  — STATION 3
   CAM02 [ACTIVE]  — STATION 7
   CAM03 [STANDBY] — STATION 2
   DEPLOYED STATIONS: 12 / SCALING FACTOR: 1.2x
   ```
2. **Database & Inference** — Model stats with terminal output:
   ```
   sqlite> PRAGMA database_list;
   0: 'ergo_db.sqlite' [RW]
   > MODEL STATUS: TRAINED (35,241 RECORDS)
   > ALGORITHM: RF + SVG (ACC: 94.5%)
   > INFERENCE TIME: <15ms (EDGE COMPUTE)
   ```
3. **Audit Trail** — Live log stream:
   ```
   [2024-07-22T08:01:34] ADMIN_LOGIN: user='j.smith' ip=192.168.1.45
   [2024-07-22T08:05:12] SESSION_START: station_id=ST-03 user_id=W1045
   [2024-07-22T08:15:00] HEALTH_METRIC: cpu=45% mem=68% gpu=32% [OK]
   [2024-07-22T08:30:45] ALERT: POSTURE_RISK_DETECTED (RULA: 7) - STATION 5
   ```
4. **Settings & Config** — Editable terminal-style form:
   ```
   [SETTINGS.CONF]
   CAMERA_REFRESH_MS:    [ 1000  ] (EDIT)
   EDGE_COMPUTE_PROFILE: [ MEDIUM ] (EDIT)
   SYSTEM_THEME_DARK:    [X] (TOGGLE)
   LOG_VERBOSITY:        [ INFO  ] (EDIT)
   SAVE CONFIG:          [YES/NO]
   ```

**Implementation:**
- Rewrite DeploymentCenter.tsx with 4-panel grid
- Add monospace font for terminal output
- Add real-time log streaming from audit trail
- Add editable settings with save functionality

#### 2. Live Monitoring — Override & Log Panel Polish
**Current:** Override button exists, observations API works  
**Target:** Match presentation's "Override & Log" panel with:
- Manual Screenshot button (already exists in CameraPanel)
- Append Log textarea (already exists)
- Timeline markers for overrides and logs
- Visual connection between override and timeline position

**Implementation:**
- Enhance OverrideButton with reason textarea
- Add timeline markers for overrides
- Style to match presentation's dark terminal aesthetic

#### 3. AI Assistant — Context-Awareness Enhancement
**Current:** Basic Ollama integration works  
**Target:** Match presentation's context-aware responses:
- "What is ErgoVigilance tracking right now?" → "Tracking 7 body features via MediaPipe, currently orchestrating RULA rules..."
- Station-specific context
- RULA/REBA parameter explanations

**Implementation:**
- Enhance assistant.py prompts with station context
- Add RULA/REBA explanation templates
- Improve AIAssistantPanel UI with context cards

#### 4. Dashboard — Risk Distribution Donut
**Current:** Basic charts exist  
**Target:** Match presentation's clean donut chart with percentage labels

**Implementation:**
- Update DashboardPage risk distribution to use donut style
- Add percentage labels inside the chart

---

## Implementation Sequence

### Phase 1: Deployment Center Rewrite (Highest Visual Impact)
1. Create terminal-style CSS classes (monospace, glow effects)
2. Rewrite DeploymentCenter.tsx with 4-panel layout
3. Wire Multi-Cam Engine to camera API
4. Wire Database & Inference to model metrics
5. Wire Audit Trail to audit API with live streaming
6. Wire Settings to config API with save

### Phase 2: Live Monitoring Polish
1. Enhance OverrideButton with reason input
2. Add timeline markers for overrides
3. Style Override & Log panel to match presentation

### Phase 3: AI Assistant Enhancement
1. Enhance assistant.py with station context
2. Add RULA/REBA explanation templates
3. Update AIAssistantPanel UI

### Phase 4: Dashboard Polish
1. Update risk distribution to donut style
2. Add percentage labels
3. Match presentation's clean aesthetic

---

## Technical Details

### Terminal-Style CSS Classes
```css
/* Terminal output styling */
.terminal-output {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background: #0a0e14;
  color: #00ff88;
  border: 1px solid #00ff8833;
  border-radius: 8px;
  padding: 16px;
  font-size: 12px;
  line-height: 1.6;
}

.terminal-prompt {
  color: #00aaff;
}

.terminal-success {
  color: #00ff88;
}

.terminal-warning {
  color: #ffaa00;
}

.terminal-error {
  color: #ff4444;
}
```

### Deployment Center Data Flow
```
Camera API → Multi-Cam Engine panel
Model Metrics → Database & Inference panel  
Audit API → Audit Trail panel (live streaming)
Settings API → Settings & Config panel
```

### Live Monitoring Override Flow
```
User clicks Override → Reason textarea appears
User enters reason → POST /api/session/override
Override saved → Timeline marker added
Override visible in session replay
```

---

## Estimated Effort

| Task | Lines | Time |
|------|-------|------|
| Deployment Center rewrite | ~500 | 2-3 hours |
| Live Monitoring polish | ~100 | 30 min |
| AI Assistant enhancement | ~150 | 1 hour |
| Dashboard donut chart | ~50 | 30 min |
| **Total** | **~800** | **4-5 hours** |

---

## Success Criteria

1. Deployment Center matches presentation's terminal-style aesthetic
2. All 4 panels show real data (not placeholders)
3. Live Monitoring override panel is intuitive
4. AI Assistant provides context-aware responses
5. Dashboard risk distribution matches presentation style
6. Build passes with zero errors
7. All features work end-to-end

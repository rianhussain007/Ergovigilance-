# TRL-6 Entry Evidence

Everything below is measured on this host and sourced to a file on disk. Each
section states what is **NOT MEASURED** so no row can be read as covering more
than it does.

**Machine:** 8 logical CPU cores, 12.7 GB RAM, **no GPU** (`nvidia-smi` absent,
`torch.cuda.is_available() == False`). Windows (Git Bash toolchain).

**Scope of the performance section:** CPU-only, short runs (15–120 s) in
compute mode, plus the 30-min / 15-min RTSP demo runs below. No GPU number,
no 4-hour number, no throughput claim for the spec's 8 workers/feed or
10 FPS/feed.

---

## Blocker 1 — Aspect-correct joint angles

**Before:** `_calculate_angles` ran on NORMALIZED keypoints against a 0.1-unit
vertical reference, so the result silently depended on frame aspect ratio.
**After:** keypoints are denormalized with the real frame dimensions before the
angle maths. `extract_features_from_keypoints` also rejects 0–1 input with an
explicit error, so a missing denormalization cannot silently return.

Same physical posture — a true 60° trunk lean — across four aspect ratios
(prototype `_lean_keypoints(60.0, w, h)` in `yolo_cloud/tests/test_trl6_blockers.py`,
re-measured for this document):

| Frame | Aspect | True | Before (normalized) | After (pixel) | Error after |
|---|---|---|---|---|---|
| 1280×720 | 16:9 | 60° | **44.26°** | **60.00°** | 0.00° |
| 640×480 | 4:3 | 60° | **52.41°** | **60.00°** | 0.00° |
| 720×720 | 1:1 | 60° | 60.00° | **60.00°** | 0.00° |
| 720×1280 | 9:16 | 60° | **72.01°** | **60.00°** | 0.00° |

- The bug **under-reported on wide frames and over-reported on portrait** — the
  9:16 error (+12.01°) was not visible from 16:9 alone.
- 1:1 is unchanged, confirming the fix removes aspect distortion rather than
  shifting results.
- Risk outcome unchanged where it matters: a true 60° lean scores **HIGH on
  15/15** frames.
- Unit tolerance: on a square frame the legacy and fixed paths agree to
  **<0.001°** (not bit-identical — the legacy vertical reference is 0.1 units ≈
  72 px at 720, vs 1 px in pixel space).

**Not claimed:** none of this measures detection accuracy. The angle maths is
given synthetic keypoints; YOLO itself is not evaluated here.

---

## Blocker 2 — Pre-alert video clips

**Implementation:** per-camera ring buffer of `CLIP_BUFFER_SECONDS (10 s) ×
INFERENCE_FPS (10) = 100 frames`, JPEG at ≤640 px wide, saved only on a HIGH
alert, served by `GET /api/cloud/cameras/{id}/clips/{alert_id}`. Clips are
**pre-roll only** — length is however many frames the buffer held when the alert
fired, not a fixed 10 s.

### End-to-end chain (slouch smoke)

`scripts/verify_slouch_chain.py` → `outputs/slouch_smoke/result.json`

| | |
|---|---|
| Legs passed | **7 / 7** |
| `chain_complete` | **`true`** |
| Legs failed | none |
| Legs not implemented | none |
| `video_clip_saved` | PASS — HTTP 200, 24,825 bytes, `ftyp` magic |
| Evidence PDF | `outputs/slouch_smoke/daily_report.pdf`, 2,425 bytes, `%PDF` |
| Exit code | 0 |

Legs: `slouch_trigger`, `risk_state_high`, `dwell_trigger`,
`websocket_event_sent`, `alert_created`, `pdf_generated`, `video_clip_saved`.

In this smoke the clip holds **1 frame**, because the alert fires on the very
first scored frame (the test footage opens with the worker already bent) and
frame 1 carries ffmpeg + model load. Session artifact confirms it:
`frame_count = 2`, `highest_risk = HIGH`. That is correct pre-roll, not a
broken buffer — and it is why the under-load measurement below matters.

### Clip capture under load (the multi-frame proof)

Measured across all clips written by the soak runs in `recordings/clips/soak-*/`:

| | |
|---|---|
| Clips written | **224** |
| Multi-frame (>1 frame) | **219 / 224 = 97.8%** |
| Mean frames | 59.0 |
| Max frames | **100** (the configured 10 s × 10 FPS capacity) |
| Clips at exactly 100 frames | **73** — the buffer saturates as designed |
| Clips with exactly 1 frame | 2 — the first alert of a run, before warm-up |
| Unplayable (no `moov` atom) | **3 / 224 = 1.3%** — truncated at camera teardown |

**Verdict:** multi-frame pre-alert clips are confirmed at steady state; the
buffer reaches its full 100-frame capacity.

**Open defect found while measuring → FIXED:** 3 clips were cut off while still
being written (camera stopped mid-encode), leaving an MP4 without a `moov` atom
and therefore unplayable. Root cause: the soak harness exited without stopping
cameras, killing the daemon processing threads mid-encode so `writer.release()`
never ran. The fix has four parts (`yolo_cloud/ingestion.py`,
`scripts/soak_cloud.py`):

1. Every `VideoWriter` — construction included — is covered by `try/finally`,
   so an in-process interruption still finalizes the container.
2. After release, a top-level box walk verifies `moov` (MP4) / `idx1` (AVI);
   a truncated clip is **deleted and counted** in `metrics_snapshot()` as
   `clips_truncated`, never left to be served.
3. `get_clip()` disk recovery re-verifies the container, so an orphan a hard
   kill did leave behind is refused instead of streamed to a supervisor.
4. The soak harness now stops all cameras gracefully before exiting (threads
   joined → in-flight encodes finish) and reports `clips.saved_total` /
   `clips.truncated_total` in the summary.

**Re-run evidence** — `soak_20260925T164246Z_summary.json` (label `moov-fix`,
1 stream × 60 s): **46 clips saved, 0 truncated**; all 47 clip files written
during the run parse (`moov` present in every one, ffprobe reads format and
duration). The 3 historical files remain broken — they are pre-fix artifacts.
Guarded by 4 tests in `TestClipIntegrity`
(`yolo_cloud/tests/test_trl6_blockers.py`); suite: **134 passed** (gate,
2026-09-26).

**Not claimed:** clip encode/write cost is not broken out — it sits inside the
frame latency number and is not separately attributed.

---

## Blocker 3 — WebSocket contract

Chosen option **(a)**: event push on alert creation, keeping the 5 Hz snapshot.

| Path | Message | Guarantee |
|---|---|---|
| Guaranteed | `{"type": "update"}` every 200 ms, carries `recent_alerts` | an alert appears within **200 ms** |
| Accelerator | `{"type": "alert"}` pushed on creation | best-effort, **may duplicate** the snapshot |

Clients **must de-duplicate on `alert_id`**. The contract is documented in three
places: `cloud_ws()` and `push_alert_event()` in `yolo_cloud/api.py`, the
`websocket_event_sent` leg wording in `scripts/verify_slouch_chain.py`, and the
proxy note in `ui_posture/vite.config.ts` (the frontend has no cloud WS client
yet; `ws: true` was added so one can be wired through `/cloud-api`).

Observed delivery in the chain run: `HIGH alert ALT-000001 delivered via 'alert'`.

---

## Test counts

| Suite | Result |
|---|---|
| `yolo_cloud/tests` | **134 passed** (0 failed) |
| `backend_api/tests` (55 test files) | **425 passed, 0 failed, 0 errors, 1 skipped, 1 deselected** |

The `backend_api` gate used to read *397 passed / 17 failed / 13 errors*. Every
one of those was root-caused and fixed in `0de8d40` rather than skipped:

| File | Was | Root cause (fixed) |
|---|---|---|
| `test_fail_closed_endpoints.py` | 9F | `get_repository()` served mock/empty payloads with no live service; 503 is now enforced centrally |
| `test_task_model_v2.py` | 5F | explicit model path ignored + model fast path ran before the "no person"/seated gates; 3 assertions tracked a pre-retrain artifact contract |
| `test_risk_calibration.py` | 2F | default bundle schema unreadable (`features` vs `feature_columns`) and a missing explicit override silently substituted the legacy model |
| `test_model_manifest.py` | 1F | `models/MANIFEST.json` still recorded the pre-`7348403` `task_model_v2.pkl` size/sha |
| teardown (13E) | `RuntimeError: generator didn't stop` | `app/main.py` lifespan yielded twice |

The single remaining **skip** is `test_postgres_store.py` (`DATABASE_URL not
set`) and the **deselect** is `-m "not hardware"` from `pytest.ini` — both
pre-existing and both print their reason.

---

## Soak / capacity table (CPU-only)

Full detail and sources: `docs/SIZING_SOAK_CLOUD.md`. Raw summaries in
`outputs/soak/*_summary.json`.

Each run is classed **capacity-probe** (1–2 streams, does this host hold the
budget at that pool size?) vs **spec-load** (4 streams, the spec's own load
point) so one shortfall factor never has to carry both meanings.

| Streams | Class | p95 worst stream | vs 500 ms budget | FPS/stream |
|---|---|---|---|---|
| 1 (60 s) | capacity-probe | 607.6 ms | **BREACH** | 3.83 |
| 1 (120 s) | capacity-probe | 652.8 ms | **BREACH** | 4.31 |
| 1 (15 s) | capacity-probe | 493.5 ms | *within* | 2.06 |
| 1 (decode mode) | capacity-probe | 309.9 ms | *within* | 3.65 |
| 2 (60 s) | capacity-probe | 1027.6 ms | **BREACH** | 1.89 |
| 2 (15 s) | capacity-probe | 320.3 ms | *within* | 4.25 |
| 4 (60 s) | spec-load | 1772.6 ms | **BREACH** | 1.03 |
| 4 (120 s) | spec-load | 831.2 ms | **BREACH** | 1.34 |
| 4 × RTSP (1800 s) | spec-load | 4407.8 ms | **BREACH** | 0.37 |
| 4 × RTSP (900 s) | spec-load | 4034.7 ms | **BREACH** | 0.39 |

The two RTSP rows are the relevant-environment demo runs (next section):
real ffmpeg decode over TCP/8554 from four distinct sources, publishers on
the **same** 8-CPU box as the scorer — a worst case, read with the
same-box caveat below.

**What this supports:**

- **Every run of ≥60 s breaches the 500 ms p95 budget — at 1, 2 and 4 streams.**
  Both 1-stream runs breach independently, and the 60 s timeline shows only
  ~4 s of warm-up before CPU pins at **230–590% of 8 cores with a single
  stream**. The constraint is inference, not contention.
- Throughput, not budget: **~4 FPS/stream at 1 stream, ~1 FPS/stream at 4.**
- Short windows flatter this workload: both 15 s runs land near/under budget
  while the same configuration at 60 s breaches. Quote a range, never one number.
- The one within-budget decode run (309.9 ms) achieved it while **dropping
  69.3% of decoded frames (883/1274)** — p95 covers *scored* frames only, so a
  low p95 bought with dropped frames is not spare capacity. That drop rate is an
  **upper bound**: ffmpeg reads a file with no real-time pacing.

**What this does NOT support:** "1–2 streams within budget, 4 streams breach."
That sentence is contradicted by the measurements and must not be written.

**Scope notes:**

- **Tracker = `builtin-iou`.** `tracker_backend = builtin-iou`,
  `tracking_audit.active_tracker = _SimpleTracker (IoU)`,
  `bytetrack_available = False`. ByteTrack cannot be imported in this ultralytics
  build (`lapx` not installed), so **no ByteTrack counter exists and none is
  quoted**.
- **No accuracy claim of any kind** appears in this document.
- Earlier 4-stream run (`soak_20260924T124208Z`, 120 s): 1.68 FPS/stream,
  634.7% CPU mean, 961 MB RSS, 20 distinct tracks, **0 ID switches**. The
  tracker's 120 s × 4-cam audit (20 new / 8 expired / 0 reacquisitions) is
  **inflated by the feeder looping the clip** and is *not* a cross-over rate.

---

## Relevant-environment demo — 4-camera RTSP trial (2026-09-26)

The relevant environment for this stage is a 4-camera RTSP trial fed by real
internet CCTV footage, run through the production ingestion path
(`scripts/soak_cloud.py --urls rtsp://...` — the same reader the cloud
service uses; **no HTTP fallback was involved**).

**Rig** (`scripts/rtsp_trial_pubs.py`, MediaMTX v1.21.1, local TCP/8554):

| Cam | Source | Provenance |
|---|---|---|
| soak-1 / cam1 | PETS2009 S1L2 (split-screen, cropped) | UCSD SVCL — research + attribution |
| soak-2 / cam2 | UCSD Anomaly S1 Peds1 `007.mp4` | UCSD Anomaly — research + citation |
| soak-3 / cam3 | warehouse lifting video | local YouTube footage — internal test only |
| soak-4 / cam4 | assembly-lines video | local YouTube footage — internal test only |

Full licence rows: `docs/FOOTAGE_PROVENANCE.csv` (10 clips fetched by
`scripts/fetch_cctv_footage.py`; footage and the MediaMTX binary are
gitignored — only the scripts and manifest are committed).

**Run A — duration/capacity (`trl6-rtsp-main`, 1800 s, jsonl+summary in
`outputs/soak/soak_20260926T021815Z*`):**

| Metric | Value |
|---|---|
| streams | 4 × RTSP (TCP), four distinct real sources |
| distinct tracks | 112 (soak-1 39, soak-2 10, soak-3 32, soak-4 31) |
| ID switches | **0** |
| alerts | 1000 (hit the query cap) |
| clips saved / truncated | **628 / 0** |
| p95 worst stream | 4407.8 ms — **BREACH** (budget 500 ms) |
| FPS/stream (mean) | 0.37; drop 95.1% of 54 192 decoded frames |
| CPU / RSS | mean 544%, max 694%; RSS max 1251 MB |
| badge binds (numeric specs) | 3/3 fired, via the registry (`bind_badge`) |
| persons ≥2 (all cams) | **28 / 30** one-minute snapshots |
| persons ≥2 (same camera) | **19 / 30**; peak 5 persons (soak-3: 2, soak-4: 3) |
| supervisor overrides | 0 |

**Run B — identity attribution (`trl6-rtsp-identity`, 900 s,
`outputs/soak/soak_20260926T025639Z*`):**

| Metric | Value |
|---|---|
| alerts with `worker_id` | **529 / 581 (91%)** |
| badge binds (wildcard specs) | 224, through the registry — same call the REST `bind` endpoint makes, executed in-process by the harness (disclosed, not a hidden shortcut) |
| identity audit rows | append-only `outputs/audit/identity_audit.jsonl` (`bind` + `reentry` events with actor `soak-harness`) |
| distinct tracks / ID switches | 65 / **0**; 1 reentry rebind |
| clips saved / truncated | **270 / 0** |
| p95 worst stream | 4034.7 ms — **BREACH** |
| supervisor overrides | 0 |

Why the remaining ~52 alerts have no `worker_id`: they fired before the
first bind landed (t ≈ 20 s) or on tracks the binder had not yet seen.
Attribution starts at bind time, per track; there is deliberately no
back-fill of pre-bind alerts.

**Spot-check sheet — DRAFT, pending human approval:**
`outputs/tri6_demo/spotcheck/alerts_spotcheck.csv` + `*.jpg` (12 rows, 3 per
camera, one pre-alert frame each; produced by `scripts/spotcheck_draft.py`
from Run B's alert rows). `model_prediction` is the system output under
test; `agent_label` is `PENDING-USER-APPROVAL`. **No label from this sheet
may be quoted or cited until a human fills `human_label` and sets
`approved`.**

**UDP transport probe (`trl6-rtsp-udp`, 120 s × 4 cams,
`outputs/soak/soak_20260926T034839Z_summary.json`):**

| Metric | Value |
|---|---|
| transport negotiated | **UDP** — proven on the ingest side: the 4 production reader ffmpegs ran `-rtsp_transport udp -f rawvideo` (captured cmdlines, `outputs/tri6_demo/ffmpeg_cmdlines.txt`; the rig's publish side stays TCP) |
| decoded frames | **4340** on all 4 streams (1128 / 1133 / 1015 / 1064) |
| FPS/stream | per-stream fps > 0 in 54/60 steady samples (mean of positives 0.77–0.85; run mean 0.74, max 1.5) |
| alerts / clips | 132 alerts; clips **71 saved / 0 truncated** |
| tracks / ID switches | 20 / **0** |
| p95 worst stream | **1966.0 ms — BREACH** (354/354 frames over the 500 ms budget) |
| drop rate | **91.8%** of decoded frames (single-slot buffer under 4-stream same-box load) |
| CPU / RSS | mean 540.0%, max 703.2%; RSS mean 873 MB, max 1126.7 MB |

**Transport verdict:** RTSP over TCP end-to-end through the production
reader (Runs A/B above), **and UDP is now measured**: with
`RTSP_TRANSPORT=udp` the production reader negotiates UDP and streams
frames, alerts and clips — verified from the ingest ffmpeg command lines,
not assumed from config. But the UDP probe still breaches the latency
budget (p95 1966.0 ms) and drops 91.8% of decoded frames in the 4-stream
same-box worst case, and no load-matched TCP-vs-UDP A/B was run, so **no
transport performance claim** is made in either direction.
`RTSP_TRANSPORT=tcp` remains the configured default.

**Same-box caveat — read with every p95/FPS row above:** four ffmpeg
publishers, MediaMTX and 4-stream pose inference share these 8 CPUs
(CPU mean 531–544%, max 703%). These numbers are a **worst case for
same-host rigs**, not a field deployment where feeds arrive over the
network from separate hosts.

---

## Cloud engine accuracy (yolo_cloud)

**The first accuracy number for the cloud engine.** Script:
`scripts/eval_cloud_accuracy.py` (prints a JSON report; one process per profile
because `yolo_cloud.config` reads the env at import).

Method: every labelled still is pushed through the production risk path
`YOLOPoseEngine.process_frame()` (YOLOv8-pose → COCO_17 features →
`models/yolo_risk_model.pkl`), with a fresh `camera_id` per frame so tracker and
temporal state never cross stills; the largest person in the frame supplies the
band. Ground truth is the `human_risk` column of
`outputs/real_data/human_labels.csv`. Date: 2026-09-25, CPU-only.

### Dataset join

| Item | Count |
|---|---|
| rows in `human_labels.csv` | 1429 |
| rows joining `outputs/real_data/frames/` | **184** |
| rows not in that dir | **1245** — all of them resolve under `outputs/real_data/frames_diverse/`, so 1429/1429 images exist on disk |
| rows carrying a human risk label | 119 (LOW 117, MEDIUM 2, **HIGH 0**) |
| labelled rows with an image → evaluated **N** | **119** (all inside the 184-row join) |
| of those, `quality=occluded` | 8 (reported both included and excluded) |
| `partial` / `blurry` / `clear` / unflagged | 52 / 2 / 1 / 56 |

Ground truth contains **no HIGH row**, so no HIGH accuracy is claimed — same
Safe Claims rule as the 87.6% number (LOW/MEDIUM only).

### Results (both profiles, same 119 frames)

| Profile | N | Accuracy | LOW recall | MEDIUM precision / recall | predicted MEDIUM | predicted HIGH | no detection |
|---|---|---|---|---|---|---|---|
| default `yolov8s-pose` @ 640 | 119 | **0.84% (1/119)** | **0.00 (0/117)** | 0.011 / 0.50 | 93 | 24 | 2 |
| capacity `yolov8n-pose` @ 320 | 119 | **0.84% (1/119)** | **0.00 (0/117)** | 0.016 / 0.50 | 64 | 37 | 18 |

Occluded rows excluded (N=111): default **0.90% (1/111)**, capacity
**0.90% (1/111)** — the 8 occluded frames are not what drives the result.

Confusion (rows = human, cols = predicted), default profile:

| | LOW | MEDIUM | HIGH | no detection |
|---|---|---|---|---|
| LOW (117) | 0 | 92 | 23 | 2 |
| MEDIUM (2) | 0 | 1 | 1 | 0 |

The capacity profile differs only by moving 29 LOW rows from MEDIUM to HIGH and
by 16 extra no-detections (18 vs 2): detection completeness at 320 px is
**101/119 (84.9%)** vs **117/119 (98.3%)** at 640 px.

### Verdict

- **Keep `yolov8s-pose` @ 640 as the default profile.** The capacity profile is
  not more accurate (identical 1/119) *and* loses 16 detections, so the
  measured capacity gain (2 streams within budget at n/320, `ccbcfbe`) is the
  only thing n/320 buys — accuracy data give no reason to switch.
- **No cloud accuracy claim may be made.** Both profiles are effectively
  non-discriminative against this truth set: LOW recall is 0.00 and the head
  never emits LOW at all. The risk head needs human-labelled training data
  before any number is quoted.
- **Do not quote the artifact's own `metrics`** (`yolo_risk_model.pkl`:
  `test_accuracy 0.9413`, `n_samples 80454`) — that is agreement with its
  rule-derived training labels, not with human assessors.
- **The Safe Claims 87.6% belongs to the on-premise backend engine and is
  untouched by this section.** These numbers are scoped to the cloud engine,
  this dataset (N=119, one site, LOW-heavy) and this date.

Reproduce:

```bash
python scripts/eval_cloud_accuracy.py --label default-s640
YOLO_MODEL=yolov8n-pose.pt YOLO_IMGSZ=320 \
  python scripts/eval_cloud_accuracy.py --label capacity-n320
```

---

## NOT MEASURED (do not quote)

| Item | Why |
|---|---|
| GPU memory / utilisation | no GPU on this host |
| 10 FPS per feed | frames are processed at whatever rate the pipeline sustains; measured rate reported instead |
| 8 workers per feed | available footage is single-worker clips, so 8 real tracks per feed cannot be produced |
| 4-hour continuous run | longest run here is 30 min (RTSP demo); the harness supports `--seconds 14400` but the full run was not executed |
| ByteTrack-specific counters | ByteTrack cannot be imported in this ultralytics build |
| Real badge/QR hardware | demo binds go through the same registry call the REST endpoint uses, executed in-process by the harness — no physical scanner was exercised |
| Backend-engine accuracy | out of scope for this pack; the pre-existing Safe Claims 87.6% is the only human-ground-truth number for that engine. Cloud-engine accuracy IS measured above. |
| Frame-drop rate in compute mode | no FFmpeg decoder runs, so decoded stays 0; use `--urls <rtsp...>` |
| Clip encode cost as a share of latency | clips *are* written under load (measured above) but encode/write is inside frame latency |
| Camera-socket-drop detection latency | ffmpeg drains its buffer for minutes; the drill uses a deterministic client-kill instead |
| UDP vs TCP latency (load-matched A/B) | one 120 s UDP probe exists (functional, p95 1966.0 ms BREACH — measured above) but it was not load/duration-matched against a TCP run, so no comparative transport number |

---

## Evidence index

| Claim | Artifact |
|---|---|
| Angle before/after | `yolo_cloud/tests/test_trl6_blockers.py::TestAspectCorrectAngles` |
| Pixel-space guard | `backend/services/features.py::assert_pixel_space` |
| Chain 7/7 + `chain_complete` | `outputs/slouch_smoke/result.json`, `outputs/slouch_smoke/run.log` |
| Clip under load (224 clips) | `recordings/clips/soak-*/` |
| Soak summaries | `outputs/soak/*_summary.json` |
| RTSP demo rig (4 cams) | `scripts/rtsp_trial_pubs.py` (MediaMTX + publishers) |
| RTSP demo runs A/B | `outputs/soak/soak_20260926T021815Z_summary.json`, `soak_20260926T025639Z_summary.json` |
| UDP transport probe | `outputs/soak/soak_20260926T034839Z_summary.json` (label `trl6-rtsp-udp`) + ingest cmdlines `outputs/tri6_demo/ffmpeg_cmdlines.txt` |
| Badge binds in demo (jsonl `type=bind`) | same two jsonl files; audit trail `outputs/audit/identity_audit.jsonl` |
| persons ≥2 snapshots (`type=persons`) | `outputs/soak/soak_20260926T021815Z.jsonl` (28/30 times) |
| Alerts carrying `worker_id` | `soak_20260926T025639Z_summary.json` → `alerts_with_worker_id = 529/581` |
| Spot-check sheet (DRAFT, unapproved) | `outputs/tri6_demo/spotcheck/alerts_spotcheck.csv` + `*.jpg` |
| Footage licences | `docs/FOOTAGE_PROVENANCE.csv`, `scripts/fetch_cctv_footage.py` |
| Capacity split + sizing | `docs/SIZING_SOAK_CLOUD.md` |
| Cloud accuracy (both profiles) | `scripts/eval_cloud_accuracy.py` → JSON report (N=119) |
| Cloud tests | `yolo_cloud/tests/` (134) |
| Backend tests | `backend_api/tests/` (425 passed / 0 failed / 0 errors) |

**Commits:** `525090a` (TRL-6 blockers), `82a3231` (P0 security batch),
`217edf8` (test config drift + pixel-guard crash fix), `0de8d40` (fail-closed,
model/manifest contract, single-yield lifespan → backend gate green),
`5557fa0` (footage fetcher + provenance), `21a390d` (multi-source feeder),
`1d42742` (RTSP rig), `82884e4` (bind + persons instrumentation),
`83822ea` (spot-check draft extractor), `18a47ca` (wildcard dominant-track binds).

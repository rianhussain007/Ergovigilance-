# TRL-6 Entry Evidence

Everything below is measured on this host and sourced to a file on disk. Each
section states what is **NOT MEASURED** so no row can be read as covering more
than it does.

**Machine:** 8 logical CPU cores, 12.7 GB RAM, **no GPU** (`nvidia-smi` absent,
`torch.cuda.is_available() == False`). Windows (Git Bash toolchain).

**Scope of the performance section:** CPU-only, short runs (15–120 s), compute
mode unless stated. No GPU number, no 4-hour number, no throughput claim for the
spec's 8 workers/feed or 10 FPS/feed.

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

**Open defect found while measuring:** 3 clips were cut off while still being
written (camera stopped mid-encode), leaving an MP4 without a `moov` atom and
therefore unplayable. This is a real robustness gap in the clip writer and is
**documented, not fixed** in this pass.

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
| `yolo_cloud/tests` | **96 passed** (0 failed) |
| `backend_api/tests` (55 test files) | **397 passed, 17 failed, 13 errors, 1 skipped, 1 deselected** |

Baseline comparison for `backend_api`: **395 → 397 passed** (the two new
per-IP rate-limit tests). Failures **18 → 17**, back to the pre-existing
baseline: a regression from `525090a` (the pixel-space guard rejected
zero-filled keypoints) was found and fixed in `217edf8`.

The remaining **17 failures are all pre-existing and none are auth/security**:

| File | Failures | Cause |
|---|---|---|
| `test_fail_closed_endpoints.py` | 9 | fail-closed on missing model/service |
| `test_task_model_v2.py` | 5 | model bundle shape/gating |
| `test_risk_calibration.py` | 2 | model artifact absent |
| `test_model_manifest.py` | 1 | model manifest |

The **13 errors** are all the pre-existing teardown
`RuntimeError: generator didn't stop`; their test bodies pass.

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

## NOT MEASURED (do not quote)

| Item | Why |
|---|---|
| GPU memory / utilisation | no GPU on this host |
| 10 FPS per feed | frames are processed at whatever rate the pipeline sustains; measured rate reported instead |
| 8 workers per feed | available footage is single-worker clips, so 8 real tracks per feed cannot be produced |
| 4-hour continuous run | all runs here are 15–120 s; the harness supports `--seconds 14400` but the full run was not executed |
| ByteTrack-specific counters | ByteTrack cannot be imported in this ultralytics build |
| Accuracy / detection quality | out of scope by task constraint |
| Frame-drop rate in compute mode | no FFmpeg decoder runs, so decoded stays 0; use `--urls <rtsp...>` |
| Clip encode cost as a share of latency | clips *are* written under load (measured above) but encode/write is inside frame latency |
| Camera-socket-drop detection latency | ffmpeg drains its buffer for minutes; the drill uses a deterministic client-kill instead |
| UDP RTSP transport | untested; `RTSP_TRANSPORT=tcp` is the configured default |

---

## Evidence index

| Claim | Artifact |
|---|---|
| Angle before/after | `yolo_cloud/tests/test_trl6_blockers.py::TestAspectCorrectAngles` |
| Pixel-space guard | `backend/services/features.py::assert_pixel_space` |
| Chain 7/7 + `chain_complete` | `outputs/slouch_smoke/result.json`, `outputs/slouch_smoke/run.log` |
| Clip under load (224 clips) | `recordings/clips/soak-*/` |
| Soak summaries | `outputs/soak/*_summary.json` |
| Capacity split + sizing | `docs/SIZING_SOAK_CLOUD.md` |
| Cloud tests | `yolo_cloud/tests/` (96) |
| Backend tests | `backend_api/tests/` (397 passed / 17 failed / 13 errors) |

**Commits:** `525090a` (TRL-6 blockers), `82a3231` (P0 security batch),
`217edf8` (test config drift + pixel-guard crash fix).

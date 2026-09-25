# Cloud Sizing & Soak — Measured Results

Every number below is **measured on this machine** and sourced to a JSON file in
`outputs/soak/`. Rows that could not be measured here are marked **NOT
MEASURED** — do not quote them as facts. No accuracy claims are made anywhere
in this document.

## Machine under test

| Item | Value | Source |
|---|---|---|
| CPU | 8 logical cores | `machine.cpus` in soak summary |
| RAM | 12.7 GB | `machine.ram_gb` |
| GPU | **none present** (`torch.cuda.is_available() == False`) | `machine.gpu_measured: false` |
| OS | Windows (Git Bash toolchain) | — |

## Load model

| Item | Value | Source |
|---|---|---|
| Target | 4 cams × 8 workers @ 10 FPS | requirement — **not met on CPU; see below** |
| Measured throughput | 4 streams, **~1.7 FPS/stream mean** (0–2.5 range) | `soak_20260924T124208Z_summary.json → fps_per_stream` |
| CPU utilization | **634.7% mean / 714.3% max** of 800% | same, `cpu_pct` |
| Process RSS | **961 MB mean / 980 MB max** | same, `rss_mb` |
| Tracker backend | `builtin-iou` (ByteTrack needs `lapx`; not installed here) | same, `tracker_backend` |

**Reading:** the CPU box sustains ~1.7 FPS/stream at the test resolution —
well under the 10 FPS/stream target. This is the dominant sizing fact: the
10 FPS × 4-cam target requires the GPU box (or `lapx` + resolution reduction,
itself **NOT MEASURED** here). Do not quote a GPU FPS number — none was run.

## Capacity by stream count (verdict split)

A single shortfall factor ("7.4× short") mixes two different questions, so each
run is classed: **capacity-probe** at 1–2 streams (does this host hold the p95
budget at that pool size?) vs **spec-load** at 4 (does the spec's own concurrency
pass?). `scripts/soak_cloud.py` now prints `scale:` and `run_class` for this.

| Run label | Streams | Class | p95 worst stream | vs 500 ms | FPS/stream | Source |
|---|---|---|---|---|---|---|
| `capacity-1stream` (60 s) | 1 | capacity-probe | **607.6 ms** | BREACH | 3.83 | `soak_20260925T100012Z_summary.json` |
| `capacity-1stream-120s` | 1 | capacity-probe | **652.8 ms** | BREACH | 4.31 | `soak_20260925T100322Z_summary.json` |
| `capacity-2stream` (60 s) | 2 | capacity-probe | **1027.6 ms** | BREACH | 1.89 | `soak_20260925T100119Z_summary.json` |
| `commit-check` (60 s) | 4 | spec-load | **1772.6 ms** | BREACH | 1.03 | `soak_20260925T083105Z_summary.json` |
| `calibration-120s` | 4 | spec-load | **831.2 ms** | BREACH | 1.34 | `soak_20260925T081146Z_summary.json` |
| `wording-check` (15 s) | 1 | capacity-probe | 493.5 ms | *within* | 2.06 | `soak_20260925T100822Z_summary.json` |
| `commit-check-wording` (15 s) | 2 | capacity-probe | 320.3 ms | *within* | 4.25 | `soak_20260925T083340Z_summary.json` |
| `rtsp-decoder-dropcheck` | 1 | capacity-probe | 309.9 ms | *within* | 3.65 | `soak_20260925T081558Z_summary.json` |

### The expected "1–2 streams within budget, 4 breach" is NOT supported

Do not write that sentence. The measurements say the opposite:

- **Every run of ≥60 s breaches the 500 ms p95 budget — at 1, 2 and 4 streams.**
  Both 1-stream runs breach independently (607.6 ms and 652.8 ms), so this is
  not warm-up: the 60 s timeline shows only the first ~4 s idle while the model
  loads, then CPU pinned at **230–590% of 8 cores with a single stream**.
- The three *within* rows are each explainable and none generalises:
  - **1 stream / 15 s (493.5 ms)** and **2 streams / 15 s (320.3 ms)** — 15 s
    windows sit close to or under the budget, while the same configuration at
    60 s measures 607.6 ms and 1027.6 ms. Short windows flatter this workload.
  - **1 stream / decode mode (309.9 ms)** — this met the budget *because*
    **69.3% of decoded frames were dropped** (883/1274), so far fewer frames were
    scored. p95 covers scored frames only; a low p95 bought with dropped frames
    is not spare capacity.
- p95 also varies ~5× between runs at the same setting (4 streams: 831.2 ms vs
  1772.6 ms). Quote a range, never a single number.

### Honest capacity statement (compute mode, CPU-only)

What the data supports is throughput, not budget compliance:

| Streams | FPS/stream (mean) | p95 latency |
|---|---|---|
| 1 | 3.83 – 4.31 | 607.6 – 652.8 ms, **breach** |
| 2 | 1.89 – 4.25 | 320.3 – 1027.6 ms, **breach** (the 320.3 is a 15 s window) |
| 4 | 1.03 – 1.34 | 831.2 – 1772.6 ms, **breach** |

The real constraint is **inference, not contention**: a single stream already
saturates ~5 of 8 cores, so adding streams divides FPS roughly proportionally
while p95 degrades monotonically. The p95 < 500 ms budget is **not met at any
stream count on this host** in compute mode.

## Track stability (60 s compute soak, 4 streams)

| Item | Value | Source |
|---|---|---|
| Distinct tracks | 20 across 4 streams (5 each) | `total_distinct_tracks` |
| ID switches | **0** | `id_switches` (identity registry counter) |
| Exit/re-entry events | 0 in this window (looping video) | `reentry_rebinds` |
| Alerts | 104 in 36 s (looping clip re-triggers; **not** a field rate) | `alerts_total` |

## FFmpeg kill/reconnect drill (real subprocess, real sockets)

| Item | Value | Source |
|---|---|---|
| Stage 1 streaming | 10 frames @ 640×480, clean spawn args | `ffmpeg_reconnect_drill_result.json → 1_streaming` |
| Client killed mid-stream → detected | **2.26 s** → state `reconnecting` | same, `2_kill.detection_latency_s` |
| Recovery to streaming with fresh frames | yes (10 → 26+ frames) | same, `3_recovery` |
| Camera-socket-drop detection latency | **NOT MEASURED** (ffmpeg drains its buffer for minutes; deterministic client-kill used instead) | drill docstring |

The drill also caught and now guards a real bug: FFmpeg 9 rejects a pre-input
`-rtsp_transport` for non-RTSP sources, which made `RTSPStream._start_ffmpeg`
die instantly for file/`tcp://` URLs. Fixed in
`yolo_cloud/rtsp_manager.py::_input_url_options` (scheme-conditional options).

## NOT MEASURED (do not quote)

| Item | Why |
|---|---|
| GPU memory per stream | no GPU on this host |
| 4 h × 4 RTSP soak | only short compute-mode soaks run; the 4 h run is a site task |
| RTSP DESCRIBE/SETUP/PLAY + transport negotiation | ffmpeg 9 on Windows cannot bind an RTSP listen server; the drill uses a TCP MPEG-TS source (same reader path, no RTSP control channel) |
| UDP RTSP transport | untested; `RTSP_TRANSPORT=tcp` is the configured default |
| Accuracy / detection quality | out of scope by task constraint |

## Sizing recommendation (bounded by measurements above)

- CPU-only box (8 cores): the p95 < 500 ms budget is **not met at any stream
  count** in compute mode — measured 607.6 ms (1 stream) through 1772.6 ms
  (4 streams). Do not promise "1–2 streams within budget"; it is not what the
  runs say. What is supported: **~4 FPS/stream at 1 stream, degrading to ~1
  FPS/stream at 4**, with CPU the binding constraint (230–590% of 8 cores at
  a single stream).
- Dropping frames is *not* a way to claim the budget: the one within-budget
  decode run achieved it while discarding 69.3% of decoded frames.
- GPU box (target config): **NOT MEASURED** — provision for ≥ 8 GB VRAM as a
  placeholder and re-run `scripts/soak_cloud.py` + the drill on the actual
  hardware before any capacity statement.
- All rows above are short runs (15–120 s). The 4 h × 4-stream run is a site
  task and remains **NOT MEASURED**.

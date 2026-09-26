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
| `trl6-rtsp-main` (1800 s) | 4 | spec-load | **4407.8 ms** | BREACH | 0.37 | `soak_20260926T021815Z_summary.json` |
| `trl6-rtsp-identity` (900 s) | 4 | spec-load | **4034.7 ms** | BREACH | 0.39 | `soak_20260926T025639Z_summary.json` |

The two RTSP rows are real ffmpeg-over-TCP decode from four distinct
sources with the publishers (4× ffmpeg + MediaMTX) on this same 8-CPU box —
a **worst case for same-host rigs**; a field box only runs the reader.
Full demo context: `docs/TRL6_EVIDENCE.md`, section *Relevant-environment
demo*.

### Is "1–2 streams within budget, 4 breach" supported?

**Not at the default configuration, and only at one optimized configuration
with a stream cap of 2 — the spec's own 4-stream load point breaches either
way.** The morning batch (defaults: yolov8s-pose @ imgsz 640) does not support
the blanket sentence:

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

**Addendum — later same-day 60 s runs (see matrix below):** the default
configuration *straddles* the budget instead of cleanly breaching it: 478.5 ms
(`matrix-s640`) and 529.7 ms (`moov-fix`) at 1 stream, against the morning's
607.6/652.8 ms. So 1 stream at defaults is a **478–653 ms range over same-day
60 s runs** — not a verdict in either direction. The only configuration that
reliably held the budget in 60 s runs is **yolov8n-pose @ imgsz 320: 152.1 ms
at 1 stream, 114.5 ms at 2 streams — then 946.0 ms at 3 and 896.8 ms at 4**.
What is true at every configuration tested: **the 4-stream spec load point
breaches on this host** (1772.6 ms at defaults, 896.8 ms at the best
configuration measured).

### Honest capacity statement (compute mode, CPU-only)

What the data supports is throughput, not budget compliance:

| Streams | FPS/stream (mean) | p95 latency |
|---|---|---|
| 1 | 3.83 – 4.31 | 607.6 – 652.8 ms, **breach** |
| 2 | 1.89 – 4.25 | 320.3 – 1027.6 ms, **breach** (the 320.3 is a 15 s window) |
| 4 | 1.03 – 1.34 | 831.2 – 1772.6 ms, **breach** |

The real constraint is **inference, not contention**: a single stream already
saturates ~5 of 8 cores, so adding streams divides FPS roughly proportionally
while p95 degrades monotonically. At the **default configuration** the p95
< 500 ms budget is **not met at any stream count** in compute mode; at the
**optimized configuration** (yolov8n-pose @ 320) it is met at 1–2 streams and
fails at 3 — see the matrix below.

## Optimization matrix — model × imgsz (60 s each, 1 stream)

Added after the runs above. Each row is its own 60 s process, compute mode,
builtin-iou tracker, defaults everywhere except the named variables. Knob:
`YOLO_IMGSZ` env (`yolo_cloud/config.py`, **default 640 — behavior unchanged
unless set**), threaded into the predict call in `yolo_cloud/pose_engine.py`.
CPU and FPS exclude the first 4 s of warm-up (sampled from the run's jsonl at
t ≥ 4 s); p95 comes from the bounded latency buffer and therefore INCLUDES
warm-up frames, which is the conservative direction.

| Model | imgsz | p95 (ms) | vs 500 ms | over-budget frames | FPS/stream | CPU mean (t≥4 s) | RSS max | inference p95 | clips saved / truncated | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| yolov8s-pose | 640 (default) | **478.5** | within | 8 / 354 | 6.1 | 599.0% | 701 MB | 139.2 ms | 49 / 0 | `soak_20260925T164714Z_summary.json` |
| yolov8s-pose | 416 | **414.8** | within | 3 / 550 | 9.5 | 590.0% | 679 MB | 98.4 ms | 50 / 0 | `soak_20260925T164819Z_summary.json` |
| yolov8s-pose | 320 | **399.2** | within | 1 / 636 | 11.0 | 574.6% | 682 MB | 81.2 ms | 52 / 0 | `soak_20260925T164932Z_summary.json` |
| yolov8n-pose | 640 | **465.8** | within | 10 / 475 | 8.2 | 466.9% | 588 MB | 120.2 ms | 56 / 0 | `soak_20260925T165037Z_summary.json` |
| yolov8n-pose | 416 | **408.3** | within | 1 / 736 | 12.7 | 541.8% | 577 MB | 65.9 ms | 54 / 0 | `soak_20260925T165148Z_summary.json` |
| yolov8n-pose | 320 | **152.1** | within | 4 / 928 | 16.0 | 531.6% | 567 MB | 55.5 ms | 46 / 0 | `soak_20260925T165253Z_summary.json` |

All six cells sit within the budget at 1 stream — but the default cell sits
21 ms under it with 8 over-budget frames, i.e. at the boundary (and a second
same-day default run measured 529.7 ms, breach). Treat defaults as "around
the budget", never "within". Every run above wrote clips with
**`clips.truncated_total = 0`**.

**Accuracy is NOT measured here.** These rows are latency/throughput only.
`yolov8n-pose` (3.30 M params, measured) detection quality was not evaluated
in any run; the Safe Claims 87.6% figure belongs to a different engine and is
untouched by this matrix.

### Stream-count probes at the best configuration (yolov8n-pose @ 320, 60 s)

| Streams | Class | p95 worst stream | vs 500 ms | FPS/stream | Source |
|---|---|---|---|---|---|
| 1 | capacity-probe | **152.1 ms** | within | 16.0 | `soak_20260925T165253Z_summary.json` |
| 2 | capacity-probe | **114.5 ms** | within | 11.28 | `soak_20260925T165513Z_summary.json` |
| 3 | capacity-probe | **946.0 ms** | BREACH | 4.0 | `soak_20260925T165739Z_summary.json` |
| 4 | spec-load | **896.8 ms** | BREACH | 2.94 | `soak_20260925T165618Z_summary.json` |

**Honest max streams at p95 < 500 ms on this 8-CPU host: 2**, and only with
`YOLO_MODEL=yolov8n-pose.pt YOLO_IMGSZ=320`. The cliff between 2 and 3
streams is sharp (114.5 → 946.0 ms), so do not quote "2–3". At defaults even
1 stream is not a reliable pass (478–653 ms range). The 4-stream spec load
point fails under every configuration measured, including this one — the
spec's 4 feeds × 8 workers × 10 FPS still needs the GPU box (NOT MEASURED).

### Frame-skip probe — score every 2nd frame (4 streams, n/320, 60 s)

`YOLO_SCORE_EVERY=2` (knob added in `yolo_cloud/config.py`, default 1 = unchanged;
skipped frames are pulled, never scored/clipped/counted in latency) vs a
same-session `every=1` control, compute mode:

| Run label | score_every | p95 worst stream | vs 500 ms | over-budget | FPS/stream | CPU mean | Source |
|---|---|---|---|---|---|---|---|
| `frame-skip-4stream-n320-every2` | 2 | **1440.2 ms** | BREACH | 147/275 | 1.14 | 413.2% | `soak_20260926T015529Z_summary.json` |
| `control-4stream-n320-every1` | 1 | **1420.6 ms** | BREACH | 164/326 | 1.36 | 517.1% | `soak_20260926T015729Z_summary.json` |

**Frame-skip does not buy the budget** — the runs are 1.4% apart; the pipeline is
score-gated (it already drops frames at the single-slot buffer when inference falls
behind, so skipping pulls creates no capacity), and every frame-count window (10-frame
dwell, task window, tracker hits) would take 2× wall time at half the scoring rate,
doubling time-to-alert. Both runs also sit ~1.6× above the previous day's 896.8 ms
same-config run — further evidence of the run-to-run variance noted above. Full
verdict and the 4-camera options: `docs/DEPLOYMENT_TOPOLOGY.md`.

## Where the CPU goes (one-time profile)

`cProfile` over a 30 s default-config run (`outputs/soak/profile_s640.prof`,
run `profile-s640`). Shares below are of the sum of the listed stages;
per-function totals are consistent with the frame counts (140 frames, 349
tracked poses).

| Stage | Profiled time | Share | Evidence in the profile |
|---|---|---|---|
| YOLO inference (predict tree, incl. torch) | 14.55 s cum; `torch.conv2d` alone 11.62 s | ~59% | `ultralytics/tasks.py predict`, 141 calls |
| Risk/task ML + per-track processing | 4.86 s (`_process_tracked_pose`); of which sklearn HGB predict 3.76 s over 698 model calls | ~20% | `gradient_boosting.py _predict_iterations` |
| Pre-alert clip encode | 4.85 s — `VideoWriter.write` 3.10 s + buffer `imdecode` 1.26 s + JPEG capture 0.21 s + moov check 0.19 s | ~20% | `_save_clip`, 21 clips in 30 s |
| Frame decode (compute mode = local file read) | 0.48 s | ~2% | `VideoFeeder.frame`, 141 calls |
| Tracker + glue + persons | < 0.1 s | <1% | `_SimpleTracker.update`, `build_persons` |

**Reading:** inference dominates, but the clip writer is a real second citizen
because this footage fires an alert every ~1.4 s (21 clips / 30 s) — each HIGH
alert writes up to 100 frames *inside* the frame latency window. Caveats:
cProfile adds overhead, so this run's own p95 (501.1 ms) is a profiling
artifact and NOT a performance number (use the matrix for those); RTSP-mode
decode runs in the ffmpeg subprocess and is **not** in this profile — the 2%
row is compute mode reading a local file.

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

## UDP RTSP transport probe (measured 2026-09-26)

One 120 s run with the non-default `RTSP_TRANSPORT=udp` against the 4-cam
rig (label `trl6-rtsp-udp`, `outputs/soak/soak_20260926T034839Z_summary.json`):

| Item | Value | Source |
|---|---|---|
| Transport actually used | **UDP** — the 4 production ingest ffmpegs ran `-rtsp_transport udp -f rawvideo` (rig publish side stays TCP) | `outputs/tri6_demo/ffmpeg_cmdlines.txt` |
| Frames | 4340 decoded across 4 streams; per-stream fps > 0 in 54/60 samples (run mean 0.74, max 1.5) | `frame_drops`, jsonl samples |
| Alerts / clips | 132 alerts; 71 clips saved, **0 truncated** | `alerts_total`, `clips` |
| p95 worst stream | **1966.0 ms — BREACH** (354/354 over the 500 ms budget) | `latency.p95_worst_stream_ms` |
| Drop rate | 91.8% of decoded frames (single-slot buffer, 4-stream same-box load) | `frame_drops.overall_drop_rate` |
| CPU / RSS | mean 540.0% / max 703.2%; RSS mean 873, max 1126.7 MB | `cpu_pct`, `rss_mb` |

UDP **works** (frames, alerts and clips all flow through the production
reader) but was not benchmarked against TCP under matched load — no
transport performance claim either way; `RTSP_TRANSPORT=tcp` remains the
default.

## 4-hour soak (measured 2026-09-26)

Label `trl6-rtsp-4h`, `outputs/soak/soak_20260926T035744Z_summary.json` —
the full 4 h × 4 RTSP run executed on this box (14 404.4 s, graceful stop):

| Item | Value | Source |
|---|---|---|
| Completion | **full 4 h 00 m**, clean shutdown, summary written | `duration_s` |
| Clips | **5021 saved / 0 truncated** — moov guard held for 4 h | `clips` |
| RSS | mean 771.8 MB, max 1287.4 MB; first-10-min mean 1262.9 → last-10-min 945.2 MB — **no leak** | `rss_mb` |
| CPU | mean 470.0%, max 737.5% | `cpu_pct` |
| p95 worst stream | **5024.4 ms — BREACH** (19 951/25 005 scored frames over budget) | `latency` |
| FPS/stream | mean 0.43; drop 94.6% of 462 526 decoded frames | `frame_drops` |
| Identity | 687 distinct tracks, **0** ID switches, 1282 wildcard binds (all `bound=True`) | `total_distinct_tracks`, `identity_binds_this_run` |
| Alerts | 1000 (**query cap reached**), 664 with `worker_id` | `alerts_total` |

Duration stability is demonstrated; latency still breaches the 500 ms
budget on this same-box worst case (same caveat as the runs above).

## NOT MEASURED (do not quote)

| Item | Why |
|---|---|
| GPU memory per stream | no GPU on this host |
| 4 h × 4 RTSP soak off-host / on GPU | the 4 h run **is** measured on this box (4-hour soak section above: full 14 404 s, 0 truncated, no RSS leak); a 4 h run with feeds from separate hosts and/or on a GPU was not |
| RTSP server built on ffmpeg alone | ffmpeg 9 on Windows cannot bind an RTSP listen server — the rig publishes through **MediaMTX** instead; client-side DESCRIBE/SETUP/PLAY over TCP **is** measured (30-min 4-cam demo run) |
| UDP vs TCP latency (load-matched A/B) | one 120 s UDP probe exists (measured above: works, p95 1966.0 ms BREACH) but runs were not load/duration-matched, so no comparative transport number |
| Accuracy / detection quality | out of scope by task constraint |

## Sizing recommendation (bounded by measurements above)

- CPU-only box (8 cores), **default config** (yolov8s-pose @ 640): p95 < 500 ms
  is **not met at any stream count** — 478–653 ms at 1 stream over same-day
  60 s runs (range, not verdict), through 1772.6 ms at 4. What is supported at
  defaults: **~4–6 FPS/stream at 1 stream, degrading to ~1 FPS/stream at 4**,
  with CPU the binding constraint (230–590% of 8 cores at a single stream).
- CPU-only box, **optimized config** (`YOLO_MODEL=yolov8n-pose.pt
  YOLO_IMGSZ=320`): **max 2 streams at p95 < 500 ms** (114.5 ms measured),
  16.0 FPS/stream at 1 and 11.28 at 2 — the 10 FPS/stream target is met per
  stream at 1–2 streams in compute mode. 3 streams fails sharply (946.0 ms).
  Latency/throughput only — no accuracy claim for yolov8n-pose.
- Dropping frames is *not* a way to claim the budget: the one within-budget
  decode run achieved it while discarding 69.3% of decoded frames.
- GPU box (target config): **NOT MEASURED** — provision for ≥ 8 GB VRAM as a
  placeholder and re-run `scripts/soak_cloud.py` + the drill on the actual
  hardware before any capacity statement.
- All compute-mode rows above are short runs (15–120 s); the RTSP demo runs
  are 30 min and 15 min. The 4 h × 4-stream run is a site task and remains
  **NOT MEASURED**.

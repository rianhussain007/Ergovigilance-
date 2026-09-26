# Deployment Topology — measured stream caps & 4-camera options

Every performance number in this document is **measured on this machine** (8 logical
CPUs, no GPU — see the machine table in `docs/SIZING_SOAK_CLOUD.md`) and sourced to a
JSON file in `outputs/soak/`. GPU rows are **spec-only requirements, never measured
here**. Rows that could not be measured are marked **NOT MEASURED** and must not be
quoted as facts. **No risk-accuracy claim is made for any profile** — what the accuracy
evaluation did and did not show is in `docs/TRL6_EVIDENCE.md`.

## Machine under test

| Item | Value | Source |
|---|---|---|
| CPU | 8 logical cores | `machine.cpus` in soak summaries |
| RAM | 12.7 GB | `machine.ram_gb` |
| GPU | **none present** (`torch.cuda.is_available() == False`) | `machine.gpu_measured: false` |
| OS | Windows (Git Bash toolchain) | — |

All cap numbers below are **compute mode** (local file as frame source, the same mode
the whole measurement matrix in `docs/SIZING_SOAK_CLOUD.md` uses). RTSP mode adds an
FFmpeg decode subprocess whose latency cost on this host is **NOT MEASURED**.

## Per-box stream caps (measured)

### Capacity profile: `YOLO_MODEL=yolov8n-pose.pt YOLO_IMGSZ=320`

| Streams | Class | p95 worst stream | vs 500 ms | FPS/stream | Source |
|---|---|---|---|---|---|
| 1 | capacity-probe | **152.1 ms** | within | 16.0 | `outputs/soak/soak_20260925T165253Z_summary.json` |
| 2 | capacity-probe | **114.5 ms** | within | 11.28 | `outputs/soak/soak_20260925T165513Z_summary.json` |
| 3 | capacity-probe | **946.0 ms** | BREACH | 4.0 | `outputs/soak/soak_20260925T165739Z_summary.json` |
| 4 | spec-load | **896.8 ms** | BREACH | 2.94 | `outputs/soak/soak_20260925T165618Z_summary.json` |

**Honest per-box cap at p95 < 500 ms on this host: 2 streams**, and only with the
capacity profile. The 2→3 cliff is sharp (114.5 → 946.0 ms) — do not quote “2–3”.
At 1–2 streams the 10 FPS/stream target is met in compute mode (16.0 / 11.28).

### Default profile: `yolov8s-pose @ 640` (repo default)

| Observation | Source |
|---|---|
| Every run of ≥60 s **breaches** at 1 stream (607.6 ms, 652.8 ms); same-day later runs straddle (478.5–529.7 ms) | `docs/SIZING_SOAK_CLOUD.md` capacity table + matrix |
| 2 streams ≥60 s: **1027.6 ms** BREACH | `soak_20260925T100119Z_summary.json` |
| 4 streams: **831.2–1772.6 ms** BREACH (range across runs — quote a range, never one number) | `soak_20260925T081146Z` / `soak_20260925T083105Z` |

So the default profile supports **no reliable stream cap at this budget** on one box.
It stays the default for the *product* (it detects 117/119 labelled frames vs 101/119
for n/320 — detection completeness measured in `scripts/eval_cloud_accuracy.py`, N=119;
**neither profile discriminates risk levels, so this is not an accuracy claim**), while
**capacity-bound deployments switch to the capacity profile** and take the detection
trade-off knowingly.

Run-to-run p95 varies materially at identical settings (documented ~5× in
`docs/SIZING_SOAK_CLOUD.md`; the two same-config 4-stream n/320 runs below differ
1.6× across days) — always quote ranges and cite the summary file.

## 4-stream frame-skip probe (2026-09-26): does scoring every 2nd frame buy the budget?

**No.** `YOLO_SCORE_EVERY=2` (new knob, `yolo_cloud/config.py`, default `1` =
unchanged behavior; skipped frames are pulled, never scored, clipped, or counted in
latency) was probed at the spec load point with a **same-session control**, capacity
profile, 60 s each, compute mode:

| Run | `score_every` | p95 worst stream | vs 500 ms | over-budget frames | FPS/stream | CPU mean | Source |
|---|---|---|---|---|---|---|---|
| `frame-skip-4stream-n320-every2` | 2 | **1440.2 ms** | BREACH | 147/275 | 1.14 | 413.2% | `outputs/soak/soak_20260926T015529Z_summary.json` |
| `control-4stream-n320-every1` | 1 | **1420.6 ms** | BREACH | 164/326 | 1.36 | 517.1% | `outputs/soak/soak_20260926T015729Z_summary.json` |

Both summaries carry a `frame_skip` block proving the knob’s setting (274 skipped
frames in the probe run; 0 in the control); 0 truncated clips in both.

**Reading:**
- The two runs are 1.4% apart at p95 — **frame-skip changes nothing material at
  4 streams**. The binding constraint is inference CPU contention between the four
  scoring threads, and the loop is *score-gated*: it already consumes frames as fast
  as inference allows (frames it cannot score are dropped at the single-slot buffer
  anyway), so skipping pulls does not create capacity. This is the same caveat the
  sizing doc records for the one decode run that met the budget while discarding
  69.3% of frames: **a low p95 bought with fewer scored frames is not spare capacity.**
- Both runs (1420–1440 ms) are ~1.6× worse than yesterday’s same-config 896.8 ms —
  consistent with the documented run-to-run variance, and another reason to quote
  ranges with sources.
- **Dwell-window implication (paid even if latency had improved):** windows counted
  in *scored frames* — the 10-frame level dwell, the 10-frame task-smoothing window,
  the 3-hit tracker confirm — stretch in wall time as the scoring rate drops. At half
  the scoring rate (the knob’s intent: a 10 FPS feed scored at 5 FPS), a 10-frame
  dwell that alerts after 1 s takes **2 s → time-to-alert doubles**. Alert cooldown
  itself is wall-clock (`ALERT_COOLDOWN / INFERENCE_FPS` seconds) and does not
  double, but nothing downstream of a halved scoring rate gets faster.

**Verdict: frame-skip is not a 4-camera strategy on this box** — it neither buys the
latency budget nor is free: it costs alert latency proportional to N.

## Options for the spec’s 4 cameras

| # | Option | Status | What it rests on |
|---|---|---|---|
| 1 | **Two CPU boxes × 2 streams each** (capacity profile) | **Recommended — measured** | 2 streams at p95 114.5 ms, 11.28 FPS/stream (compute mode) per box |
| 2 | One GPU box | **SPEC-ONLY — NOT MEASURED** | Provision for **≥ 8 GB VRAM as a placeholder only**; no FPS, latency, or stream-count number exists for it. Re-run `scripts/soak_cloud.py` + the FFmpeg reconnect drill on the actual hardware before any capacity statement. |
| 3 | One CPU box × 4 streams with frame-skip | **Measured, rejected** | Probe above: 1440.2 ms (skip) vs 1420.6 ms (control), both BREACH; plus the doubled time-to-alert |

Notes for option 1: each box runs single-worker (`STRICT_SINGLE_WORKER=true` — camera
state is in-process singleton; a second worker would open a second FFmpeg per camera
and double-process every frame). `EXPECTED_CAMERAS` sizes the box, it does not enable
clustering. Identity binds/alerts are per-box state — two boxes are two independent
tenants-of-one unless a shared Postgres is configured (NOT MEASURED as a topology).

## Recommended profile (compose / env example)

Capacity-bound CPU box, the only profile with a measured p95 < 500 ms pass:

```yaml
# docker-compose.yml — recommended CPU profile (measured: 2 streams, p95 114.5 ms)
services:
  yolo-cloud:
    build: .
    environment:
      YOLO_MODEL: yolov8n-pose.pt   # capacity profile (measured matrix)
      YOLO_IMGSZ: "320"             # measured: 1 str 152.1 ms / 2 str 114.5 ms
      YOLO_SCORE_EVERY: "1"         # frame-skip measured NOT to help — keep 1
      EXPECTED_CAMERAS: "2"         # = the measured per-box cap
      STRICT_SINGLE_WORKER: "true"  # never >1 worker: in-process camera state
      RTSP_TRANSPORT: "tcp"
      INFERENCE_FPS: "10"
    ports:
      - "8100:8100"
    # GPU box (SPEC-ONLY, never measured on the sizing host):
    # deploy:
    #   resources:
    #     reservations:
    #       devices: [driver: nvidia, count: all, capabilities: [gpu]]
```

Equivalent `.env` form: `YOLO_MODEL=yolov8n-pose.pt`, `YOLO_IMGSZ=320`,
`YOLO_SCORE_EVERY=1`, `EXPECTED_CAMERAS=2`, `STRICT_SINGLE_WORKER=true`.
Where latency budget is not the binding requirement, leave the product defaults
(`yolov8s-pose @ 640`) — they are unchanged unless you set the env knobs.

## NOT MEASURED / not claimed (do not quote)

| Item | Why |
|---|---|
| Any GPU number (FPS, VRAM, stream cap) | no GPU on the measuring host; row above is a spec-only placeholder |
| 4 h × 4-stream continuous run | only 60–120 s runs exist; the 4 h run is a site task |
| RTSP-mode latency caps (decode subprocess in the path) | matrix is compute mode; the RTSP drill measured reconnect behaviour, not p95 |
| Risk accuracy of any profile (s/640 or n/320) | `scripts/eval_cloud_accuracy.py`: neither profile discriminates risk levels on the 119 human labels — **no accuracy claim is made**; Safe Claims 87.6% belongs to the backend engine and is untouched |
| 8 workers/feed, ByteTrack counters | single-worker footage only; ByteTrack unavailable in this build (`lapx` missing) |
| Two-box identity federation, shared Postgres topology | not built or run |

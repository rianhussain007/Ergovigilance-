# ErgoVigilance — Reconciled One-Pager (REVIEW BEFORE SENDING)

> Status: reconciled 2026-09-24 against `docs/DEEP_AUDIT_REPORT.md` Safe Claims Sheet + `ui_posture/src/pages/PricingPage.tsx` canonical pricing. Contact email + reviewer name are placeholders — fill before sending.

## The problem

Musculoskeletal injuries surface as compensation claims, weeks after the damage. Manual RULA/REBA spot audits are point-in-time, observer-dependent, and can't compare stations or shifts. You get a paper score, not a trend.

## The solution — one sentence

**ErgoVigilance watches a workstation from an ordinary camera, scores posture risk continuously, flags sustained risky motion, and leaves you with evidence-backed reports — video never leaves your building by default.**

## What it does (working today)

* Live risk gauge (LOW / MEDIUM / HIGH) + skeleton overlay from a USB webcam or video upload
* 17 biomechanical features (neck, trunk, shoulders, elbows, head posture, stance, wrists) → RULA/REBA-informed rules + task/fatigue/exposure context + temporal smoothing
* Sustained-risk alerts with acknowledge/resolve lifecycle + plain-language guidance
* Session history, video replay with skeleton, trend charts, per-session PDF/CSV/JSON + evidence package
* Worker records with consent-first identity (anonymous / badge-QR / face with signed consent), role-based access (Operator / Supervisor / Safety Mgr / Admin), audit trail, 30-day retention
* Cloud tier (YOLOv8-pose + RTSP CCTV) available for multi-camera sites — same dashboard and reports

## What it does NOT do

* Not a medical device. Screening and decision-support only — does not diagnose, does not replace a safety officer or ergonomist.
* No video leaves the plant in on-prem mode. No cloud account required.
* No identification without consent. Anonymous and badge-only modes work identically.

## Accuracy — stated exactly as measured

* **87.6% agreement with human assessors on 500 labeled frames** (`results/ground_truth_evaluation.json`). LOW precision 100% / recall 57% (tends to over-warn MEDIUM); MEDIUM precision 85% / recall 100%. **No HIGH validated. Single worker, single room.** Treat as screening sensitivity, not universal accuracy.
* Other figures in older docs (94.1% / 97.6% YOLO holdout on rule-derived labels; 88.6% / 86.4% F1 research track; 76.9% REBA holdout) are **not product accuracy** and are not quoted here.
* Ergonomic thresholds: RULA/REBA-informed heuristics. Threshold review: **[Pending / Reviewed by ___ , ___credential___]**.

## Pricing (canonical — matches Pricing page + Stripe)

| Tier | Price | Cameras | Notes |
|---|---|---|---|
| On-Premise Starter | Free (self-hosted) | 4 USB/webcam | Laptop install, offline |
| Cloud Professional | $299/mo per 10 cams (up to 20); $239/mo annual | 20 RTSP | Zero on-site app, central dashboard |
| Enterprise | Custom | 50+, multi-site | GPU cluster, ERP/CMMS, SLA |

First-10 Indian SMB lane (decision pending): quote INR equivalent explicitly if buyer budgets in INR — do not mix USD/INR in one quote. ROI figures ($42k/injury, 40% reduction) are industry benchmarks, not measured results.

## The pilot offer

**$0 for 2 weeks. One station, 1–2 cameras, ~30-min laptop install.** We remove it ourselves if you see no value. Success = risk-score trend + supervisor feedback (two weeks won't move injury rates). Consent flow + signage + "screening aid, not medical device" in the agreement. Day-one smoke test: live feed → deliberate slouch → alert → report + clip.

---

Contact: Rian Hussain · **[contact email — FILL BEFORE SENDING]** · [phone] — ErgoVigilance · Industrial ergonomics, automated.

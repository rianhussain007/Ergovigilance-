# ErgoVigilance — Operations Runbook

Companion to `README.md`. Covers the operational concerns that matter once the
stack is deployed outside the local dev machine: what to back up, how to serve
TLS, what to monitor, and how to scale.

## 1. Production prerequisites (Tier 0 checklist)

Before any non-local deployment, verify every row of `backend_api/.env.production.example`:

| Check | Command / value |
|---|---|
| Debug off | `DEBUG=false` |
| Strong JWT secret | `AUTH_JWT_SECRET` = `python -c "import secrets; print(secrets.token_urlsafe(48))"` — the API **refuses to start** with a weak/known secret in non-debug mode |
| Live repositories | `USE_MOCK_REPOSITORY=false` (fails closed with 503 if the monitoring service is unavailable) |
| CORS locked | `CORS_ORIGINS` = the real UI origin(s), never `*` |
| Ollama reachable | `ollama pull qwen2.5:1.5b` and `ollama pull nomic-embed-text` on the host (or point `OLLAMA_HOST` at a managed endpoint) |
| Pose model | `POSE_MODEL_PATH` — lite (default, ~15-20 FPS) vs full/heavy (cluttered industrial scenes, ~2-4× slower) |

The startup log prints a loud warning in debug mode; production config should
never see it.

## 2. Backup strategy

Four things hold state. Back up all of them on the same schedule:

| Data | Location | Notes |
|---|---|---|
| Auth DB (users, workers, alerts, audit, pilot requests) | `AUTH_DB_PATH` (default `backend_api/local_auth.db`; `/data/local_auth.db` in containers) | The only DB with credentials — highest priority |
| Video-analysis job registry | `video_analysis_jobs.db` next to the auth DB | SQLite; completed job results survive restarts |
| Session summaries | `outputs/sessions/` (JSON per session) | Evidence trail — retain per policy (default 30 days via retention) |
| Recordings | `recordings/` | Large; usually NOT backed up (retention deletes after 30 days) — keep only for audit/legal if required |
| AI knowledge corpus | `knowledge/` (source of truth, in git) | Not a runtime asset |

**Recommended schedule:**

```bash
# nightly, e.g. cron / Task Scheduler
sqlite3 local_auth.db ".backup '/backups/ergo-auth-$(date +%F).db'"
sqlite3 video_analysis_jobs.db ".backup '/backups/ergo-jobs-$(date +%F).db'"
tar -czf "/backups/sessions-$(date +%F).tar.gz" outputs/sessions
# retention: keep 14 daily, 8 weekly, 12 monthly (example)
```

SQLite is safe to back up with `.backup` while the app is running (it uses the
online backup API); copying the file directly can produce a torn snapshot.
Test restore at least quarterly: `sqlite3 restored.db 'PRAGMA integrity_check;'`
plus one login + one session report.

**Restore:** stop the service, replace the DB files, restart. The app runs
migrations idempotently (`PRAGMA user_version`) so an older schema upgrades on
first boot.

## 3. TLS termination

The bundled nginx frontend terminates TLS. After mounting certs:

```yaml
# docker-compose.yml (frontend service)
ports:
  - "443:443"
volumes:
  - ./certs/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
  - ./certs/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
  - ./ui_posture/nginx.tls.conf.example:/etc/nginx/conf.d/default.conf:ro
```

- Generate with `certbot certonly --standalone -d app.yourcompany.com` or your
  provider's DNS challenge; renew automatically (certbot timer).
- **Never publish `:8000` publicly** — the API is loopback-only and trusts the
  frontend proxy (`TRUST_PROXY_HEADERS=true`). Only 443 (and 80 → 443 redirect)
  are exposed.
- The backend binds `127.0.0.1:8000` in compose; the frontend reaches it over
  the internal Docker network.

## 4. Observability

Operational endpoints are auth-free and root-level (probes need no token):

| Endpoint | Purpose |
|---|---|
| `/healthz` | Liveness — process up (used by Docker healthcheck) |
| `/readyz` | Readiness — 503 until the app can serve real requests |
| `/metrics` | Prometheus text exposition — request counters, active sessions, uptime |
| `/health` | Human-readable status incl. app/version/uptime |

**Dashboards/alerting:** scrape `/metrics` with Prometheus (or a managed
Prometheus — e.g. `prometheus.yml` job targeting the backend container on the
internal network) and alert on:

- `up == 0` (service down) — 5m
- request error rate > 5% over 5m (`rate(http_requests_total{status=~"5.."}[5m])`)
- p99 latency > 2s over 10m
- `active_sessions > 0` unexpectedly outside working hours (or as a live
  monitoring heartbeat)
- disk usage > 85% (recordings grow fast; the 20 GB cap evicts oldest first,
  but alert before eviction thrashes)

## 5. Scaling & capacity

- The live pipeline is **single-camera by design**: one PoseEngine per process
  (lite model ≈ 15-20 FPS on a laptop CPU, ~1 core). Multi-camera production
  = **one backend container per camera** (each owns its own session/engine),
  fronted by the nginx load balancer keyed by camera.
- `uvicorn` runs single-worker by default. For higher HTTP concurrency under
  load, run multiple workers (`--workers N`) — but note each worker is its own
  process, so the in-process session/feed state is per-worker. Keep `--workers 1`
  unless sessions are short-lived and clients tolerate a re-login.
- Uploaded video analysis (`POST /video/analyze`) runs in a background daemon
  thread per job with a 200 MB cap and a 30-minute job TTL. Under sustained
  load, prefer a separate worker (or a queue worker) so long analyses don't
  compete with live inference. Jobs persist to SQLite and survive restarts.
- Tune `EMBED_DIM`/corpus load if the AI Assistant startup time (12s corpus
  embed in dev) is a concern — it loads in the background and never blocks startup.

## 6. Smoke test after deploy

```bash
venv/Scripts/python.exe scripts/load_test.py --base https://app.yourcompany.com \
  --workers 8 --duration 15 --per-second 20 --endpoint dashboard
```

Expect p95 < 1 s and 0 errors on the seeded admin account. Then do one manual
login → start session → watch a live feed tile → stop session → export a
session report (PDF exercises Playwright/Chromium — the only external browser
dependency).

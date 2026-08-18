# Worker Identity Engine — consent-first identification

**Audience:** safety managers, plant managers, HR/works councils, unions.
**Purpose:** explain *how* ErgoVigilance identifies workers, what data it stores, and how consent is enforced — so face recognition is a feature your factory opts into, not a surprise.

---

## The three identity modes (per worker)

| Mode | How the worker is identified | Face data used? | Best for |
|---|---|---|---|
| **Face camera** | Live camera face recognition (SFace embedding match against an enrolled photo) | Yes — 128-dim numeric embedding, no raw photo retained | Factories with signed consent; fastest, zero worker action |
| **Badge / QR** | A printed QR badge scanned at the start of a shift (or any badge code) | No | Works councils / unions that want explicit opt-in; workers who refuse cameras; guests |
| **No identification** | Sessions stay anonymous (worker = "Person 1/2/3") | No | Anything else — posture monitoring works fully without identity |

Every worker record carries **identity_mode** and **consent_status** (`granted` / `pending` / `denied`). A worker whose consent is `denied` — or who is in badge/off mode — is **immediately excluded from face matching at runtime**. The code enforces this in the matcher itself, not just in the UI:

```python
# backend_api/app/services/worker_faces.py
WHERE w.identity_mode = 'face' AND w.consent_status != 'denied'
```

## What is stored, what is not

| Stored | Not stored |
|---|---|
| A 128-dim numeric face embedding (~2 KB) per enrolled worker | Raw enrollment photos (transient, processed in memory then discarded) |
| Badge/QR identifier (worker-chosen or HR-assigned) | Any footage linked to identity beyond the session record you choose to keep |
| Worker name / employee ID / department / shift (HR-provided) | Cloud copies — everything lives in the local SQLite store on your machine |

## The consent workflow (recommended)

1. **HR briefing** — one page (this doc) handed to the works council / union rep: what the camera does, what it never does (no cloud, no raw photos, no tracking outside the monitored station).
2. **Per-worker opt-in** — supervisor sets each worker's identity mode and consent in **Workers → Identity & Consent**.
3. **Denied is hard** — consent `denied` removes the worker from face matching immediately; their sessions become anonymous.
4. **Erasure** — the existing per-worker right-to-erasure wipes alerts, session files, and the face embedding on request (see the Privacy page).
5. **Badge alternative** — print each worker's QR (Workers → Show QR), and badge-scan check-in replaces the camera entirely if the floor prefers it.

## Why this is a selling point, not a risk

- **Offline-first:** no face data ever leaves the building — the strongest answer to works-council / GDPR concerns competitors can't match.
- **Choice, not mandate:** badge-only floors and anonymous floors work identically for posture safety — identity is an overlay, not a requirement.
- **Audited:** every identity-mode, consent, badge, and enrollment change is written to the audit trail with actor + timestamp.

## API surface (for integrators)

| Endpoint | Purpose |
|---|---|
| `PATCH /api/workers/{id}/identity` | Set identity_mode + consent_status (enforced in the matcher) |
| `PUT /api/workers/{id}/badge` | Assign a badge/QR identifier (unique) |
| `DELETE /api/workers/{id}/badge` | Remove it |
| `GET /api/workers/{id}/badge/qr` | SVG QR code of the badge (print on the worker's badge) |
| `POST /api/workers/identify-badge` | Resolve a scanned code → worker (badge check-in) |
| `POST /api/workers/{id}/face` / `DELETE` | Enroll / remove a face photo |

**The single sentence for the customer:** *"Every worker chooses how the system knows them — by face with signed consent, by a badge they scan, or not at all — and the posture safety works exactly the same either way."*

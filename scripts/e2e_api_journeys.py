"""End-to-end API QA journeys against the live backend (default http://127.0.0.1:8000).

Run:  python scripts/e2e_api_journeys.py [--base http://127.0.0.1:8000]

Covers the core user journeys at the API layer:
  J1 health                J2 demo auth (operator)
  J3 unauthenticated 401    J4 garbage-token 401
  J5 operator 403 matrix    J6 operator-allowed reads
  J7 signup entitlements (pilot: 4 cameras / 50 workers / admin role)
  J8 login (good + bad password)
  J9 RBAC matrix: anon/operator/admin x guarded endpoints
  J10 report digest RBAC    J11 session lifecycle start -> status -> stop -> history
  J12 pilot request create (QA-marked) + admin list
  J13 404 handling          J14 billing config (trial honesty evidence)
  J15 cleanup (delete the QA user we created)

Evidence: results/qa-pass/e2e_api_results.json (gitignored, like the rest of qa-pass).
Exit code: 0 = no blockers failed, 1 = at least one blocker failed.
Severity: 'blocker' = journey broken; 'finding' = recorded anomaly, not a hard fail.

Deliberate limits: no rate-limit probing (auth is throttled 10/min/IP), no erasure of
pre-existing data, exactly ONE QA-marked pilot request is created so the intake tracker
gets one clearly-labelled record this run.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

RESULTS: list[dict] = []
START = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def call(method: str, path: str, token: str | None = None, body: dict | None = None,
         base: str = "", timeout: float = 30.0) -> tuple[int, object, int]:
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ms = round((time.monotonic() - t0) * 1000)
            try:
                return resp.status, json.loads(raw), ms
            except json.JSONDecodeError:
                return resp.status, {"_bytes": len(raw)}, ms
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        ms = round((time.monotonic() - t0) * 1000)
        try:
            return exc.code, json.loads(raw), ms
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:300].decode("utf-8", "replace")}, ms
    except Exception as exc:  # noqa: BLE001 — evidence, not control flow
        ms = round((time.monotonic() - t0) * 1000)
        return -1, {"error": repr(exc)}, ms


def check(step_id: str, name: str, ok: bool, severity: str = "blocker", **extra) -> bool:
    entry = {"id": step_id, "name": name, "ok": bool(ok), "severity": severity, **extra}
    RESULTS.append(entry)
    mark = "PASS" if ok else ("FAIL" if severity == "blocker" else "NOTE")
    print(f"[{mark}] {step_id} {name}" + (f" — {extra.get('detail', '')}" if not ok or extra.get("detail") else ""),
          flush=True)
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    B = args.base

    # ---- J1 health -------------------------------------------------------
    st, body, ms = call("GET", "/health", base=B)
    check("J1", "GET /health is 200", st == 200, status=st, ms=ms)

    # ---- J2 demo auth ----------------------------------------------------
    st, body, ms = call("POST", "/api/auth/demo", base=B)
    demo_token = (body or {}).get("token") if isinstance(body, dict) else None
    demo_role = ((body or {}).get("user") or {}).get("role") if isinstance(body, dict) else None
    check("J2", "demo login returns token with operator role",
          st == 200 and bool(demo_token) and demo_role == "operator",
          status=st, ms=ms, detail=f"status={st} role={demo_role}")

    # ---- J3/J4 unauthenticated & garbage token ---------------------------
    st, body, _ = call("GET", "/api/cameras", base=B)
    check("J3", "anonymous GET /api/cameras -> 401", st == 401, status=st)
    st, body, _ = call("GET", "/api/cameras", token="not-a-real-jwt", base=B)
    check("J4", "garbage bearer token -> 401", st == 401, status=st)

    # ---- J5/J6 operator role behaviour ------------------------------------
    if demo_token:
        st, body, ms = call("GET", "/api/cameras", token=demo_token, base=B)
        detail = json.dumps(body)[:160] if body else ""
        friendly = "permission" in detail.lower() or "role" in detail.lower() or "forbidden" in detail.lower()
        check("J5", "operator GET /api/cameras -> 403 with explained message",
              st == 403, status=st, ms=ms, detail=detail)
        check("J5b", "403 detail explains the permission (not a raw stack)",
              st != 403 or friendly, severity="finding", status=st, detail=detail)
        st, body, ms = call("GET", "/api/dashboard", token=demo_token, base=B)
        check("J6", "operator GET /api/dashboard -> 200", st == 200, status=st, ms=ms)

    # ---- J7 signup entitlements ------------------------------------------
    qa_email = f"qa-e2e-{START.lower()}@ergovigilance-qa.com"
    qa_password = "Qa-E2E-Passw0rd!42"
    st, body, ms = call(
        "POST", "/api/auth/signup", base=B,
        body={
            "organization_name": f"QA E2E Org {START}",
            "industry": "Manufacturing",
            "country": "IN",
            "email": qa_email,
            "password": qa_password,
            "full_name": "QA E2E Runner",
            "agree_terms": True,
        },
    )
    qa_token = (body or {}).get("token") if isinstance(body, dict) else None
    org = (body or {}).get("organization") or {} if isinstance(body, dict) else {}
    user = (body or {}).get("user") or {} if isinstance(body, dict) else {}
    ok_shape = (
        st in (200, 201)
        and bool(qa_token)
        and org.get("plan") == "pilot"
        and org.get("max_cameras") == 4
        and org.get("max_workers") == 50
        and user.get("role") == "admin"
    )
    check("J7", "signup -> pilot plan, max_cameras=4, max_workers=50, admin user",
          ok_shape, status=st, ms=ms,
          detail=f"status={st} plan={org.get('plan')} cams={org.get('max_cameras')} "
                 f"workers={org.get('max_workers')} role={user.get('role')}")
    # duplicate-email conflict
    st_dup, _, _ = call("POST", "/api/auth/signup", base=B,
                        body={"organization_name": "Dup Org", "email": qa_email,
                              "password": qa_password, "agree_terms": True})
    check("J7dup", "duplicate signup email -> 409", st_dup == 409, status=st_dup)

    # ---- J8 login good + bad ---------------------------------------------
    st, body, ms = call("POST", "/api/auth/login", base=B,
                        body={"email": qa_email, "password": qa_password})
    qa_token = (body or {}).get("token") if isinstance(body, dict) else qa_token
    check("J8a", "login with just-created account -> 200 + token",
          st == 200 and bool(qa_token), status=st, ms=ms)
    st, body, ms = call("POST", "/api/auth/login", base=B,
                        body={"email": qa_email, "password": "wrong-password-x"})
    check("J8b", "bad password -> 4xx (not 200)", 400 <= st < 500, status=st, ms=ms,
          detail=json.dumps(body)[:120] if body else "")

    # ---- J9 RBAC matrix ---------------------------------------------------
    # (endpoint, anonymous, operator, admin, note) expected status classes
    matrix = [
        ("/api/cameras",        401, 403, 200, "supervisor+"),
        ("/api/alerts",         401, 200, 200, "any authenticated (+ live-session access)"),
        ("/api/reports/digest", 401, 403, 200, "supervisor+"),
        ("/api/users",          401, 403, 200, "admin"),
        ("/api/audit-log",      401, 403, 200, "admin/safety_mgr"),
        ("/api/manager",        401, 403, 200, "safety_mgr+"),
        ("/api/deployment",     401, 403, 200, "admin"),
        ("/api/session/status", 401, 200, 200, "any authenticated"),
    ]
    for path, want_anon, want_op, want_admin, note in matrix:
        anon_st, _, _ = call("GET", path, base=B)
        op_st, _, _ = call("GET", path, token=demo_token, base=B) if demo_token else (-2, None, 0)
        ad_st, _, _ = call("GET", path, token=qa_token, base=B) if qa_token else (-2, None, 0)
        check(f"J9:{path}", f"RBAC {path} ({note}): anon={want_anon} operator={want_op} admin={want_admin}",
              anon_st == want_anon and op_st == want_op and ad_st == want_admin,
              severity="blocker" if want_op == 403 else "finding",
              detail=f"got anon={anon_st} op={op_st} admin={ad_st}")

    # ---- J10 digest body sanity (admin) -----------------------------------
    if qa_token:
        st, body, ms = call("GET", "/api/reports/digest", token=qa_token, base=B)
        check("J10", "admin GET /api/reports/digest -> 200 JSON",
              st == 200, severity="finding", status=st, ms=ms,
              detail=json.dumps(body)[:120] if body else "")

    # ---- J11 session lifecycle -------------------------------------------
    if demo_token:
        st, body, ms = call("POST", "/api/session/start", token=demo_token, base=B, body={})
        start_body = body if isinstance(body, dict) else {}
        detail = json.dumps(body)[:200] if body else ""
        session_ok = st in (200, 201)
        env_issue = (not session_ok) and any(
            k in detail.lower() for k in ("camera", "unavailable", "device", "webcam")
        )
        check("J11a", "POST /api/session/start succeeds (or explains missing camera/service)",
              session_ok or env_issue,
              severity="finding" if env_issue else "blocker",
              status=st, ms=ms, detail=detail)
        st, body, ms = call("GET", "/api/session/status", token=demo_token, base=B)
        check("J11b", "GET /api/session/status -> 200", st == 200, status=st, ms=ms)
        if session_ok:
            st, body, ms = call("POST", "/api/session/stop", token=demo_token, base=B, body={})
            check("J11c", "POST /api/session/stop -> 2xx", 200 <= st < 300, status=st, ms=ms)
            # J11e: a stopped session must appear in history even when no person
            # was detected (guards the O1 "zero-person sessions vanish" fix).
            st, body, ms = call("GET", "/api/sessions", token=demo_token, base=B)
            # /api/sessions is paginated: {sessions, total, page, pages}
            if isinstance(body, dict):
                listed = body.get("sessions") or []
            elif isinstance(body, list):
                listed = body
            else:
                listed = []
            sid = start_body.get("session_id") or start_body.get("id")
            if sid is None and isinstance(start_body.get("session"), dict):
                sid = start_body["session"].get("id")
            if sid is not None:
                found = any(s.get("id") == sid for s in listed if isinstance(s, dict))
            else:
                found = len(listed) > 0
            check("J11e", "stopped session appears in GET /api/sessions history",
                  st == 200 and found, severity="finding", status=st, ms=ms,
                  detail=f"listed={len(listed)} session_id={sid}")
        st, body, ms = call("GET", "/api/sessions", token=demo_token, base=B)
        check("J11d", "GET /api/sessions -> 200 list", st == 200, status=st, ms=ms)

    # ---- J12 pilot request (single QA-marked record) ----------------------
    st, body, ms = call("POST", "/api/pilot-requests", base=B, body={
        "company_name": f"QA-AUTO TEST ORG ({START})",
        "contact_name": "QA Automation",
        "email": "qa-e2e@example.com",
        "role": "EHS Manager",
        "num_stations": "1",
        "message": "Created by scripts/e2e_api_journeys.py — safe to delete.",
    })
    check("J12a", "anonymous POST /api/pilot-requests -> 2xx", 200 <= st < 300,
          status=st, ms=ms, detail=json.dumps(body)[:160] if body else "")
    if qa_token:
        st, body, ms = call("GET", "/api/pilot-requests", token=qa_token, base=B)
        found = False
        if st == 200 and isinstance(body, list):
            found = any("QA-AUTO" in json.dumps(item) for item in body)
        elif st == 200 and isinstance(body, dict):
            found = "QA-AUTO" in json.dumps(body)
        check("J12b", "admin can list the QA pilot request", st == 200 and found,
              severity="finding", status=st, ms=ms)

    # ---- J13 404 ----------------------------------------------------------
    st, body, _ = call("GET", "/api/sessions/99999999", token=demo_token, base=B)
    check("J13", "unknown session id -> 404", st == 404, status=st,
          detail=json.dumps(body)[:120] if body else "")

    # ---- J14 billing config (evidence for trial-claim honesty) ------------
    st, body, ms = call("GET", "/api/billing/config", base=B)
    stripe_on = None
    if st == 200 and isinstance(body, dict):
        stripe_on = body.get("stripe_enabled", body.get("enabled"))
    check("J14", "GET /api/billing/config -> 200 (records trial-config state)",
          st == 200, severity="finding", status=st, ms=ms,
          detail=f"stripe_enabled={stripe_on}")

    # ---- J15 cleanup: delete QA users we created (incl. earlier crashed runs) ----
    # The acting QA admin cannot delete its own account: the API answers 409 by
    # design (backend_api/app/api/users.py delete_user self-lockout guard).
    # So cleanup is three explicit steps, each asserted:
    #   J15a  self-delete -> 409 (the guard works)
    #   J15   API sweep removes every OTHER qa-e2e-* user
    #   J15db direct SQLite sweep removes leftovers a crashed run left behind
    self_uid = user.get("id") if isinstance(user, dict) else None
    if qa_token and self_uid is not None:
        st, body, _ = call("DELETE", f"/api/users/{self_uid}", token=qa_token, base=B)
        check("J15a", "admin DELETE own account -> 409 self-lockout guard",
              st == 409, severity="finding", status=st,
              detail=json.dumps(body)[:120] if body else "")

    if qa_token:
        st_list, body_list, _ = call("GET", "/api/users", token=qa_token, base=B)
        qa_uids = []
        if st_list == 200 and isinstance(body_list, list):
            qa_uids = [
                u.get("id") for u in body_list
                if isinstance(u.get("email"), str)
                and u["email"].startswith("qa-e2e-")
                and u["email"].endswith("@ergovigilance-qa.com")
                and u.get("id") != self_uid
            ]
        deleted = 0
        failed = []
        for uid in qa_uids:
            st, _, _ = call("DELETE", f"/api/users/{uid}", token=qa_token, base=B)
            if 200 <= st < 300:
                deleted += 1
            else:
                failed.append(f"{uid}:{st}")
        check("J15", "admin DELETE sweeps every OTHER QA E2E user",
              st_list == 200 and deleted == len(qa_uids), severity="finding",
              status=st_list,
              detail=f"list_status={st_list} deleted {deleted}/{len(qa_uids)}" +
                     (f" failed={failed}" if failed else ""))

    # J15db: final sweep directly in the SQLite store — catches users left by
    # crashed runs (a stale qa-e2e-* admin can never delete the new one via API).
    db_path = "backend_api/local_auth.db"
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(
            "DELETE FROM users WHERE email LIKE 'qa-e2e-%@ergovigilance-qa.com'"
        )
        users_removed = cur.rowcount
        cur.execute(
            "DELETE FROM organizations WHERE name LIKE 'QA E2E Org %' OR name = 'Dup Org'"
        )
        orgs_removed = cur.rowcount
        con.commit()
        cur.execute(
            "SELECT COUNT(*) FROM users WHERE email LIKE 'qa-e2e-%@ergovigilance-qa.com'"
        )
        remaining = cur.fetchone()[0]
        con.close()
        check("J15db", "SQLite sweep removes leftover QA users + QA/Dup orgs",
              remaining == 0, severity="finding",
              detail=f"users_removed={users_removed} orgs_removed={orgs_removed} remaining={remaining}")
    except Exception as exc:  # noqa: BLE001 — evidence, not control flow
        check("J15db", "SQLite sweep of QA users/orgs", False, severity="finding",
              detail=repr(exc))

    # ---- persist ----------------------------------------------------------
    blockers_failed = [r for r in RESULTS if r["severity"] == "blocker" and not r["ok"]]
    findings = [r for r in RESULTS if r["severity"] == "finding" and not r["ok"]]
    out = {
        "started": START,
        "base": B,
        "total": len(RESULTS),
        "passed": sum(1 for r in RESULTS if r["ok"]),
        "blockers_failed": len(blockers_failed),
        "findings": len(findings),
        "results": RESULTS,
    }
    path = "results/qa-pass/e2e_api_results.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nAPI journeys: {out['passed']}/{out['total']} passed · "
          f"{len(blockers_failed)} blocker failure(s) · {len(findings)} finding(s)")
    print(f"evidence: {path}")
    return 1 if blockers_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

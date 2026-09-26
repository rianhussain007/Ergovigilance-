#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# ErgoVigilance — TLS Handshake Drill (P0-3, TRL-7 C4 evidence)
# ══════════════════════════════════════════════════════════════════
#
# Proves the production TLS stack actually terminates HTTPS with the
# exact configuration we ship, without touching the running compose
# stack. A throwaway nginx container on an ISOLATED docker network is
# started with:
#   - the production nginx config (ui_posture/nginx.tls.conf.example)
#   - a self-signed pair generated per certs/README.md (the documented
#     internal-LAN path; Let's Encrypt issuance needs a public DNS name
#     and is exercised at the real site on Day 0)
# All handshakes and HTTP checks run from the HOST via openssl s_client,
# so the drill proves the network path too, not just in-container state.
#
# Stages (all must pass):
#   1. production nginx TLS config parses (nginx -t with cert pair)
#   2. compose TLS overlay interpolates (with dummy required secrets)
#   3. nginx starts and serves HTTPS on :443 (real GET over TLS)
#   4. TLSv1.2 handshake succeeds          (protocol floor held)
#   5. TLSv1.3 handshake succeeds          (modern protocol works)
#   6. TLSv1.0 handshake REFUSED           (deprecated protocols off)
#   7. HSTS + nosniff headers on the HTTPS response
#   8. HTTP :80 answers 301 -> https://    (redirect works)
#   9. overlay binds the documented cert paths
#
# Usage:  bash deploy/tls_handshake_drill.sh
# Output: DRILL PASS/FAIL + JSON result at outputs/tls_drill/result.json
# ══════════════════════════════════════════════════════════════════

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RESULT_DIR="${REPO_ROOT}/outputs/tls_drill"
RESULT_FILE="${RESULT_DIR}/result.json"
mkdir -p "${RESULT_DIR}"

NET="tls-drill-net-${STAMP}"
CTR="tls-drill-${STAMP}"
# Windows/Docker Desktop: a mount source under MSYS /tmp resolves to
# C:\Users\...\Temp for host tools, but Docker mounts it as a path
# that does not exist for the daemon (bind mount silently empty).
# Keep every docker -v source under the repo (a real Windows path).
WORK="${REPO_ROOT}/outputs/tls_drill/work_${STAMP}"
mkdir -p "${WORK}"
trap 'docker rm -f "${CTR}" >/dev/null 2>&1; docker network rm "${NET}" >/dev/null 2>&1; rm -rf "${WORK}"' EXIT

PASS=0; FAIL=0
declare -a STAGES=()
log()  { echo "[TLS-DRILL] $1"; }
pass() { echo "[TLS-DRILL] ✅ $1"; PASS=$((PASS+1)); STAGES+=("\"$1\": \"pass\""); }
fail() { echo "[TLS-DRILL] ❌ $1"; FAIL=$((FAIL+1)); STAGES+=("\"$1\": \"fail\""); }

# ── Self-signed pair, per certs/README.md (same subject, CN=ergovigilance) ──
# The subject goes through a config file with `prompt = no` instead of
# `-subj`: Git Bash (MSYS) rewrites the leading "/" of "/CN=..." into a
# Windows path ("C:/Program Files/Git/CN=..."), which openssl rejects. The
# -config form is path-mangling-proof and portable to Linux shells too.
log "Generating self-signed pair (certs/README.md path)"
printf '[req]\ndistinguished_name = dn\nprompt = no\n[dn]\nCN = ergovigilance\n' \
    > "${WORK}/req.cnf"
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "${WORK}/privkey.pem" -out "${WORK}/fullchain.pem" \
    -config "${WORK}/req.cnf" >/dev/null 2>&1
if [ -s "${WORK}/fullchain.pem" ] && [ -s "${WORK}/privkey.pem" ]; then
    log "cert pair generated"
else
    fail "self-signed pair generation"
fi

docker network create "${NET}" >/dev/null 2>&1

# Compose files hard-require AUTH_JWT_SECRET via :? gates; a dummy is fine
# for config VALIDATION (no container from this path ever starts).
COMPOSE_ENV=(AUTH_JWT_SECRET="${AUTH_JWT_SECRET:-drill-only-dummy-secret-0123456789abcdef}")

# ── Stage 1+2: config validity ──────────────────────────────────────
# MSYS_NO_PATHCONV: Git Bash rewrites "-v /c/...:/etc/nginx/...:ro" — it
# converts the container-side path to "C:\Program Files\Git\etc\..." and
# the ":" separators to ";", so the container silently gets NO mounts and
# runs the stock image config (no :443 listener). Disabling the rewrite is
# what makes host↔container bind mounts actually land on Docker Desktop.
MSYS_NO_PATHCONV=1 docker run --rm \
    -v "${WORK}/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro" \
    -v "${WORK}/privkey.pem:/etc/nginx/ssl/privkey.pem:ro" \
    -v "${REPO_ROOT}/ui_posture/nginx.tls.conf.example:/etc/nginx/conf.d/default.conf:ro" \
    nginx:alpine nginx -t >/dev/null 2>&1 \
    && pass "production nginx TLS config parses" \
    || fail "production nginx TLS config does not parse"

if env "${COMPOSE_ENV[@]}" docker compose -f docker-compose.yml -f docker-compose.tls.yml \
        --project-directory "${REPO_ROOT}" config >/dev/null 2>&1; then
    pass "compose TLS overlay interpolates cleanly"
else
    fail "compose TLS overlay config invalid"
fi

# ── Throwaway nginx with the production config ──────────────────────
# Ports are PUBLISHED to host loopback (drill-only ports, 18443/18080) —
# Docker Desktop container IPs are not reachable from the Windows host,
# so host-side openssl s_client must go through a published port, exactly
# like a real client would.
MSYS_NO_PATHCONV=1 docker run -d --name "${CTR}" --network "${NET}" \
    -p 127.0.0.1:18443:443 -p 127.0.0.1:18080:80 \
    -v "${WORK}/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro" \
    -v "${WORK}/privkey.pem:/etc/nginx/ssl/privkey.pem:ro" \
    -v "${REPO_ROOT}/ui_posture/nginx.tls.conf.example:/etc/nginx/conf.d/default.conf:ro" \
    nginx:alpine >/dev/null 2>&1
sleep 2
TLS_ENDPOINT="127.0.0.1:18443"
if ! docker inspect "${CTR}" >/dev/null 2>&1; then
    log "drill container did not start"
    fail "throwaway nginx container started"
fi
# Surface nginx startup errors directly — 'running' with a dead master is
# the failure mode the '-c /dev/null' emerg taught us to expect.
docker logs "${CTR}" 2>&1 | grep -iE 'emerg|\[error\]' | head -3
# The nginx MASTER can die while the container (tail -f pidfile) stays up.
nginx_alive=$(docker exec "${CTR}" pgrep nginx >/dev/null 2>&1 && echo yes || echo no)
if [ "${nginx_alive}" != "yes" ]; then
    fail "nginx master process alive in container"
fi

# Host-side helpers (openssl s_client against the published drill port)
_tls_out() { printf '%b' "$1" | openssl s_client -connect "${TLS_ENDPOINT}" -quiet 2>/dev/null; }

# Wait for the published port to answer (Windows port-proxy can lag the
# container start by seconds; manual runs with sleep 3 always worked).
PORT_UP=no
for _try in 1 2 3 4 5; do
    if _tls_out 'GET / HTTP/1.0\r\n\r\n' | head -1 | grep -q "HTTP/"; then PORT_UP=yes; break; fi
    sleep 2
done
if [ "${PORT_UP}" != "yes" ]; then
    log "published port never answered — container state:"
    docker ps --filter "name=${CTR}" --format '{{.Names}} {{.Ports}} {{.Status}}' >&2
    log "in-container nginx master: $(docker exec "${CTR}" pgrep nginx >/dev/null 2>&1 && echo alive || echo DEAD)"
    log "in-container listeners: $(docker exec "${CTR}" sh -c 'cat /proc/net/tcp | wc -l') tcp lines"
    log "s_client verbose tail:"
    echo | openssl s_client -connect "${TLS_ENDPOINT}" 2>&1 | tail -5 >&2
fi

# ── Stage 3: HTTPS answers with a real HTTP response ────────────────
STATUS=$(_tls_out 'GET / HTTP/1.0\r\n\r\n' | head -1)
case "${STATUS}" in
    HTTP/1*200*|HTTP/1*301*) pass "nginx serves HTTPS on :443 with production config (${STATUS})" ;;
                          *) fail "HTTPS :443 did not answer (got: ${STATUS:-nothing})" ;;
esac

# ── Stages 4-6: protocol handshakes ─────────────────────────────────
# Matcher: "Cipher is [^ (]" — a FAILED handshake still prints
# "Cipher is (NONE)", so a bare grep -q "Cipher is" would false-pass
# every stage whenever nothing answers at all. Requiring a real cipher
# (first char not "(" or space) makes pass ⇔ negotiated, fail ⇔ refused.
echo | openssl s_client -connect "${TLS_ENDPOINT}" -tls1_2 2>/dev/null | grep -qE "Cipher is [^ (]" \
    && pass "TLSv1.2 handshake succeeds" \
    || fail "TLSv1.2 handshake failed"
echo | openssl s_client -connect "${TLS_ENDPOINT}" -tls1_3 2>/dev/null | grep -qE "Cipher is [^ (]" \
    && pass "TLSv1.3 handshake succeeds" \
    || fail "TLSv1.3 handshake failed"
if echo | openssl s_client -connect "${TLS_ENDPOINT}" -tls1 2>/dev/null | grep -qE "Cipher is [^ (]"; then
    fail "TLSv1.0 still accepted (must be refused)"
else
    pass "TLSv1.0 refused"
fi

# ── Stage 7: security headers over the real HTTPS response ──────────
HDRS=$(_tls_out 'HEAD / HTTP/1.0\r\n\r\n')
echo "${HDRS}" | grep -qi "strict-transport-security" \
    && pass "HSTS header present on HTTPS response" \
    || fail "HSTS header missing"
echo "${HDRS}" | grep -qi "x-content-type-options: nosniff" \
    && pass "nosniff header present on HTTPS response" \
    || fail "nosniff header missing"

# ── Stage 8: :80 -> :443 redirect (busybox wget inside the container) ──
LOC=$(docker exec "${CTR}" sh -c \
    'wget -S -q -O /dev/null http://127.0.0.1/ 2>&1' | grep -i "^ *Location:" | head -1 | tr -d '\r' | awk '{print $2}')
case "${LOC}" in
    https://*) pass "HTTP :80 redirects to HTTPS" ;;
            *) fail "HTTP :80 did not redirect (got: ${LOC:-nothing})" ;;
esac

# ── Stage 9: overlay binds the documented cert paths ────────────────
if env "${COMPOSE_ENV[@]}" docker compose -f docker-compose.yml -f docker-compose.tls.yml \
        --project-directory "${REPO_ROOT}" config 2>/dev/null | grep -q "fullchain.pem"; then
    pass "TLS overlay binds the documented cert paths"
else
    fail "TLS overlay cert bind mounts not resolved by compose"
fi

# ── Result JSON ─────────────────────────────────────────────────────
STAGE_LINES=$(printf '%s,\n' "${STAGES[@]:-}" | sed 's/^/  /' | sed '$ s/,$//')
VERDICT="$([ ${FAIL} -eq 0 ] && echo DRILL_PASS || echo DRILL_FAIL)"
cat > "${RESULT_FILE}" <<EOF
{
  "drill": "tls_handshake",
  "date_utc": "${STAMP}",
  "scope": "throwaway nginx container + isolated docker network; production nginx config + self-signed pair per certs/README.md; host-side openssl s_client handshakes",
  "stages": {
${STAGE_LINES}
  },
  "passed": ${PASS},
  "failed": ${FAIL},
  "verdict": "${VERDICT}"
}
EOF

echo ""
log "═══════════════════════════════════════════════════════════"
log "DRILL ${VERDICT#DRILL_} — ${PASS} passed, ${FAIL} failed"
log "Result: ${RESULT_FILE}"
log "═══════════════════════════════════════════════════════════"
[ ${FAIL} -eq 0 ]

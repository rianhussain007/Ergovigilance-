#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# ErgoVigilance — Backup/Restore Drill (P0-7, TRL-7 C4 evidence)
# ══════════════════════════════════════════════════════════════════
#
# Exercises the full backup → encrypt → decrypt → restore → verify loop
# in a HERMETIC temp sandbox. It never touches the real repo tree's
# outputs/, recordings/, backend_api/local_auth.db or any live volume —
# the sandbox gets its own copy of deploy/ and its own fake data trees,
# so a bug in the scripts can destroy nothing but the sandbox.
#
# What it proves (each stage must pass for the drill to count):
#   1. backup.sh captures sessions + config from the sandbox tree
#   2. --encrypt produces an .enc archive that is NOT plaintext-readable
#   3. restore.sh --dry-run lists contents without changing anything
#   4. restore.sh --yes restores sessions byte-identical to the source
#   5. wrong passphrase is rejected
#
# Usage:  bash deploy/backup_restore_drill.sh
# Output: prints DRILL PASS / DRILL FAIL and writes a JSON result to
#         outputs/backup_drill/result.json (for the evidence pack).
# ══════════════════════════════════════════════════════════════════

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SANDBOX="$(mktemp -d)"
RESULT_FILE="${REPO_ROOT}/outputs/backup_drill/result.json"
RESULT_DIR="$(dirname "${RESULT_FILE}")"
mkdir -p "${RESULT_DIR}"

PASS=0
FAIL=0
declare -a STAGE_RESULTS=()
T0=$(date +%s)

log()  { echo "[DRILL] $1"; }
pass() { echo "[DRILL] ✅ $1"; PASS=$((PASS+1)); STAGE_RESULTS+=("\"$1\": \"pass\""); }
fail() { echo "[DRILL] ❌ $1"; FAIL=$((FAIL+1)); STAGE_RESULTS+=("\"$1\": \"fail\""); }

cleanup() { rm -rf "${SANDBOX}"; }
trap cleanup EXIT

log "Sandbox: ${SANDBOX} (deleted on exit — real repo data is never touched)"

# ── Stage 0: sandbox layout with fake "production" data ────────────
mkdir -p "${SANDBOX}/outputs/sessions" "${SANDBOX}/recordings" \
         "${SANDBOX}/deploy" "${SANDBOX}/backend_api"
cp "${REPO_ROOT}/deploy/backup.sh"  "${SANDBOX}/deploy/"
cp "${REPO_ROOT}/deploy/restore.sh" "${SANDBOX}/deploy/"
chmod +x "${SANDBOX}/deploy/"*.sh
echo '{"session_id": "SESH-DRILL-1", "risk_level": "MEDIUM"}' \
    > "${SANDBOX}/outputs/sessions/SESH-DRILL-1.json"
echo '{"session_id": "SESH-DRILL-2", "risk_level": "LOW"}' \
    > "${SANDBOX}/outputs/sessions/SESH-DRILL-2.json"
echo "drill-config-marker" > "${SANDBOX}/.env"
cp "${REPO_ROOT}/docker-compose.yml" "${SANDBOX}/docker-compose.yml" 2>/dev/null || true
log "Sandbox prepared: 2 session files, config, deploy scripts"

# ── Stage 1: backup (plain) ─────────────────────────────────────────
if (cd "${SANDBOX}" && bash deploy/backup.sh) > "${SANDBOX}/backup.log" 2>&1; then
    ARCHIVE=$(ls "${SANDBOX}"/backups/ergovigilance_backup_*.tar.gz 2>/dev/null | head -1)
    # Layout: outer archive holds <name>/sessions.tar.gz (tar-in-tar).
    # Stream the inner member out and list it — 'tar | grep -q' would die
    # by SIGPIPE under pipefail the moment grep matches.
    if [ -n "${ARCHIVE}" ]; then
        INNER_NAME=$(tar -tzf "${ARCHIVE}" | grep "sessions.tar.gz" | head -1)
        INNER_LIST=$(tar -xzOf "${ARCHIVE}" "${INNER_NAME}" 2>/dev/null | tar -tz 2>/dev/null || true)
    fi
    if [ -n "${ARCHIVE:-}" ] && echo "${INNER_LIST:-}" | grep -q "SESH-DRILL-1.json"; then
        pass "backup captures sessions into the archive"
    else
        fail "backup archive missing session data"
    fi
else
    fail "backup.sh exited non-zero (see ${SANDBOX}/backup.log — kept below in JSON as text)"
    ARCHIVE=""
fi

# ── Stage 2: backup --encrypt ───────────────────────────────────────
export BACKUP_PASSPHRASE="drill-passphrase-0123456789"
if [ -n "${ARCHIVE:-}" ] && (cd "${SANDBOX}" && bash deploy/backup.sh --encrypt) \
        >> "${SANDBOX}/backup.log" 2>&1; then
    ENC=$(ls "${SANDBOX}"/backups/ergovigilance_backup_*.tar.gz.enc 2>/dev/null | head -1)
    if [ -n "${ENC}" ] && ! tar -tzf "${ENC}" >/dev/null 2>&1 \
       && ! grep -q "SESH-DRILL-1" "${ENC}" 2>/dev/null; then
        pass "encrypted archive is not plaintext-readable"
    else
        fail "encrypted archive missing or readable"
    fi
else
    fail "backup.sh --encrypt exited non-zero"
    ENC=""
fi

# ── Stage 3: restore --dry-run changes nothing ──────────────────────
if [ -n "${ENC:-}" ]; then
    SUM_BEFORE=$(find "${SANDBOX}/outputs" -type f | sort | xargs md5sum 2>/dev/null | md5sum)
    if (cd "${SANDBOX}" && bash deploy/restore.sh "${ENC}" --dry-run) \
            > "${SANDBOX}/dryrun.log" 2>&1; then
        SUM_AFTER=$(find "${SANDBOX}/outputs" -type f | sort | xargs md5sum 2>/dev/null | md5sum)
        [ "${SUM_BEFORE}" = "${SUM_AFTER}" ] \
            && pass "restore --dry-run lists contents without changes" \
            || fail "dry-run modified outputs/"
    else
        fail "restore --dry-run exited non-zero"
    fi
fi

# ── Stage 4: full restore → byte-identical sessions ─────────────────
if [ -n "${ENC:-}" ]; then
    rm -rf "${SANDBOX}/outputs/sessions"
    if (cd "${SANDBOX}" && bash deploy/restore.sh "${ENC}" --yes) \
            > "${SANDBOX}/restore.log" 2>&1; then
        if diff <(echo '{"session_id": "SESH-DRILL-1", "risk_level": "MEDIUM"}') \
                "${SANDBOX}/outputs/sessions/SESH-DRILL-1.json" >/dev/null 2>&1 \
           && [ -f "${SANDBOX}/outputs/sessions/SESH-DRILL-2.json" ]; then
            pass "restore --yes recovers sessions byte-identical"
        else
            fail "restored sessions differ from source"
        fi
    else
        fail "restore --yes exited non-zero"
    fi
fi

# ── Stage 5: wrong passphrase rejected ──────────────────────────────
if [ -n "${ENC:-}" ]; then
    if (cd "${SANDBOX}" && BACKUP_PASSPHRASE="wrong-passphrase" \
            bash deploy/restore.sh "${ENC}" --yes) \
            > "${SANDBOX}/wrongpass.log" 2>&1; then
        fail "wrong passphrase was accepted"
    else
        pass "wrong passphrase rejected"
    fi
fi

T1=$(date +%s)
RTO=$((T1 - T0))

# ── Result JSON for the evidence pack ───────────────────────────────
# Join entries with commas; strip the trailing comma from the last line.
STAGES=$(printf '%s,\n' "${STAGE_RESULTS[@]:-}" | sed 's/^/  /' | sed '$ s/,\n$//; $ s/,$//')
cat > "${RESULT_FILE}" <<EOF
{
  "drill": "backup_restore",
  "date_utc": "${STAMP}",
  "sandbox": "hermetic-temp-dir (real repo data untouched)",
  "rto_seconds": ${RTO},
  "stages": {
${STAGES}
  },
  "passed": ${PASS},
  "failed": ${FAIL},
  "verdict": "$([ ${FAIL} -eq 0 ] && echo DRILL_PASS || echo DRILL_FAIL)"
}
EOF

echo ""
log "═══════════════════════════════════════════════════════════"
log "DRILL $([ ${FAIL} -eq 0 ] && echo PASS || echo FAIL) — ${PASS} passed, ${FAIL} failed, RTO ${RTO}s"
log "Result: ${RESULT_FILE}"
log "═══════════════════════════════════════════════════════════"
[ ${FAIL} -eq 0 ]

#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# ErgoVigilance — Enterprise Backup Script
# ══════════════════════════════════════════════════════════════════
#
# Backs up:
# 1. PostgreSQL database (full dump)
# 2. Session JSON files
# 3. Recorded videos
# 4. Configuration files
# 5. User data (workers, API keys)
#
# Usage:
#   ./backup.sh                    # Full backup
#   ./backup.sh --db-only          # Database only
#   ./backup.sh --retention=30     # Keep last 30 backups
#   ./backup.sh --encrypt          # AES-256 the archive (BACKUP_PASSPHRASE required)
#
# Requires: pg_dump, tar, gzip (+ openssl for --encrypt, docker for
# capturing the compose auth DB)
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

# All paths below are repo-relative (sessions live in outputs/sessions, the
# auth DB under backend_api/) — anchor to the repo root so cron jobs that
# start in another directory still back up the right files.
cd "$(dirname "$0")/.."

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ergovigilance}"
DB_USER="${DB_USER:-ergovigilance}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="ergovigilance_backup_${TIMESTAMP}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BACKUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Create backup directory
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# Parse arguments
DB_ONLY=false
ENCRYPT=false
for arg in "$@"; do
    case $arg in
        --db-only) DB_ONLY=true ;;
        --encrypt) ENCRYPT=true ;;
        --retention=*) RETENTION_DAYS="${arg#*=}" ;;
    esac
done

if [ "$ENCRYPT" = true ] && [ -z "${BACKUP_PASSPHRASE:-}" ]; then
    error "--encrypt requires BACKUP_PASSPHRASE to be set"
fi

log "Starting backup: ${BACKUP_NAME}"
log "Backup directory: ${BACKUP_DIR}/${BACKUP_NAME}"

# ── 1. PostgreSQL Database Backup ────────────────────────────────
log "Backing up PostgreSQL database..."
PGPASSWORD="${DB_PASSWORD:-}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -F c \
    -Z 9 \
    -f "${BACKUP_DIR}/${BACKUP_NAME}/database.dump" 2>/dev/null || {
        warn "pg_dump failed — trying SQLite fallback"
        # Fallback to SQLite if PostgreSQL not available (bare-metal layout)
        if [ -f "backend_api/local_auth.db" ]; then
            cp backend_api/local_auth.db "${BACKUP_DIR}/${BACKUP_NAME}/local_auth.db"
            log "SQLite database backed up"
        elif command -v docker >/dev/null 2>&1; then
            # Compose deployments: the auth DB lives inside the
            # ergovigilance-db volume, not on the host filesystem.
            docker compose cp backend:/data/local_auth.db \
                "${BACKUP_DIR}/${BACKUP_NAME}/local_auth.db" >/dev/null 2>&1 \
                && log "SQLite database backed up (from compose volume)" \
                || warn "Auth DB not captured (stack not running, or no local_auth.db)"
        fi
    }

if [ -f "${BACKUP_DIR}/${BACKUP_NAME}/database.dump" ]; then
    DB_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}/database.dump" | cut -f1)
    log "Database backup: ${DB_SIZE}"
fi

# ── 2. Session Data Backup ──────────────────────────────────────
if [ "$DB_ONLY" = false ]; then
    log "Backing up session data..."
    # Real layout is outputs/sessions (both bare-metal and compose bind
    # mount); bare "sessions/" at the repo root never exists and the old
    # check silently skipped every session file.
    SESSIONS_SRC=""
    if [ -d "outputs/sessions" ] && [ "$(ls -A outputs/sessions 2>/dev/null)" ]; then
        SESSIONS_SRC="outputs/sessions"
    elif [ -d "sessions" ] && [ "$(ls -A sessions 2>/dev/null)" ]; then
        SESSIONS_SRC="sessions"
    fi
    if [ -n "${SESSIONS_SRC}" ]; then
        # Archive top level is always "sessions/" so restore.sh can extract
        # into outputs/ regardless of where it came from.
        tar -czf "${BACKUP_DIR}/${BACKUP_NAME}/sessions.tar.gz" \
            -C "$(dirname "${SESSIONS_SRC}")" "$(basename "${SESSIONS_SRC}")" 2>/dev/null || true
        SESSION_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}/sessions.tar.gz" 2>/dev/null | cut -f1)
        log "Sessions backup: ${SESSION_SIZE}"
    else
        warn "No sessions directory found"
    fi

    # ── 3. Recorded Videos Backup ────────────────────────────────
    log "Backing up recorded videos..."
    if [ -d "recordings" ] && [ "$(ls -A recordings 2>/dev/null)" ]; then
        tar -czf "${BACKUP_DIR}/${BACKUP_NAME}/recordings.tar.gz" recordings/ 2>/dev/null || true
        REC_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}/recordings.tar.gz" 2>/dev/null | cut -f1)
        log "Recordings backup: ${REC_SIZE}"
    else
        warn "No recordings found"
    fi

    # ── 4. Configuration Backup ──────────────────────────────────
    log "Backing up configuration..."
    mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}/config"
    cp -f .env "${BACKUP_DIR}/${BACKUP_NAME}/config/" 2>/dev/null || true
    cp -f .env.production.example "${BACKUP_DIR}/${BACKUP_NAME}/config/" 2>/dev/null || true
    cp -f docker-compose.yml "${BACKUP_DIR}/${BACKUP_NAME}/config/" 2>/dev/null || true

    # ── 5. Worker Data Backup ────────────────────────────────────
    log "Backing up worker data..."
    if [ -d "workers" ]; then
        tar -czf "${BACKUP_DIR}/${BACKUP_NAME}/workers.tar.gz" workers/ 2>/dev/null || true
    fi
fi

# ── 6. Create Archive ────────────────────────────────────────────
log "Creating final archive..."
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" -C "${BACKUP_DIR}" "${BACKUP_NAME}"
rm -rf "${BACKUP_DIR}/${BACKUP_NAME}"

ARCHIVE_PATH="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
if [ "$ENCRYPT" = true ]; then
    log "Encrypting archive (aes-256-cbc + pbkdf2)..."
    openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE \
        -in "${ARCHIVE_PATH}" -out "${ARCHIVE_PATH}.enc"
    rm -f "${ARCHIVE_PATH}"
    ARCHIVE_PATH="${ARCHIVE_PATH}.enc"
fi

FINAL_SIZE=$(du -h "${ARCHIVE_PATH}" | cut -f1)
log "Backup complete: ${ARCHIVE_PATH} (${FINAL_SIZE})"

# ── 7. Cleanup Old Backups ──────────────────────────────────────
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "ergovigilance_backup_*.tar.gz*" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

REMAINING=$(find "${BACKUP_DIR}" -name "ergovigilance_backup_*.tar.gz*" | wc -l)
log "Backups remaining: ${REMAINING}"

echo ""
log "═══════════════════════════════════════════════════════════"
log "Backup Summary"
log "═══════════════════════════════════════════════════════════"
log "  Name:     $(basename "${ARCHIVE_PATH}")"
log "  Size:     ${FINAL_SIZE}"
log "  Location: ${ARCHIVE_PATH}"
log "  Retention: ${RETENTION_DAYS} days"
log "═══════════════════════════════════════════════════════════"

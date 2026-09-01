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
#   ./backup.sh --retention 30     # Keep last 30 backups
#
# Requires: pg_dump, tar, gzip
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

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
for arg in "$@"; do
    case $arg in
        --db-only) DB_ONLY=true ;;
        --retention=*) RETENTION_DAYS="${arg#*=}" ;;
    esac
done

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
        # Fallback to SQLite if PostgreSQL not available
        if [ -f "backend_api/local_auth.db" ]; then
            cp backend_api/local_auth.db "${BACKUP_DIR}/${BACKUP_NAME}/local_auth.db"
            log "SQLite database backed up"
        fi
    }

if [ -f "${BACKUP_DIR}/${BACKUP_NAME}/database.dump" ]; then
    DB_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}/database.dump" | cut -f1)
    log "Database backup: ${DB_SIZE}"
fi

# ── 2. Session Data Backup ──────────────────────────────────────
if [ "$DB_ONLY" = false ]; then
    log "Backing up session data..."
    if [ -d "sessions" ]; then
        tar -czf "${BACKUP_DIR}/${BACKUP_NAME}/sessions.tar.gz" sessions/ 2>/dev/null || true
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

FINAL_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)
log "Backup complete: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz (${FINAL_SIZE})"

# ── 7. Cleanup Old Backups ──────────────────────────────────────
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "ergovigilance_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

REMAINING=$(find "${BACKUP_DIR}" -name "ergovigilance_backup_*.tar.gz" | wc -l)
log "Backups remaining: ${REMAINING}"

echo ""
log "═══════════════════════════════════════════════════════════"
log "Backup Summary"
log "═══════════════════════════════════════════════════════════"
log "  Name:     ${BACKUP_NAME}.tar.gz"
log "  Size:     ${FINAL_SIZE}"
log "  Location: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
log "  Retention: ${RETENTION_DAYS} days"
log "═══════════════════════════════════════════════════════════"

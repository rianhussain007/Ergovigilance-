#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# ErgoVigilance — Enterprise Restore Script
# ══════════════════════════════════════════════════════════════════
#
# Restores from backup:
# 1. PostgreSQL database
# 2. Session JSON files
# 3. Recorded videos
# 4. Configuration files
#
# Usage:
#   ./restore.sh backups/ergovigilance_backup_20260901_120000.tar.gz
#   ./restore.sh backups/ergovigilance_backup_20260901_120000.tar.gz --db-only
#   ./restore.sh backups/ergovigilance_backup_20260901_120000.tar.gz --dry-run
#
# WARNING: This will OVERWRITE existing data!
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

# Repo-relative paths (see backup.sh) — works from any starting directory.
cd "$(dirname "$0")/.."

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ergovigilance}"
DB_USER="${DB_USER:-ergovigilance}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[RESTORE]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup.tar.gz> [--db-only] [--dry-run]"
    echo ""
    echo "Available backups:"
    ls -lh backups/ergovigilance_backup_*.tar.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"
DB_ONLY=false
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --db-only) DB_ONLY=true ;;
        --dry-run) DRY_RUN=true ;;
    esac
done

# Verify backup exists
if [ ! -f "${BACKUP_FILE}" ]; then
    error "Backup file not found: ${BACKUP_FILE}"
fi

# Encrypted archives (backup.sh --encrypt): decrypt first.
DECRYPTED_FILE=""
if [[ "${BACKUP_FILE}" == *.enc ]]; then
    if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
        error "Encrypted backup — set BACKUP_PASSPHRASE to decrypt"
    fi
    DECRYPTED_FILE="$(mktemp).tar.gz"
    log "Decrypting backup..."
    openssl enc -d -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE \
        -in "${BACKUP_FILE}" -out "${DECRYPTED_FILE}" || {
        rm -f "${DECRYPTED_FILE}"
        error "Decryption failed — wrong BACKUP_PASSPHRASE?"
    }
    BACKUP_FILE="${DECRYPTED_FILE}"
fi

log "Backup file: ${BACKUP_FILE}"
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
log "Backup size: ${BACKUP_SIZE}"

# Extract to temp directory
TEMP_DIR=$(mktemp -d)
log "Extracting backup..."
tar -xzf "${BACKUP_FILE}" -C "${TEMP_DIR}"

# Find the backup directory
BACKUP_DIR=$(find "${TEMP_DIR}" -maxdepth 1 -type d -name "ergovigilance_backup_*" | head -1)
if [ -z "${BACKUP_DIR}" ]; then
    error "Invalid backup format"
fi

log "Backup contents:"
ls -la "${BACKUP_DIR}/"

if [ "$DRY_RUN" = true ]; then
    log "DRY RUN — no changes will be made"
    log "Would restore:"
    [ -f "${BACKUP_DIR}/database.dump" ] && log "  ✓ PostgreSQL database"
    [ -f "${BACKUP_DIR}/sessions.tar.gz" ] && log "  ✓ Session data"
    [ -f "${BACKUP_DIR}/recordings.tar.gz" ] && log "  ✓ Recorded videos"
    [ -d "${BACKUP_DIR}/config" ] && log "  ✓ Configuration files"
    rm -rf "${TEMP_DIR}"
    if [ -n "${DECRYPTED_FILE}" ]; then rm -f "${DECRYPTED_FILE}"; fi
    exit 0
fi

# Confirmation
echo ""
warn "═══════════════════════════════════════════════════════════"
warn "WARNING: This will OVERWRITE existing data!"
warn "═══════════════════════════════════════════════════════════"
read -p "Type 'RESTORE' to confirm: " CONFIRM
if [ "$CONFIRM" != "RESTORE" ]; then
    log "Restore cancelled"
    rm -rf "${TEMP_DIR}"
    if [ -n "${DECRYPTED_FILE}" ]; then rm -f "${DECRYPTED_FILE}"; fi
    exit 0
fi

# ── 1. Restore PostgreSQL Database ──────────────────────────────
if [ -f "${BACKUP_DIR}/database.dump" ]; then
    log "Restoring PostgreSQL database..."
    PGPASSWORD="${DB_PASSWORD:-}" pg_restore \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        -c \
        -if "${BACKUP_DIR}/database.dump" 2>/dev/null || {
            warn "pg_restore had warnings (this is usually OK)"
        }
    log "Database restored"
elif [ -f "${BACKUP_DIR}/local_auth.db" ]; then
    log "Restoring SQLite database..."
    cp "${BACKUP_DIR}/local_auth.db" "backend_api/local_auth.db"
    log "SQLite database restored"
fi

if [ "$DB_ONLY" = false ]; then
    # ── 2. Restore Session Data ──────────────────────────────────
    if [ -f "${BACKUP_DIR}/sessions.tar.gz" ]; then
        log "Restoring session data..."
        # Archive top level is "sessions/"; the app reads outputs/sessions
        # (both layouts archive the same top-level name — see backup.sh).
        mkdir -p outputs
        rm -rf outputs/sessions
        tar -xzf "${BACKUP_DIR}/sessions.tar.gz" -C outputs
        log "Sessions restored to outputs/sessions"
    fi

    # ── 3. Restore Recorded Videos ────────────────────────────────
    if [ -f "${BACKUP_DIR}/recordings.tar.gz" ]; then
        log "Restoring recorded videos..."
        rm -rf recordings/
        tar -xzf "${BACKUP_DIR}/recordings.tar.gz"
        log "Recordings restored"
    fi

    # ── 4. Restore Configuration ──────────────────────────────────
    if [ -d "${BACKUP_DIR}/config" ]; then
        log "Restoring configuration..."
        cp -f "${BACKUP_DIR}/config/"* . 2>/dev/null || true
        log "Configuration restored"
    fi
fi

# Cleanup
rm -rf "${TEMP_DIR}"
if [ -n "${DECRYPTED_FILE}" ]; then
    rm -f "${DECRYPTED_FILE}"
fi

echo ""
log "═══════════════════════════════════════════════════════════"
log "Restore Complete"
log "═══════════════════════════════════════════════════════════"
log "  Restart the application to apply changes:"
log "    docker compose restart"
log "    # or"
log "    sudo systemctl restart ergovigilance"
log "═══════════════════════════════════════════════════════════"

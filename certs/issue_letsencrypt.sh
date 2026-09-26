#!/bin/bash
# ErgoVigilance — Let's Encrypt issuance for the TLS overlay (P0-3).
#
# Automates what certs/README.md used to document as manual copies, and
# gives renewal (real domain + public HTTP-01 required):
#
#   sudo ./certs/issue_letsencrypt.sh issue <domain> <email>
#   sudo ./certs/issue_letsencrypt.sh renew
#   sudo ./certs/issue_letsencrypt.sh install <domain>   # copy only, no certbot
#
# Requirements: certbot on the HOST, run as root (standalone binds :80),
# DNS A/AAAA record for <domain> pointing at this host with ports
# 80/443 reachable. The frontend container is stopped for the ACME
# challenge and restarted with the TLS overlay afterwards (trap on EXIT,
# so a failed issuance still brings the stack back up).
#
# Renewal cron (host):
#   0 3 * * * /path/to/ergovigilance/certs/issue_letsencrypt.sh renew >> /var/log/ergovigilance-certbot.log 2>&1
# ══════════════════════════════════════════════════════════════════

set -euo pipefail
cd "$(dirname "$0")/.."

CERTS_DIR="certs"
DOMAIN_FILE="${CERTS_DIR}/.domain"
FRONTEND_STOPPED=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log() { echo -e "${GREEN}[TLS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

usage() {
    cat <<'EOF'
Usage:
  issue_letsencrypt.sh issue <domain> <email>   Issue via certbot HTTP-01 standalone
  issue_letsencrypt.sh renew                    Renew last-issued cert, reinstall, restart
  issue_letsencrypt.sh install <domain>         Copy /etc/letsencrypt/live/<domain> into certs/ only
EOF
    exit 1
}

restart_frontend() {
    if [ "$FRONTEND_STOPPED" = true ]; then
        FRONTEND_STOPPED=false
        log "Starting frontend with TLS overlay..."
        docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d frontend \
            || warn "frontend restart failed — bring it up manually"
    fi
}
trap restart_frontend EXIT

stop_frontend_for_acme() {
    # HTTP-01 standalone needs host :80 free (default stack maps 8080->80,
    # but FRONTEND_PORT=80 or any other :80 listener would collide).
    if command -v docker >/dev/null 2>&1 \
        && docker compose ps --status running 2>/dev/null | grep -q frontend; then
        log "Stopping frontend for the ACME challenge (host :80)..."
        docker compose stop frontend
        FRONTEND_STOPPED=true
    fi
    if command -v ss >/dev/null 2>&1 && ss -ltn | grep -q ':80 '; then
        error "host port 80 is still occupied by another process — stop it first"
    fi
}

install_certs() {
    local domain="$1"
    local live="/etc/letsencrypt/live/${domain}"
    [ -f "${live}/fullchain.pem" ] && [ -f "${live}/privkey.pem" ] \
        || error "no certificate found at ${live}/ — run: $0 issue <domain> <email>"
    cp -f "${live}/fullchain.pem" "${CERTS_DIR}/fullchain.pem"
    cp -f "${live}/privkey.pem" "${CERTS_DIR}/privkey.pem"
    chmod 600 "${CERTS_DIR}/privkey.pem"
    printf '%s\n' "${domain}" > "${DOMAIN_FILE}"
    log "Installed ${domain} into ${CERTS_DIR}/fullchain.pem + privkey.pem"
}

[ "$(id -u)" -eq 0 ] || error "run as root (sudo) — certbot writes /etc/letsencrypt and standalone binds :80"

case "${1:-}" in
    issue)
        [ -n "${3:-}" ] || usage
        command -v certbot >/dev/null 2>&1 || error "certbot not installed (apt/dnf install certbot)"
        DOMAIN="$2"
        EMAIL="$3"
        stop_frontend_for_acme
        log "Requesting certificate for ${DOMAIN}..."
        certbot certonly --standalone --non-interactive --agree-tos \
            --email "${EMAIL}" -d "${DOMAIN}" --keep-until-expiring
        install_certs "${DOMAIN}"
        log "Issue complete (frontend restarts via trap)."
        ;;
    renew)
        command -v certbot >/dev/null 2>&1 || error "certbot not installed (apt/dnf install certbot)"
        [ -f "${DOMAIN_FILE}" ] || error "${DOMAIN_FILE} missing — run: $0 issue <domain> <email> first"
        DOMAIN="$(cat "${DOMAIN_FILE}")"
        stop_frontend_for_acme
        log "Renewing certificates (last issued for ${DOMAIN})..."
        certbot renew --quiet
        install_certs "${DOMAIN}"
        log "Renew complete (frontend restarts via trap)."
        ;;
    install)
        [ -n "${2:-}" ] || usage
        install_certs "$2"
        ;;
    *)
        usage
        ;;
esac

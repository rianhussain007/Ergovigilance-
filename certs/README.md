# TLS certificates

HTTPS is an opt-in overlay so the base stack (`docker compose up`) starts with
no certificate material on the host. Enable TLS with:

```bash
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

`docker-compose.tls.yml` binds `:443`, mounts the two files below into the
frontend container, and swaps in `ui_posture/nginx.tls.conf.example`, which
also redirects plain `:80` to `:443`. These two files must exist **before**
starting, because Docker creates a *directory* in place of a missing
bind-mount source and nginx then fails to load the certificate:

- `certs/fullchain.pem` — certificate chain (server cert first)
- `certs/privkey.pem` — matching private key, PEM-encoded, unencrypted

Neither file is committed (see `.gitignore`); place them on the host here.

## Self-signed pair (internal / LAN use)

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certs/privkey.pem -out certs/fullchain.pem \
  -subj "/CN=ergovigilance"
```

## Let's Encrypt / corporate CA

Copy the issued chain and key into this directory with the same names:

```bash
cp /etc/letsencrypt/live/<host>/fullchain.pem certs/fullchain.pem
cp /etc/letsencrypt/live/<host>/privkey.pem   certs/privkey.pem
```

Then restart the frontend: `docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d frontend`
(bind mounts — no rebuild needed). Verify with `curl -kI https://localhost/`.

## Running without TLS

Just omit the overlay:

```bash
docker compose up -d
```

The frontend then serves HTTP on `${FRONTEND_PORT:-8080}` with the image's
default nginx config.

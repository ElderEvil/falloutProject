# Deployment Guide

Complete guide for deploying Fallout Shelter in various environments.

## Admin session security

The embedded `/admin` interface uses an HTTPS-only production cookie with `SameSite=Strict` and a 30,008-second maximum age. Keep the admin route behind the same TLS reverse proxy as the API.

## Quick Start

```bash
# Local development
docker compose up -d
# Access: http://localhost:5173

# Production (Hetzner K3s)
# Push a verified release, then run the "Deploy to Hetzner" GitHub Actions workflow.
```

## Deployment Options

| Environment | Compose File | Description |
|-------------|--------------|-------------|
| Local Dev | `docker-compose.yml` | Hot reload, Mailpit, debug logging |
| Local Full | `docker-compose.local.yml` | Full stack local testing |
| Hetzner Production | `deployment/k3s/` | K3s deployments updated by the GitHub Actions workflow |

## Local Development

**File:** `docker-compose.yml` or `docker-compose.local.yml`

**Features:**
- Hot reload for backend and frontend
- Volume mounts for live code changes
- Mailpit for local dev email testing (no real emails are sent; see [Production Email: Mailcow on Hetzner](#production-email-mailcow-on-hetzner) for real transactional email)
- Debug logging enabled
- All ports exposed locally

**Usage:**
```bash
# Start all services
docker compose up -d

# Or use local config
docker compose -f docker-compose.local.yml up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Access Points:**
| Service | URL | Scope |
|---------|-----|-------|
| Frontend | http://localhost:5173 | Local dev |
| Backend API | http://localhost:8000 | Local dev |
| API Docs | http://localhost:8000/docs | Local dev |
| Dramatiq Worker | (background tasks) | Local dev |
| Mailpit | http://localhost:8025 | Local dev only (dev SMTP sink; no real emails) |

## Hetzner Production

The `backend` and `dramatiq-worker` deployments in the `fallout` namespace load environment variables from the
`backend-env` Kubernetes Secret. Deployment images are updated by the **Deploy to Hetzner** GitHub Actions workflow.
`ENVIRONMENT` must be `production`: the deployment verifies this before serving traffic, and admin session cookies are
marked Secure only in production.

Verify a running release (including its reported version and environment) with:

```bash
cd backend
uv run fo-cli ops check-ai --api-url https://fallout-api.evillab.tech --skip-chat --expect-environment production
```

### Release Preflight

1. Confirm the backend/frontend manifests, backend lockfile, and changelog have the same release version.
   Confirm `backend-logs-pvc` is `Bound` before rollout.
2. Build and publish the backend and frontend images for that version.
3. Confirm `backend-env` has all existing required application secrets plus these AI variables when Gateway is used:

   ```text
   PYDANTIC_AI_GATEWAY_API_KEY
   PYDANTIC_AI_GATEWAY_ROUTE
   PYDANTIC_AI_GATEWAY_BASE_URL
   OPENAI_API_KEY
   AI_PROVIDER
   AI_MODEL
   ENVIRONMENT=production
   ```

4. Leave RustFS variables unset if storage is intentionally unavailable; the backend now starts without it. Configure
   them when media uploads are required.
5. Run the **Deploy to Hetzner** workflow with the versioned backend image tag and migrations enabled when applicable.
6. Confirm rollout and health after deployment:

   ```bash
   kubectl -n fallout rollout status deployment/backend deployment/dramatiq-worker
   kubectl -n fallout get pods
   kubectl -n fallout logs deployment/backend --tail=100
   ```

7. Confirm the API log file is present on its persistent volume:

   ```bash
   kubectl -n fallout exec deployment/backend -- test -s /var/log/fallout_shelter/backend.log
   kubectl -n fallout get pvc backend-logs-pvc
   ```

The API writes JSON logs to a 1 GiB persistent volume. Files rotate at midnight and retain 14 days of rotated logs.
Kubernetes stdout logs remain enabled for immediate cluster diagnostics. The worker currently uses stdout until its
deployment manifest is added; do not provision an unused worker log volume.

The Gateway-specific secret patch and API verification steps are documented in
[Pydantic AI Gateway Setup](backend/PYDANTIC_AI_GATEWAY.md).

## Production Email: Mailcow on Hetzner

Local development uses **Mailpit** as a dev-only SMTP sink (no real emails leave the machine). Production uses a
self-hosted [Mailcow](https://docs.mailcow.email/) mail server running on a Hetzner Cloud VPS. Mailcow bundles
Postfix (MTA), Dovecot (IMAP), Rspamd (spam filtering), SOGo (webmail), and ACME TLS in a single Docker Compose
stack. The backend's `backend/app/core/email.py` sends via generic async SMTP (`aiosmtplib`), so switching from
Mailpit to Mailcow is a config + infrastructure change, not a code rewrite.

### Prerequisites

- A Hetzner Cloud VPS (CX22 or larger recommended; Mailcow needs ~4 GB RAM).
- A domain you control (e.g. `yourdomain.tld`). The VPS will serve mail for this domain.
- Docker and Docker Compose installed on the VPS (Mailcow ships its own compose stack).
- DNS access at your registrar to add MX, A, TXT, and other records.
- The backend's SMTP env vars (see [App → Mailcow SMTP connection](#app--mailcow-smtp-connection) below).

### Architecture

```
                  +---------------------------+
   Internet       |  Hetzner Cloud VPS        |
                  |                           |
   MX lookup ---> |  mail.yourdomain.tld      |
                  |    - Postfix (25/587/465) |
   App SMTP  ---> |    - Dovecot (993, IMAP)  |
   (587/465)      |    - Rspamd (11334, int.) |
                  |    - SOGo   (webmail UI)  |
                  |    - ACME   (Let's Encrypt)|
                  +---------------------------+
```

- **Inbound mail (25):** only if you need to receive replies at `yourdomain.tld` addresses. For send-only
  transactional email (verification, password reset), port 25 inbound can stay closed.
- **Submission (587 STARTTLS, 465 implicit TLS):** the backend connects here to send.
- **IMAP (993):** keep private unless you need to read mail from a client. The app does not read mail.

### DNS Setup

Point your domain at the VPS. All records are at your registrar (or wherever you host DNS for `yourdomain.tld`).

| Type  | Name                | Value / Target                              | TTL   | Purpose |
|-------|---------------------|---------------------------------------------|-------|---------|
| A     | `mail.yourdomain.tld` | `<VPS-IPv4>`                              | 300   | Mailcow host |
| MX    | `yourdomain.tld`    | `mail.yourdomain.tld` (priority 10)         | 3600  | Inbound mail routing |
| TXT   | `yourdomain.tld`    | `v=spf1 a:mail.yourdomain.tld ~all`         | 3600  | SPF (authorize VPS to send) |
| TXT   | `_dmarc.yourdomain.tld` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.tld; fo=1` | 3600 | DMARC policy |
| TXT   | `default._domainkey.yourdomain.tld` | *(DKIM value from Mailcow UI; see below)* | 3600 | DKIM signature verification |

**PTR / reverse DNS (critical for deliverability):** set the PTR record of the VPS IP to `mail.yourdomain.tld`.
In the Hetzner Cloud Console: **Server → Networking → IPv4 → Edit Reverse DNS** and enter `mail.yourdomain.tld`.
Without a matching PTR, major providers (Gmail, Outlook) will reject or spam-folder your mail.

**TLS:** Mailcow's ACME component obtains and renews Let's Encrypt certificates for `mail.yourdomain.tld`
automatically. No manual cert setup is needed.

### Provisioning Mailcow

1. **SSH into the VPS** and clone the Mailcow installer:

   ```bash
   ssh root@mail.yourdomain.tld
   apt update && apt install -y git curl
   git clone https://github.com/mailcow/mailcow-dockerized /opt/mailcow
   cd /opt/mailcow
   ```

2. **Generate the initial config:**

   ```bash
   ./generate_config.sh
   ```

   When prompted, set the hostname to `mail.yourdomain.tld` and choose a timezone.

3. **Start the stack:**

   ```bash
   docker compose pull
   docker compose up -d
   ```

   Mailcow takes a few minutes to initialize all containers on first run.

4. **Log in to the Mailcow UI** at `https://mail.yourdomain.tld` with the default admin credentials
   (`admin` / `moohoo`). **Change the admin password immediately.**

5. **Add the mail domain:** in the Mailcow UI, go to **Configuration → Mail Setup → Add Domain** and
   enter `yourdomain.tld`. Accept the defaults (DKIM selector `default`, key size 2048).

6. **Create a mailbox for the app:** in the Mailcow UI, go to **Configuration → Mail Setup → Mailboxes**
   and create a mailbox such as `no-reply@yourdomain.tld` with a strong password. This is the address the
   backend will authenticate as and send from.

7. **Publish the DKIM record:** in the Mailcow UI, go to **Configuration → Mail Setup → DNS**, find the
   DKIM entry for `yourdomain.tld`, and copy the TXT record value. Add it to your DNS as described in the
   [DNS Setup](#dns-setup) table above.

8. **Verify DNS propagation** before testing the app:

   ```bash
   dig MX yourdomain.tld +short
   dig A mail.yourdomain.tld +short
   dig TXT yourdomain.tld +short
   dig TXT default._domainkey.yourdomain.tld +short
   dig -x <VPS-IPv4> +short   # should return mail.yourdomain.tld
   ```

### App → Mailcow SMTP Connection

The backend reads SMTP settings from `backend/app/core/config.py`. Update the production environment
(the `backend-env` Kubernetes Secret, or the production `.env`) with:

```bash
SMTP_HOST=mail.yourdomain.tld
SMTP_PORT=587
SMTP_USER=no-reply@yourdomain.tld
SMTP_PASSWORD=<app-smtp-password>
SMTP_TLS=false
SMTP_SSL=true
EMAIL_FROM_ADDRESS=no-reply@yourdomain.tld
EMAIL_FROM_NAME=Fallout Shelter
FRONTEND_URL=https://fallout.evillab.tech
```

**TLS flag semantics (unintuitive, read carefully):**

The backend's `email.py` maps the env flags to `aiosmtplib` options in a way that is inverted from the
conventional naming:

| Env flag | aiosmtplib option | Meaning | Port |
|----------|-------------------|---------|------|
| `SMTP_TLS=true` | `use_tls=True` | Implicit TLS (connection starts encrypted) | **465** |
| `SMTP_SSL=true` | `start_tls=True` | STARTTLS (upgrade plaintext to encrypted) | **587** |

The names are backwards: `SMTP_TLS` means implicit TLS (port 465), `SMTP_SSL` means STARTTLS (port 587).
Pick the flag that matches the port you choose. The recommended setup is **port 587 with STARTTLS**, which
means `SMTP_SSL=true` and `SMTP_TLS=false` (as shown in the example above). If you prefer port 465 with
implicit TLS, set `SMTP_TLS=true` and `SMTP_SSL=false` instead. If both are `true`, `SMTP_TLS`
(implicit TLS) takes precedence; if both are `false`, no STARTTLS upgrade is requested and the
connection may remain plaintext. Prefer setting exactly one.

**`EMAIL_FROM_ADDRESS`** must be a real, existing mailbox on the Mailcow domain. Postfix will reject
messages whose envelope sender does not match an authenticated local mailbox.

**`FRONTEND_URL`** is used to build the verification and password-reset links in email bodies
(`verify_email.html`, `reset_password.html`, `password_changed.html`). In production this must be the real
public frontend origin (e.g. `https://fallout.evillab.tech`), not `http://localhost:5173`.

### Firewall and Security

Open only the ports the app and the internet need:

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 587  | TCP      | Inbound from the app only | Submission (STARTTLS) |
| 465  | TCP      | Inbound from the app only | Submission (implicit TLS), if used |
| 25   | TCP      | Inbound (optional) | Receiving inbound mail; close if send-only |
| 443  | TCP      | Inbound | Mailcow UI + ACME |
| 80   | TCP      | Inbound | ACME HTTP-01 challenge (or use DNS-01 via `ACME_DNS_CHALLENGE=y` and omit this port) |
| 993  | TCP      | Inbound (optional) | IMAP; close unless you need a mail client |

In the Hetzner Cloud Firewall, restrict 587/465 to the app's IP range (the K3s node IPs) rather than
`0.0.0.0/0`. Keep the Mailcow admin UI behind its own strong password and, if possible, restrict access
to known admin IPs.

Do not expose Dovecot IMAP (993) publicly unless you have a specific need to read mail from a client.
The app sends only; it never reads incoming mail.

### Deliverability Checklist

Before going live, verify every item:

- [ ] **SPF** TXT record published and includes `mail.yourdomain.tld`.
- [ ] **DKIM** TXT record published (value copied from the Mailcow UI).
- [ ] **DMARC** TXT record published (at minimum `p=none` to start, then `p=quarantine` or `p=reject`).
- [ ] **PTR / rDNS** set on the VPS IP in the Hetzner Cloud Console, matching `mail.yourdomain.tld`.
- [ ] **TLS** certificate issued by Mailcow's ACME component (check the Mailcow UI).
- [ ] **Test send** from the app: trigger a verification email and confirm it lands in the inbox, not spam.
- [ ] **Health check:** hit the backend's detailed health endpoint and confirm `smtp` reports `healthy`:

  ```bash
  curl https://<your-api-host>/healthcheck?detailed=true | jq .services.smtp
  ```

  Replace `<your-api-host>` with your deployed backend API hostname (e.g. the value of `PRODUCTION_API_URL`).

  The `check_smtp` method in `backend/app/services/health_check.py` connects, authenticates, and quits.

- [ ] **Warm-up:** new IPs and domains start with low sending reputation. Keep volume low for the first
  few days (a handful of verification emails per hour is fine). Hetzner does not block outbound 25 on
  request, but some receiving servers will throttle unknown senders initially.

### Troubleshooting

**Emails land in spam or are rejected.**
Check SPF, DKIM, DMARC, and PTR. All four must be correct. Use `dig` to verify each record, and test with
a service like [mail-tester.com](https://www.mail-tester.com/) to get a spam-score report.

**Connection refused on 587 or 465.**
Confirm the Hetzner Cloud Firewall allows inbound TCP on the port from the app's IP. Confirm Mailcow's
Postfix container is running (`docker compose ps` inside `/opt/mailcow`). Confirm `SMTP_HOST` resolves to
the VPS IP.

**Authentication failed.**
Verify `SMTP_USER` is the full mailbox address (`no-reply@yourdomain.tld`, not just `no-reply`). Verify
`SMTP_PASSWORD` matches the mailbox password set in the Mailcow UI. Check the Mailcow UI logs under
**Monitoring → Logs** for Postfix authentication errors.

**TLS mismatch / handshake failure.**
The `SMTP_TLS` and `SMTP_SSL` flags are inverted from conventional naming. For port 587 (STARTTLS), set
`SMTP_SSL=true` and `SMTP_TLS=false`. For port 465 (implicit TLS), set `SMTP_TLS=true` and
`SMTP_SSL=false`. If both are `true`, `SMTP_TLS` (implicit TLS) wins; if both are `false`, no
STARTTLS upgrade is requested and the connection may be plaintext. Prefer exactly one.

**Health check reports SMTP unhealthy.**
Run the detailed health endpoint and inspect the `smtp` entry. The error message includes the host, port,
and the underlying exception. Common causes: wrong port for the TLS mode, firewall blocking the port, or
the Mailcow stack not fully started yet.

## Environment Configuration

### Required Variables

**Security (CRITICAL):**
```bash
SECRET_KEY=             # Generate: openssl rand -hex 32
FIRST_SUPERUSER_PASSWORD=  # Admin password
POSTGRES_PASSWORD=      # Database password
```

**Database:**
```bash
POSTGRES_SERVER=db      # Service name in Docker Compose
POSTGRES_USER=postgres
POSTGRES_DB=fallout_db
```

**URLs (for Hetzner/production):**
```bash
FRONTEND_URL=https://fallout.evillab.tech
PRODUCTION_API_URL=https://fallout-api.evillab.tech
```

**AI Provider:**
```bash
PYDANTIC_AI_GATEWAY_API_KEY=... # Recommended: routes chat and Pydantic AI agents through Gateway
PYDANTIC_AI_GATEWAY_ROUTE=...   # Optional custom Gateway provider or routing-group identifier
PYDANTIC_AI_GATEWAY_BASE_URL=... # Regional Gateway proxy, e.g. https://gateway-eu.pydantic.dev/proxy
AI_PROVIDER=openai               # or: anthropic; Ollama is local development only
AI_MODEL=gpt-4o
OPENAI_API_KEY=sk-...            # Still required for OpenAI image generation, TTS, and Whisper
```

The Gateway key is used for chat/text model traffic only. Direct OpenAI access remains intentionally configured for
the native image and audio APIs; do not remove `OPENAI_API_KEY` if those features are enabled.

For the complete provider, local verification, Logfire, and Hetzner procedure, see
[Pydantic AI Gateway Setup](backend/PYDANTIC_AI_GATEWAY.md).

**Activation:**

- **Local:** add `PYDANTIC_AI_GATEWAY_API_KEY` to `backend/.env`, then restart the backend.
- **Hetzner:** the Kubernetes backend reads the `backend-env` Secret in the `fallout` namespace. Add the Gateway key
  without replacing existing secret values, then restart the backend and worker deployments:

  ```bash
  kubectl -n fallout patch secret backend-env --type merge \
    -p '{"stringData":{"PYDANTIC_AI_GATEWAY_API_KEY":"<gateway-key>","PYDANTIC_AI_GATEWAY_ROUTE":"<route>","PYDANTIC_AI_GATEWAY_BASE_URL":"<regional-proxy-url>"}}'
  kubectl -n fallout rollout restart deployment/backend deployment/dramatiq-worker
  ```

  Configure the selected upstream provider/model in Pydantic AI Gateway before enabling the key. The backend will log
  `AI initialized via Gateway (<provider>/<model>)` after a successful rollout.

### Environment Files

| File | Purpose |
|------|---------|
| `.env.example` | Development template |
| `.env` | Your local config (never commit!) |

### Docker vs Native Services

When using Docker Compose, use **service names**:
```bash
POSTGRES_SERVER=db
REDIS_HOST=redis
```

When running natively:
```bash
POSTGRES_SERVER=localhost
REDIS_HOST=localhost
```

## CI/CD Automation

### Semantic Release

Every push to `master` triggers:
1. Commit analysis for version bump
2. CHANGELOG.md update
3. Git tag creation
4. GitHub release publication

There is **no root `package.json`**: `.github/workflows/release.yml` runs a pinned
`npx --package semantic-release@...` invocation (installing the non-bundled
`@semantic-release/changelog`/`@semantic-release/exec`/`@semantic-release/git` plugins the same way),
so no `npm ci` or root lockfile is needed. Backend/frontend versions are synchronized by
`.releaserc.json` (`@semantic-release/exec` runs `uv --directory backend version`; `@semantic-release/npm`
updates `frontend/package.json` with `npmPublish: false`).

### Docker Image Builds

Images built on push to `master` (when files change), org from the `DOCKER_USERNAME` secret:
- `$DOCKER_USERNAME/fo-shelter-be:latest`, `v1.x.x`
- `$DOCKER_USERNAME/fo-shelter-fe:latest`, `v1.x.x`

### Commit Conventions

| Type | Version Bump | Example |
|------|--------------|---------|
| `feat:` | Minor (1.X.0) | `feat: add dweller mood system` |
| `fix:` | Patch (1.0.X) | `fix: correct resource calculation` |
| `feat!:` | Major (X.0.0) | `feat!: redesign API endpoints` |
| `docs:` | None | `docs: update deployment guide` |

### GitHub Actions Setup

**Required Secrets:**
```
DOCKER_USERNAME  - Docker Hub username
DOCKER_PASSWORD  - Docker Hub access token
```

**Required Variables:**
```
PRODUCTION_API_URL  - Frontend build API URL (e.g., https://fallout-api.evillab.tech)
```

**Setup:** GitHub > Repository > Settings > Secrets and variables > Actions

## Database Migrations

### Automatic (Recommended)
Migrations run on container startup:
```yaml
command: sh -c "uv run alembic upgrade head && uv run uvicorn main:app ..."
```

### Manual
```bash
# Run migrations
docker compose exec fastapi uv run alembic upgrade head

# Rollback one migration
docker compose exec fastapi uv run alembic downgrade -1

# Create new migration
docker compose exec fastapi uv run alembic revision --autogenerate -m "description"
```

## Health Checks

**Basic:**
```bash
curl https://your-api-domain.com/healthcheck
# {"status":"ok"}
```

**Detailed:**
```bash
curl https://your-api-domain.com/healthcheck?detailed=true
# {"status":"ok","services":{"db":"ok","redis":"ok",...}}
```

## Backup & Restore

### Database Backup
```bash
# Backup
docker compose exec db pg_dump -U postgres fallout_db > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker compose exec -T db psql -U postgres -d fallout_db
```

## Troubleshooting

### Services Won't Start
```bash
docker compose logs
docker compose config
```

### Database Connection Errors
```bash
docker compose ps db
docker compose exec db psql -U postgres -d fallout_db -c "SELECT 1"
```

### Frontend Connection Errors
- Check `VITE_API_BASE_URL` was set during build
- Verify reverse proxy configuration
- Check browser console for CORS errors

### Background Tasks Not Running
```bash
docker compose ps redis
docker compose logs dramatiq_worker
```

## Security Checklist

- [ ] Strong, unique passwords
- [ ] `SECRET_KEY` rotated from default
- [ ] HTTPS enabled (via reverse proxy)
- [ ] Firewall configured
- [ ] `.env` files never committed
- [ ] Regular database backups
- [ ] Rate limiting enabled

## Performance Notes

### Dockerfile Optimizations

**Backend:** Use `--no-dev --no-cache` for production builds:
```dockerfile
RUN uv sync --frozen --no-dev --no-install-project --no-cache
```

**Frontend:** Use multi-stage builds with production-only dependencies:
```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm run build

FROM node:22-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist .
CMD ["serve", "-s", ".", "-l", "3000"]
```

**Layer Ordering:** Copy dependency manifests before source code to maximize cache hits:
```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
```

**BuildKit Cache:** Enable registry caching in CI:
```yaml
cache_from:
  - type=registry,ref=${DOCKER_USERNAME}/fo-shelter-be:cache
cache_to:
  - type=registry,ref=${DOCKER_USERNAME}/fo-shelter-be:cache,mode=max
```

### .dockerignore Recommendations

**Backend:**
```text
__pycache__
*.pyc
.pytest_cache
.coverage
htmlcov/
.env
.venv
.git
**/tests/
```

**Frontend:**
```text
node_modules
dist
.git
.env
.env.local
coverage
tests
```

## Related Documentation

- [Security Guide](SECURITY_GUIDE.md) - Security best practices

---

**Last Updated:** 2026-08-24

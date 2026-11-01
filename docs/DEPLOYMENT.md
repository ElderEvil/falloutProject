# Deployment Guide

Complete guide for deploying Fallout Shelter in various environments.

## Admin session security

The embedded `/admin` interface uses an HTTPS-only production cookie with `SameSite=Strict` and a 30,008-second maximum age. Keep the admin route behind the same TLS reverse proxy as the API.

## Admin support interface

Only active, non-deleted superusers can sign in to `/admin`; access is rechecked on each request. The panel defaults to dark mode and stores the dark/light/system choice in the browser.

Use a row's detail page or select one row for support actions: verify email, promote/demote a superuser, deactivate/reactivate or soft-delete a user, pause/resume a vault, cancel training, or recall an explorer. Each action requires POST confirmation. Provider-only accounts need to add a password from their profile before using the admin login.

Deactivation blocks account access, clears recovery links, and pauses vaults without marking the account as deleted. Reactivation restores access and leaves vaults paused for the owner to resume. Soft-delete remains a separate action; Reactivate cannot restore a deleted account.

Only the first superuser can create or promote administrators, demote them, or perform administrative account actions against other administrators. Other superusers can still manage regular users. The same restrictions apply to the user API. The first account cannot be deactivated, deleted, or demoted.

The first-superuser marker is internal and fixed to the account ID; email changes and later promotions cannot transfer it. Migration `b4d8f2a6c0e1` backfills the configured `FIRST_SUPERUSER_EMAIL` when it matches an existing superuser, otherwise the earliest-created existing superuser, and enforces that at most one account has the marker. Apply the migration before running the updated application.

Soft-deleting a user blocks sign-in, clears recovery links, and pauses their vaults in one transaction. It retains account and game data and cannot target the current admin. Incident controls support up to 50 selected vaults or an explicitly confirmed global change. Operational records are read-only to keep their state transitions inside gameplay services; catalog instances are also read-only because their data comes from catalog factories. Profile bio/avatar editing and existing exports remain available; credentials and AI audit views cannot be exported.

The admin PostgreSQL concurrency test is opt-in: set `ADMIN_TEST_DATABASE_URI` to a dedicated, Alembic-migrated `postgresql+asyncpg` database, then run `uv run pytest app/tests/integration/test_admin_user_actions_pg.py` from `backend/`. It skips when unset and rejects the application's database name; never point it at a shared or production database.

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

Traffic enters through the Traefik ingress in `deployment/k3s/ingress.yaml`: `fallout.evillab.tech` routes to
`frontend-service` and `fallout-api.evillab.tech` to `backend-service`, with cert-manager issuing the
`fallout-ingress-tls` certificate. There is no in-cluster Caddy.

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
   Migrations run in a dedicated Job using the target image before application images change. A failed Job aborts rollout.
   Enable `maintenance_mode` for incompatible schema changes, including the upgrade from v2.165.1 that drops
   `dweller.is_adult`: the workflow records API/worker replica counts, stops both writers, creates and verifies a
   PostgreSQL dump under the server user's `~/fallout-backups/`, migrates, then restores the replicas on the new image.
   Backup creation, archive listing, and transfer share a 120-second deadline (with a 10-second termination grace).
   The archive is listed inside the PostgreSQL pod from a temporary file, without streaming it back into an
   interactive `kubectl exec`. The server receives a `.partial` file and renames it to `.dump` only after verification
   and transfer succeed. A backup error or timeout restores the recorded API/worker replica counts and aborts before
   migration; retain any `.partial` file for diagnosis, but do not use it as a verified backup. Archive listing checks
   readability, not full restoreability; a separate isolated restore drill is still required.
   Plan a brief API maintenance window. Migration failure keeps writers stopped for inspection; retain the backup
   and restore the previous schema/image together rather than restarting old code against a changed schema.
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

### Runner cannot reach the host

The workflow's **Probe SSH connectivity** step fails when GitHub-hosted runners cannot complete an SSH session to the
production host. Read its output before changing anything: it prints a host fingerprint, DNS resolution, raw TCP 22
reachability, and verbose `ssh` output. `TCP 22: open` with a completed key exchange means the network path is fine
and the problem is in authentication, not routing.

Read the failure by where it stops:

| Verbose output stops at | Meaning |
|---|---|
| `Connecting to ...` then `timed out` | Packets never arrive: Hetzner Cloud Firewall, or a fail2ban DROP on that source |
| `kex_exchange_identification` / `Connection closed` before keys | The host answered and refused the handshake |
| Keys exchanged, then `Connection closed by remote host` after ~120s | Authentication never completed. 120s is sshd's `LoginGraceTime`; the client's auth packets were dropped mid-connection (a ban applied to an established session does this) or auth stalled |

Confirm the runner is talking to the intended machine by comparing the host key it prints with
`ssh-keyscan -t ed25519 <host> | ssh-keygen -lf -`. To verify which value a secret holds without printing it,
compare `printf '%s' "<candidate>" | sha256sum | cut -c1-12` against the probe's fingerprint.

The usual cause on this host is **fail2ban**: the sshd jail runs `mode = aggressive`, `maxretry = 3`, `bantime = 1h`,
and its default action drops banned packets, so a ban reads as a timeout. Aggressive mode counts "Timeout before
authentication" and banner-exchange events as failures, and cloud CI addresses are shared — a GitHub runner can
inherit a ban earned by unrelated traffic from the same address. This was confirmed by experiment: with
`fail2ban` stopped the identical probe connected immediately and the workflow passed.

Keep the sshd jail in `mode = normal` with `maxretry` of at least 5. `aggressive` is not worth it on a host that
is scanned continuously, and banning shared cloud ranges breaks CI. Confirm the diagnosis by testing the jail's ban
list against GitHub's `actions` ranges (`https://api.github.com/meta`) — runner addresses do appear there. Inspect
and clear bans with `sudo fail2ban-client status sshd` and `sudo fail2ban-client unban --all`; bans persist in
fail2ban's database across restarts, so a restart alone does not release them. Whitelisting the GitHub Actions
egress ranges is impractical at ~7000 CIDRs, so relax the jail instead. Leaving `fail2ban` stopped is not a fix —
the host sees thousands of brute-force attempts and would be unprotected.

When the pipeline is blocked, the same steps can be replayed by hand — the workflow is a scripted version of them.
Stop the writers, run the migration Job with the target image, set the images (including the backend's
`run-migrations` init container), restore the writers, then verify. Migrations deadlock against live traffic on
this database, so use `maintenance_mode=true`: an additive `ALTER TABLE` can still wait on a lock the running API
holds and abort the upgrade.

### Room layout data backfills

The unit-grid release changed how vault rooms are placed and extended. Existing vaults keep their previous
coordinates and duplicate rooms until these backfills run once against the deployed database. Both commands are
dry-run by default, print a per-vault summary, and are idempotent, so re-running them is safe.

```bash
cd backend

# 1. Re-lay vaults onto the unit grid: door at the origin, elevator shaft beside it,
#    resource rooms left of the shaft, every other room to the right.
uv run fo-cli backfill backfill-vault-layout --all-active           # preview
uv run fo-cli backfill backfill-vault-layout --all-active --apply   # persist

# 2. Merge adjacent same-name/same-tier rooms into extended rooms.
uv run fo-cli backfill merge-rooms --all-active           # preview
uv run fo-cli backfill merge-rooms --all-active --apply   # persist
```

Scope a single vault with `--vault <uuid>` instead of `--all-active`: `--all-active` skips deleted vaults, while
`--vault <uuid>` targets that vault directly and fails when it is missing or deleted. `backfill-vault-layout
--apply` refuses to commit a layout that still has overlaps, floating rooms, or a floor wider than the grid. Run
`backfill-vault-layout` before `merge-rooms` when both are needed.

To run them against a cluster, execute inside the backend pod so it uses the deployed database and image:

```bash
kubectl -n fallout exec deployment/backend -- uv run fo-cli backfill backfill-vault-layout --all-active --apply
kubectl -n fallout exec deployment/backend -- uv run fo-cli backfill merge-rooms --all-active --apply
```

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

  The `check_smtp` method in `backend/app/core/health_check.py` connects, authenticates, and quits.

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
AI_PROVIDER=openai               # Ollama and LM Studio are local development only
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

### Branch protection and release writes

`master` protection applies to administrators; force pushes and branch deletion are disabled.
Developer pushes to `master` are also rejected by the local `scripts/pre-push` hook (install it using
the README instructions). The local hook is not installed by the release workflow.

A server-side pull-request requirement is **not enabled**: the existing semantic-release workflow
uses `GITHUB_TOKEN` and `@semantic-release/git` to write the synchronized version/changelog commit
directly to `master`. This personal repository cannot configure the attempted GitHub Actions app
bypass for that requirement. Admin enforcement alone does not reject ordinary direct pushes.

Before enabling a server-side PR requirement, change the release write path to use reviewed PRs,
or establish supported release-only authentication/bypass. Do not exempt the maintainer's normal
token or disable protection around a release; that would reopen direct pushes for ordinary work.
Preserve published release commits, tags and artifacts when correcting an accidental push.

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

### Content seeding
Game content (quests, objectives, places) loads from JSON at **backend startup**, so a deploy's rollout
picks up new rows automatically. Seeding is **insert-only** — an existing row is never updated — so
**editing an existing seed's content requires a data migration** (or a manual `UPDATE`); re-running the
seeder will not change rows that already exist.

## Health Checks

**Basic:**
```bash
curl https://your-api-domain.com/healthcheck
# {"status":"ok"}
```

**Detailed:**
```bash
curl https://your-api-domain.com/healthcheck?detailed=true
# {"status":"ok","services":{"postgresql":{"status":"healthy",...},"redis":{"status":"healthy",...},...}}
```

**Readiness (Kubernetes):**
```bash
curl -fsS https://your-api-domain.com/readiness
# {"status":"ready","services":{"postgresql":{...},"redis":{...}}}
```

Readiness checks only PostgreSQL and Redis and returns HTTP 503 when either is unavailable. Optional
integrations (RustFS, local AI, SMTP) and the worker broker are excluded so they cannot remove an
otherwise healthy API pod from service. Liveness stays on `/healthcheck`. See
[`deployment/k3s/README.md`](../deployment/k3s/README.md) for probe wiring, the checked-in worker
manifest and the deploy order.

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

### Production images

The backend uses a multi-stage build from the repository root. The root `.dockerignore` excludes
tests, local environments, caches, and environment files; there is no separate backend ignore file.
Only runtime dependency groups are installed with `uv sync --frozen --no-default-groups`.
The project and its `fo-cli` entry point are installed during the build.

The runtime image sets `UV_NO_SYNC=1`, `UV_NO_DEFAULT_GROUPS=1`, and `UV_NO_CACHE=1`.
Existing `uv run` commands for the API, workers, and migrations use the baked environment without
installing packages or writing a home-directory cache. Rebuild the image after dependency changes.
Local source mounts still work; testing tools remain in the host development environment.

The frontend runtime contains compiled `dist` assets and its static server. Build tools stay in the
build stage. Both Dockerfiles copy dependency manifests before source to retain dependency caching.

`frontend/serve.json` keeps HTML revalidated, caches assets for seven days, and caches content-addressed
room-grid and content-addressed wasteland scene WebP images for one year with `immutable`.
Regenerate scenes with `uv run --project backend python scripts/import_wasteland_scenes.py /path/to/backgrounds`
and commit `frontend/public/assets/wasteland-scenes/` together with
`frontend/src/modules/exploration/models/wasteland-scenes.json`. The backend's public `/static` mount uses a
seven-day lifetime with ETag/Last-Modified revalidation; catalog files can be replaced in place.
Rebuild compact grid images after changing room artwork with
`uv run --project backend python scripts/optimize_room_grid_images.py` from the repo root. Commit the
generated `frontend/public/assets/room-grid/` files and `roomGridImages.json` together; full-size sources
remain available to detail views and as fallbacks.

CI builds the backend image and runs `scripts/check_backend_image.py` before publishing. The check
runs as the image user, offline and with a read-only root filesystem, and verifies that tests and
development packages are absent, runtime assets exist, API/worker modules import, and API, migration,
worker, scheduler, and CLI entry points work. Run the same check locally:

```bash
podman build -t fallout-backend-check -f backend/Dockerfile .
podman run --rm -i --network=none --read-only \
  --tmpfs /tmp --tmpfs /var/log/fallout_shelter:mode=1777 \
  --entrypoint uv fallout-backend-check run --offline python - < scripts/check_backend_image.py
```

The database-backed application tests continue to run in backend CI; the image check does not apply
migrations or contact infrastructure.

## Related Documentation

- [Security Guide](SECURITY_GUIDE.md) - Security best practices

---

**Last Updated:** 2026-08-24

## Social sign-in (Google / GitHub)

Each provider is enabled only when its client ID **and** secret are present; a
missing pair disables that provider without blocking startup.

1. Register the clients:
   - Google: Google Auth Platform → Clients → Web application, redirect
     `https://fallout-api.evillab.tech/api/v1/auth/oauth/google/callback`.
   - GitHub: OAuth App, callback
     `https://fallout-api.evillab.tech/api/v1/auth/oauth/github/callback`.
2. Add repository secrets: `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`,
   `OAUTH_GITHUB_CLIENT_ID`, `OAUTH_GITHUB_CLIENT_SECRET`, and optionally
   `OAUTH_REDIRECT_BASE` (GitHub Actions forbids the `GITHUB_` prefix). (defaults to `https://fallout-api.evillab.tech`).
3. The deploy workflow writes them into the `backend-env` Secret alongside the
   existing settings; `kubectl -n fallout set env` picks them up. To patch
   manually:

   ```bash
   kubectl -n fallout create secret generic backend-env \
     --from-literal=GOOGLE_CLIENT_ID=... \
     --from-literal=GOOGLE_CLIENT_SECRET=... \
     --from-literal=GITHUB_CLIENT_ID=... \
     --from-literal=GITHUB_CLIENT_SECRET=... \
     --from-literal=OAUTH_REDIRECT_BASE=https://fallout-api.evillab.tech \
     --dry-run=client -o yaml | kubectl apply -f -
   kubectl -n fallout rollout restart deployment/backend deployment/dramatiq-worker
   ```

4. `GET /api/v1/auth/oauth/providers` reports which pairs are live.


## JWT purpose validation rollout

Access and refresh JWTs require distinct `type` claims (`access` and `refresh`).
Every JWT consumer requires `exp`, `sub`, and its exact purpose, using the configured
signing key and algorithm. HTTP/SSE and WebSocket authentication accept access tokens
only; refresh still requires the current token stored in Redis.

Deploying this change rejects previously issued, untyped access and refresh tokens.
Existing players must sign in once again. The frontend clears rejected credentials
and returns to login; no compatibility fallback should accept untyped tokens.
Keep the signing key unchanged: existing typed email-verification and password-reset
links remain valid subject to their expiry and stored-token/one-use checks. No schema
migration, Redis flush, or key rotation is required. During a rolling deployment,
older API replicas still accept untyped credentials until they have been replaced.

This follows [RFC 8725 §3.12](https://www.rfc-editor.org/rfc/rfc8725.html#section-3.12),
which requires mutually exclusive validation rules for different JWT uses.

## Postgres observability and query profiling

The production Postgres manifest enables `pg_stat_statements`, `auto_explain`, and
`track_io_timing`. These settings require a Postgres restart and a one-time extension
creation. Run this in a maintenance window:

1. Back up the database and record replica counts, then scale API and workers down:

   ```bash
   kubectl -n fallout scale deployment/backend deployment/dramatiq-worker --replicas=0
   ```

2. Patch only the Postgres args; do not `kubectl apply` the full manifest over the live
   deployment, whose environment wiring may differ:

   ```bash
   kubectl -n fallout patch deployment postgres --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","args":["-c","shared_preload_libraries=pg_stat_statements,auto_explain","-c","track_io_timing=on","-c","auto_explain.log_min_duration=200ms","-c","auto_explain.log_analyze=off","-c","pg_stat_statements.max=5000","-c","pg_stat_statements.track=all"]}]}}}}'
   kubectl -n fallout rollout status deployment/postgres --timeout=300s
   ```

3. Create the extension and reset the baseline:

   ```bash
   kubectl -n fallout exec deploy/postgres -- psql -U postgres -d fallout_db -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements;'
   kubectl -n fallout exec deploy/postgres -- psql -U postgres -d fallout_db -c 'SELECT pg_stat_statements_reset();'
   ```

4. Restore the API/worker replica counts. Verify `SHOW shared_preload_libraries`,
   `SHOW track_io_timing`, and the `pg_stat_statements` view. Slow plans are emitted
   to the Postgres pod logs through `auto_explain`.

5. After collecting a representative window, review the top statements and slow plans
   before changing query shape or indexes.

`deployment/k3s/postgres-deployment.yaml` is the source-of-truth manifest; it is pinned
to the live `postgres:18-alpine` image and `/var/lib/postgresql` data mount to avoid a
data-path change on future applies.

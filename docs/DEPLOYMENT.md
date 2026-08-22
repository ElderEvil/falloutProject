# Deployment Guide

Complete guide for deploying Fallout Shelter in various environments.

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
- Mailpit for email testing (no real emails)
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
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Dramatiq Worker | (background tasks) |
| Mailpit | http://localhost:8025 |

## Hetzner Production

The `backend` and `dramatiq-worker` deployments in the `fallout` namespace load environment variables from the
`backend-env` Kubernetes Secret. Deployment images are updated by the **Deploy to Hetzner** GitHub Actions workflow.

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

**Last Updated:** 2026-05-19

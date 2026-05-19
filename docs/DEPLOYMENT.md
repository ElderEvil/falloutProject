# Deployment Guide

Complete guide for deploying Fallout Shelter in various environments.

## Quick Start

```bash
# Local development
docker compose up -d
# Access: http://localhost:5173

# TrueNAS staging
# See docs/deployment/TRUENAS_SETUP.md
```

## Deployment Options

| Environment | Compose File | Description |
|-------------|--------------|-------------|
| Local Dev | `docker-compose.yml` | Hot reload, Mailpit, debug logging |
| Local Full | `docker-compose.local.yml` | Full stack local testing |
| TrueNAS | [examples/docker-compose.truenas.yml](examples/docker-compose.truenas.yml) | Staging/production on TrueNAS |

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

## TrueNAS Staging

**Complete Guide:** [deployment/TRUENAS_SETUP.md](deployment/TRUENAS_SETUP.md)

**Summary:**
- Production-like environment on TrueNAS Scale
- Pre-built images from Docker Hub
- Automated updates via semantic-release
- Nginx Proxy Manager for SSL/reverse proxy
- External domains (fallout.evillab.dev)

**Quick Setup:**
```bash
# On TrueNAS
mkdir -p /mnt/dead-pool/apps/fallout-shelter/config
cd /mnt/dead-pool/apps/fallout-shelter/config

# Download configs
curl -o compose.yml https://raw.githubusercontent.com/ElderEvil/falloutProject/master/docs/examples/docker-compose.truenas.yml
curl -O https://raw.githubusercontent.com/ElderEvil/falloutProject/master/docs/examples/.env.staging.example
mv .env.staging.example .env

# Edit .env with your values
nano .env

# Deploy
docker compose up -d
```

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

**URLs (for TrueNAS/production):**
```bash
FRONTEND_URL=https://fallout.evillab.dev
API_URL=https://fallout-api.evillab.dev
```

**AI Provider:**
```bash
AI_PROVIDER=openai      # or: anthropic, ollama
AI_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

### Environment Files

| File | Purpose |
|------|---------|
| `.env.example` | Development template |
| `docs/examples/.env.staging.example` | TrueNAS/staging template |
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

### Docker Image Builds

Images built on push to `master` (when files change):
- `elerevil/fo-shelter-be:latest`, `v1.x.x`
- `elerevil/fo-shelter-fe:latest`, `v1.x.x`

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
PRODUCTION_API_URL  - Frontend build API URL (e.g., https://fallout-api.evillab.dev)
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
  - type=registry,ref=${DOCKER_USERNAME}/fastapi:cache
cache_to:
  - type=registry,ref=${DOCKER_USERNAME}/fastapi:cache,mode=max
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

- [TrueNAS Setup](deployment/TRUENAS_SETUP.md) - TrueNAS-specific guide
- [Security Guide](SECURITY_GUIDE.md) - Security best practices

---

**Last Updated:** 2026-05-19

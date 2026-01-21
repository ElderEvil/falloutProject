# TrueNAS Staging Deployment Guide

Complete guide for deploying Fallout Shelter to TrueNAS Scale using Docker Compose.

## Overview

**Infrastructure:**
- Host: TrueNAS Scale
- Path: `/mnt/dead-pool/apps/fallout-shelter/config/`
- Images: Docker Hub (automated by semantic-release)
- Reverse Proxy: Nginx Proxy Manager

**Domains:**
- Frontend: `https://fallout.evillab.dev`
- Backend API: `https://fallout-api.evillab.dev`
- Media (MinIO): `https://fallout-media.evillab.dev`

## Prerequisites

- TrueNAS Scale installed
- Nginx Proxy Manager configured (see [NGINX_PROXY_MANAGER_SETUP.md](NGINX_PROXY_MANAGER_SETUP.md))
- Domain names configured with DNS pointing to TrueNAS
- Docker Hub access (public images, no login required)

## Directory Structure

On TrueNAS:
```
/mnt/dead-pool/apps/fallout-shelter/
├── config/
│   ├── .env                    # Environment variables
│   ├── compose.yml            # Docker Compose config
│   └── truenas-app.yml        # TrueNAS Apps integration (optional)
└── volumes/                   # Auto-created by Docker
    ├── postgres-data/
    ├── minio_data/
    └── redis-data/
```

## Initial Setup

### Step 1: Create Directory Structure

```bash
sudo mkdir -p /mnt/dead-pool/apps/fallout-shelter/config
cd /mnt/dead-pool/apps/fallout-shelter/config
```

### Step 2: Create Environment File

```bash
# Download example from repo
sudo curl -O https://raw.githubusercontent.com/ElderEvil/falloutProject/master/docs/examples/.env.staging.example

# Rename and edit
sudo mv .env.staging.example .env
sudo nano .env
```

**Required Changes in .env:**
| Variable | Action |
|----------|--------|
| `SECRET_KEY` | Generate with `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Strong password |
| `FIRST_SUPERUSER_PASSWORD` | Admin password |
| `MINIO_ROOT_PASSWORD` | Min 8 characters |
| `OPENAI_API_KEY` | Your API key |
| URLs | Verify they match your domains |

### Step 3: Create Docker Compose File

```bash
# Download from repo
sudo curl -o compose.yml https://raw.githubusercontent.com/ElderEvil/falloutProject/master/docs/examples/docker-compose.truenas.yml
```

### Step 4: Configure Nginx Proxy Manager

Follow the guide: [NGINX_PROXY_MANAGER_SETUP.md](NGINX_PROXY_MANAGER_SETUP.md)

Create proxy hosts for:
| Domain | Target | Notes |
|--------|--------|-------|
| `fallout.evillab.dev` | `http://fallout_frontend:3000` | Frontend |
| `fallout-api.evillab.dev` | `http://fallout_api:8000` | Backend API |
| `fallout-media.evillab.dev` | `http://fallout_minio:9000` | MinIO with CORS |

### Step 5: Deploy

```bash
cd /mnt/dead-pool/apps/fallout-shelter/config

# Pull latest images
docker compose pull

# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f fastapi
```

### Step 6: Verify Deployment

```bash
# Health check
curl https://fallout-api.evillab.dev/healthcheck
# Expected: {"status":"ok"}

# Check frontend
curl -I https://fallout.evillab.dev
# Expected: HTTP 200

# Test login at https://fallout.evillab.dev
```

## TrueNAS Apps Integration (Optional)

TrueNAS Scale Apps can reference external compose files:

**File:** `/mnt/dead-pool/apps/fallout-shelter/config/truenas-app.yml`

```yaml
include:
  - env_file:
      - /mnt/dead-pool/apps/fallout-shelter/config/.env
    path: /mnt/dead-pool/apps/fallout-shelter/config/compose.yml
```

Then add as custom app in TrueNAS UI.

## Version Management

### Current Strategy
- `BE_VERSION=latest` - Always pulls latest backend release
- `FE_VERSION=latest` - Always pulls latest frontend release

This auto-updates when semantic-release publishes new versions.

### Pinning to Specific Version (Optional)

Edit `.env`:
```bash
BE_VERSION=v1.14.2
FE_VERSION=v1.14.2
```

Then pull and restart:
```bash
docker compose pull
docker compose up -d
```

## Update Procedure

When new version is released (automated via GitHub Actions):

```bash
cd /mnt/dead-pool/apps/fallout-shelter/config

# Pull new images
docker compose pull

# Restart services
docker compose up -d

# Run migrations (if needed)
docker compose exec fastapi uv run alembic upgrade head

# Check logs for errors
docker compose logs -f --tail=100
```

## Rollback Procedure

```bash
cd /mnt/dead-pool/apps/fallout-shelter/config

# Edit .env - change to previous version
sudo nano .env
# Set: BE_VERSION=v1.14.0, FE_VERSION=v1.14.0

# Pull old version
docker compose pull

# Restart
docker compose up -d

# If database migration issue, restore backup
cat backup.sql | docker compose exec -T db psql -U postgres -d fallout_db
```

## Maintenance

### Database Backup
```bash
# Create backup
docker compose exec db pg_dump -U postgres fallout_db > backup_$(date +%Y%m%d).sql

# Restore backup
cat backup_20260121.sql | docker compose exec -T db psql -U postgres -d fallout_db
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi
docker compose logs -f celery_worker

# Last 100 lines
docker compose logs --tail=100
```

### Restart Services
```bash
# All services
docker compose restart

# Specific service
docker compose restart fastapi
```

### Clean Up
```bash
# Stop all services
docker compose down

# Stop and remove volumes (DESTRUCTIVE!)
docker compose down -v
```

## Monitoring

### Service Status
```bash
docker compose ps
```

### Resource Usage
```bash
docker stats
```

### Celery Tasks (Flower)
- URL: `http://truenas-ip:5555`
- Or expose through Nginx Proxy Manager

### Email Testing (Mailpit)
- URL: `http://truenas-ip:8025`
- Captures all emails sent by the application

## Troubleshooting

### Services Won't Start
```bash
# Check logs
docker compose logs

# Verify environment variables
docker compose config

# Check port conflicts
sudo netstat -tulpn | grep -E '8000|3000|5432|6379|9000'
```

### Database Connection Errors
```bash
# Check database is healthy
docker compose ps db

# Test connection
docker compose exec db psql -U postgres -d fallout_db -c "SELECT 1"

# View database logs
docker compose logs db
```

### Frontend Shows Connection Error
- Verify `API_URL` in .env matches your domain
- Check Nginx Proxy Manager configuration
- Verify frontend was built with correct API URL
- Check browser console for CORS errors

### MinIO/Media Files Not Loading
See [NGINX_PROXY_MANAGER_SETUP.md](NGINX_PROXY_MANAGER_SETUP.md) for CORS configuration.

### Celery Tasks Not Running
```bash
# Check Redis
docker compose ps redis

# Check worker logs
docker compose logs celery_worker

# Inspect active tasks
docker compose exec celery_worker celery -A app.core.celery inspect active
```

## Security Considerations

**Required:**
- [ ] All passwords are strong and unique
- [ ] `.env` file permissions: `chmod 600 .env`
- [ ] HTTPS enforced via Nginx Proxy Manager
- [ ] Regular database backups

**Recommended:**
- [ ] Firewall rules restrict access to ports
- [ ] Restrict Flower (port 5555) to internal network
- [ ] Restrict Mailpit (port 8025) to internal network
- [ ] Set up automated backups

## Reference Configuration

Complete example files are available in the repository:
- [`docs/examples/docker-compose.truenas.yml`](../examples/docker-compose.truenas.yml)
- [`docs/examples/.env.staging.example`](../examples/.env.staging.example)
- [`docs/examples/truenas-app.yml`](../examples/truenas-app.yml)

## Related Documentation

- [Nginx Proxy Manager Setup](NGINX_PROXY_MANAGER_SETUP.md)
- [MinIO Setup](MINIO_SETUP.md)
- [Main Deployment Guide](../DEPLOYMENT.md)
- [Security Guide](../SECURITY_GUIDE.md)

---

**Last Updated:** 2026-01-21
**Tested On:** TrueNAS Scale 24.x

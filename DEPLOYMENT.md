# Environment Setup and Deployment Guide

This guide covers how to run the Fallout Shelter application in different environments.

## Table of Contents
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [Docker Commands](#docker-commands)

---

## Local Development

### Prerequisites
- Docker and Docker Compose installed
- Git

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd falloutProject
   ```

2. **Create local environment file**
   ```bash
   cp .env.example .env.local
   ```

3. **Update `.env.local` with your local settings**
   - Set `POSTGRES_SERVER=db` (for docker-compose)
   - Set `REDIS_HOST=redis` (for docker-compose)
   - Set `MINIO_HOSTNAME=minio` (for docker-compose)
   - Set `SMTP_HOST=mailpit` (for docker-compose)
   - Add your `OPENAI_API_KEY`

4. **Start the development environment**
   ```bash
   docker-compose -f docker-compose.local.yml up -d
   ```

5. **Check service status**
   ```bash
   docker-compose -f docker-compose.local.yml ps
   ```

### Access Points (Local)
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower (Celery)**: http://localhost:5555
- **MinIO Console**: http://localhost:9001
- **Mailpit (Email)**: http://localhost:8025

### Development Features
- **Hot reload enabled** for FastAPI and Vue.js
- **Volume mounts** for live code updates
- **Mailpit** for email testing (no real emails sent)
- **Debug logging** enabled

---

## Production Deployment

### Prerequisites
- Docker and Docker Compose installed
- Domain name (optional but recommended)
- SSL certificates (if using HTTPS)

### Setup Steps

1. **Create production environment file**
   ```bash
   cp .env.example .env.prod
   ```

2. **Update `.env.prod` with production settings**
   - Generate a strong `SECRET_KEY`
   - Set `ENVIRONMENT=production`
   - Use strong passwords for all services
   - Configure real SMTP service (not Mailpit)
   - Set `POSTGRES_SERVER=db`
   - Set `REDIS_HOST=redis`
   - Set `MINIO_HOSTNAME=minio`
   - Add production `OPENAI_API_KEY`
   - Set `FLOWER_USER` and `FLOWER_PASSWORD`

3. **Build production images**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

4. **Start production environment**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Production Differences
- **No hot reload** - requires container restart for code changes
- **No volume mounts** - code is baked into images
- **Multiple workers** - FastAPI runs with 4 workers
- **Healthchecks** - all services have health monitoring
- **Resource limits** - Redis has memory limits
- **Network isolation** - services use dedicated network
- **Production logging** - warning level for Celery

### Production Checklist
- [ ] Update all default passwords
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure real SMTP service
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy for PostgreSQL
- [ ] Set up monitoring and alerting
- [ ] Configure firewall rules
- [ ] Enable HTTPS
- [ ] Restrict Flower access (currently exposed)
- [ ] Consider adding Nginx reverse proxy

---

## Environment Variables

### Required Variables
```bash
# Security
SECRET_KEY=your-secret-key

# Database
POSTGRES_SERVER=db  # or localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=fallout_db

# Redis
REDIS_HOST=redis  # or localhost
REDIS_PORT=6379

# OpenAI
OPENAI_API_KEY=your-openai-key

# MinIO
MINIO_HOSTNAME=minio  # or localhost
MINIO_PORT=9000
MINIO_ROOT_USER=your-username
MINIO_ROOT_PASSWORD=your-password

# SMTP
SMTP_HOST=your-smtp-host
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-password
SMTP_TLS=True
```

### Docker Compose vs Native
When running services inside docker-compose, use service names:
- `POSTGRES_SERVER=db` (not `localhost`)
- `REDIS_HOST=redis` (not `localhost`)
- `MINIO_HOSTNAME=minio` (not `localhost`)

When running services natively (without docker-compose):
- `POSTGRES_SERVER=localhost`
- `REDIS_HOST=localhost`
- `MINIO_HOSTNAME=localhost`

---

## Docker Commands

### Local Development

```bash
# Start services
docker-compose -f docker-compose.local.yml up -d

# Stop services
docker-compose -f docker-compose.local.yml down

# View logs
docker-compose -f docker-compose.local.yml logs -f

# Restart a specific service
docker-compose -f docker-compose.local.yml restart fastapi

# Rebuild a service
docker-compose -f docker-compose.local.yml build fastapi
docker-compose -f docker-compose.local.yml up -d fastapi

# Run database migrations
docker exec fastapi uv run alembic upgrade head

# Access database shell
docker exec -it falloutproject-db-1 psql -U postgres -d fallout_db

# Clear all data (DESTRUCTIVE)
docker-compose -f docker-compose.local.yml down -v
```

### Production

```bash
# Start services
docker-compose -f docker-compose.prod.yml up -d

# Stop services
docker-compose -f docker-compose.prod.yml down

# View logs (last 100 lines)
docker-compose -f docker-compose.prod.yml logs --tail=100

# Monitor logs in real-time
docker-compose -f docker-compose.prod.yml logs -f

# Check service health
docker-compose -f docker-compose.prod.yml ps

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Update services (after code changes)
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=4
```

### Database Management

```bash
# Backup database
docker exec falloutproject-db-1 pg_dump -U postgres fallout_db > backup.sql

# Restore database
cat backup.sql | docker exec -i falloutproject-db-1 psql -U postgres -d fallout_db

# Clear incidents table
docker exec -i falloutproject-db-1 psql -U postgres -d fallout_db -c "TRUNCATE TABLE incident CASCADE;"

# Check table sizes
docker exec -i falloutproject-db-1 psql -U postgres -d fallout_db -c "
SELECT
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

### Monitoring

```bash
# Check container resource usage
docker stats

# Check Celery worker status
docker exec celery_worker celery -A app.core.celery inspect active

# Check scheduled tasks
docker exec celery_beat celery -A app.core.celery inspect scheduled

# View Flower UI
# Open http://localhost:5555 in browser
```

---

## Troubleshooting

### Services won't start
- Check logs: `docker-compose -f docker-compose.local.yml logs`
- Ensure ports are not in use: `netstat -an | grep LISTEN`
- Verify environment variables are set correctly

### Database connection errors
- Ensure `POSTGRES_SERVER=db` when using docker-compose
- Wait for database health check to pass
- Check database logs: `docker-compose -f docker-compose.local.yml logs db`

### Celery tasks not running
- Check Redis is running: `docker-compose -f docker-compose.local.yml ps redis`
- Check Celery worker logs: `docker-compose -f docker-compose.local.yml logs celery_worker`
- Verify `CELERY_BROKER_URL` is correct

### MinIO connection errors
- Ensure `MINIO_HOSTNAME=minio` when using docker-compose
- Check MinIO logs: `docker-compose -f docker-compose.local.yml logs minio`
- Verify credentials in `.env.local` or `.env.prod`

---

## Security Notes

### Never commit these files:
- `.env`
- `.env.local`
- `.env.prod`
- `.env.staging`

### Always commit:
- `.env.example` (with placeholder values)

### Production Security:
1. Use strong, unique passwords for all services
2. Rotate `SECRET_KEY` regularly
3. Enable HTTPS/TLS
4. Restrict Flower and MinIO console access
5. Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
6. Enable Docker security scanning
7. Keep images updated
8. Configure firewall rules
9. Enable audit logging
10. Use read-only containers where possible

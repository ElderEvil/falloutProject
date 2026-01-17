# Deployment Guide

This guide covers how to deploy the Fallout Shelter application in different environments.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [Docker Commands](#docker-commands)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## Prerequisites

### Required Software
- **Python 3.12+** (matches pyproject.toml requirements)
- **Node.js 22+** with **pnpm 10.26+**
- **Docker/Podman** (for containerized deployment)
- **PostgreSQL 18+** (if running natively)
- **Redis** (if running natively)

### Development Tools
- **Git** for version control
- **VS Code** (recommended) with Python/TypeScript extensions

---

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd falloutProject
```

### 2. Generate Secret Key

```bash
# Generate a secure secret key
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 3. Environment Setup

```bash
# Backend environment
cd backend
cp .env.example .env
# Edit .env with your settings (add the generated SECRET_KEY)

# Frontend environment  
cd ../frontend
cp .env.example .env.local
# Edit .env.local if needed
```

### 4. Start Development

```bash
# Option 1: Full stack with containers
docker-compose up -d

# Option 2: Manual development
# Terminal 1: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run fastapi dev main.py

# Terminal 2: Frontend  
cd frontend
pnpm install
pnpm run dev
```

**Access Points:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Local Development

### Native Development (without containers)

#### Backend Setup

```bash
cd backend

# Install dependencies
uv sync --all-extras --dev

# Setup environment
cp .env.example .env
# Edit .env:
# - Set POSTGRES_SERVER=localhost
# - Set REDIS_HOST=localhost
# - Set MINIO_HOSTNAME=localhost
# - Add your OPENAI_API_KEY
# - Add generated SECRET_KEY

# Start PostgreSQL (if not running)
# Example for macOS with Homebrew:
brew services start postgresql

# Create database
createdb fallout_db

# Run migrations
uv run alembic upgrade head

# Start development server
uv run fastapi dev main.py
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Generate API types (backend must be running)
pnpm run types:generate

# Start development server
pnpm run dev
```

#### Required Services

**PostgreSQL:**
```bash
# Start PostgreSQL
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux

# Create database
createdb fallout_db

# Create user (optional)
createuser -s postgres
```

**Redis:**
```bash
# Start Redis
brew services start redis  # macOS  
sudo systemctl start redis # Linux
```

---

## Production Deployment

### Containerized Production

#### 1. Prepare Environment

```bash
# Create production environment
cp .env.example .env.production

# Edit .env.production with production settings:
# - Generate strong SECRET_KEY
# - Set ENVIRONMENT=production
# - Use strong passwords for all services
# - Configure real SMTP (not Mailpit)
# - Set production API keys
# - Set MINIO_PUBLIC_URL to your domain
```

#### 2. Deploy with Docker

```bash
# Build and start production
docker-compose -f docker-compose.yml up -d --build

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

#### 3. SSL Configuration

```bash
# With Nginx reverse proxy (recommended)
# - Configure Let's Encrypt certificates
# - Set up HTTPS redirection
# - Configure security headers
```

### Production Checklist

- [ ] Generate strong `SECRET_KEY`
- [ ] Update all default passwords
- [ ] Configure real SMTP service
- [ ] Set up SSL/TLS certificates
- [ ] Configure database backups
- [ ] Set up monitoring and alerting
- [ ] Configure firewall rules
- [ ] Enable HTTPS
- [ ] Restrict admin panel access
- [ ] Add reverse proxy (Nginx/Caddy)
- [ ] Set up log aggregation
- [ ] Configure CDN for static assets

---

## Environment Variables

### Core Variables

```bash
# Application
SECRET_KEY=your-generated-secret-key
ENVIRONMENT=production  # local, staging, production

# Database
POSTGRES_SERVER=localhost  # or db (in containers)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=fallout_db

# Redis
REDIS_HOST=localhost  # or redis (in containers)
REDIS_PORT=6379

# MinIO Storage
MINIO_HOSTNAME=localhost  # or minio (in containers)
MINIO_PORT=9000
MINIO_ROOT_USER=adminuser
MINIO_ROOT_PASSWORD=strong-password
MINIO_PUBLIC_URL=https://media.yourdomain.com

# AI Provider
AI_PROVIDER=openai  # openai, anthropic, ollama
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
OLLAMA_BASE_URL=http://localhost:11434/v1

# Email/SMTP
SMTP_HOST=your-smtp-server
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-password
SMTP_TLS=True
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
```

### Security Variables

```bash
# Authentication
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_EMAIL=admin@yourdomain.com
FIRST_SUPERUSER_PASSWORD=strong-password
USERS_OPEN_REGISTRATION=False  # Set to False in production

# Rate Limiting
ENABLE_RATE_LIMITING=True  # Enable in production
```

---

## Docker Commands

### Development

```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d db redis

# Rebuild services
docker-compose up -d --build

# View logs
docker-compose logs -f fastapi
docker-compose logs -f frontend

# Access containers
docker exec -it fastapi bash
docker exec -it db psql -U postgres -d fallout_db
```

### Database Operations

```bash
# Run migrations
docker exec fastapi uv run alembic upgrade head

# Create new migration
docker exec fastapi uv run alembic revision --autogenerate -m "description"

# Backup database
docker exec db pg_dump -U postgres fallout_db > backup.sql

# Restore database
cat backup.sql | docker exec -i db psql -U postgres -d fallout_db
```

### Production

```bash
# Scale workers
docker-compose up -d --scale celery_worker=4

# Rotate logs
docker-compose logs --no-log-prefix > production.log

# Update application
docker-compose pull
docker-compose up -d

# Cleanup unused images
docker image prune -f
```

---

## Troubleshooting

### Common Issues

#### Database Connection
```bash
# Check if database is accessible
docker exec -it db psql -U postgres -d fallout_db -c "SELECT 1;"

# Check connection string in logs
docker-compose logs fastapi | grep -i database
```

#### Service Dependencies
```bash
# Check service health
docker-compose ps

# Restart specific service
docker-compose restart fastapi

# Check network connectivity
docker network ls
docker network inspect falloutproject_default
```

#### Volume Issues
```bash
# Check volume mounts
docker inspect fastapi | grep -A 10 "Mounts"

# Clean up volumes (destructive)
docker-compose down -v
```

### Debug Commands

```bash
# Check container resources
docker stats

# Inspect container configuration
docker inspect fastapi

# Access shell in container
docker exec -it fastapi /bin/bash

# Check environment variables
docker exec fastapi env | grep -E "(SECRET_KEY|DATABASE|REDIS)"
```

---

## Security Notes

### Never Commit
- `.env` files with real credentials
- Database backups
- SSL certificates
- SSH private keys

### Always Do
- Use strong, unique passwords
- Rotate secrets regularly  
- Enable rate limiting
- Use HTTPS in production
- Keep dependencies updated
- Scan container images for vulnerabilities

### Production Security
1. **Secrets Management**: Use HashiCorp Vault, AWS Secrets Manager, or similar
2. **Network Security**: Configure firewalls, use VPN for admin access
3. **Container Security**: Use read-only containers, minimal base images
4. **Monitoring**: Set up log aggregation, alerting for security events
5. **Backups**: Regular automated backups with point-in-time recovery
6. **Access Control**: RBAC for all services, audit logging enabled

### Monitoring Commands

```bash
# Check application health
curl http://localhost:8000/health

# Monitor Celery tasks
curl http://localhost:8000/api/v1/tasks/status

# Database connections
docker exec db psql -U postgres -d fallout_db -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory usage
docker exec redis redis-cli info memory
```

---

*For detailed security configuration, see [SECURITY_GUIDE.md](./SECURITY_GUIDE.md)*
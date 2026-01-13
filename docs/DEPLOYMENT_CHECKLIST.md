# 🚀 Production Deployment Checklist

This checklist ensures a safe and successful deployment of your Fallout Shelter game to staging/production.

## 📋 Pre-Deployment Tasks

### 🔐 Security & Credentials (CRITICAL)

- [ ] **Create `.env.prod` file** using `.env.prod.example` as template
- [ ] **Generate secure SECRET_KEY**: `openssl rand -hex 32`
- [ ] **Configure rate limiting** (fastapi-guard):
  - [ ] Set `ENABLE_RATE_LIMITING=True` for production
  - [ ] Adjust `RATE_LIMIT_REQUESTS` based on expected traffic (default: 200/min)
  - [ ] Configure `AUTO_BAN_THRESHOLD` and `AUTO_BAN_DURATION`
  - [ ] Optional: Add `IPINFO_TOKEN` for geolocation features
  - [ ] Optional: Configure `SECURITY_WHITELIST_IPS` for trusted sources
- [ ] **Change all default passwords**:
  - [ ] `FIRST_SUPERUSER_PASSWORD` - Strong password for admin account
  - [ ] `POSTGRES_PASSWORD` - Database password (min 16 chars recommended)
  - [ ] `MINIO_ROOT_PASSWORD` - MinIO password (min 8 chars required)
  - [ ] `FLOWER_PASSWORD` - Celery monitoring password
- [ ] **Set production SMTP credentials** (SendGrid, AWS SES, Mailgun, etc.)
  - [ ] Update `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
  - [ ] Verify `EMAIL_FROM_ADDRESS` domain is authorized
- [ ] **Configure AI Provider**:
  - [ ] Set `AI_PROVIDER` (openai/anthropic/ollama)
  - [ ] Add valid `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
  - [ ] Consider cost: `gpt-4o-mini` is cheaper than `gpt-4o`
- [ ] **Review registration settings**:
  - [ ] Set `USERS_OPEN_REGISTRATION=False` for closed alpha
- [ ] **Update domains**:
  - [ ] Set `FRONTEND_URL` to actual production domain

### 🐳 Docker & Container Configuration

- [ ] **Build Docker images with correct API URL**:
  ```bash
  # Backend
  cd backend
  docker build -t elerevil/fastapi:v1.13 .

  # Frontend (with production API URL)
  cd frontend
  docker build --build-arg VITE_API_BASE_URL=https://api.yourdomain.com -t elerevil/vuejs:v1.13 .
  ```
- [ ] **Push images to Docker Hub**:
  ```bash
  docker push elerevil/fastapi:v1.13
  docker push elerevil/vuejs:v1.13
  ```
- [ ] **Update K8s deployment image tags** in `deployment/k3s/*.yaml` files
- [ ] **Create K8s secret for backend environment**:
  ```bash
  kubectl create secret generic backend-env --from-env-file=.env.prod
  ```

### 🗄️ Database Preparation

- [ ] **Backup existing database** (if applicable):
  ```bash
  pg_dump -h localhost -U postgres fallout_prod_db > backup_$(date +%Y%m%d_%H%M%S).sql
  ```
- [ ] **Test migration on staging database**:
  ```bash
  docker-compose run --rm fastapi alembic upgrade head
  ```
- [ ] **Verify migration success** - check logs for errors
- [ ] **Create rollback plan** - document how to revert if needed

### ✅ Testing & Validation

- [ ] **Run backend test suite**:
  ```bash
  cd backend
  uv run pytest --tb=short
  ```
  Expected: 293+ tests passing

- [ ] **Run frontend test suite**:
  ```bash
  cd frontend
  pnpm test --run
  ```
  Expected: 639+ tests passing (1 skipped is OK)

- [ ] **Test production build locally**:
  ```bash
  docker-compose -f docker-compose.prod.yml up -d
  ```

- [ ] **Verify services are healthy**:
  - [ ] Backend: `curl http://localhost:8000/healthcheck?detailed=true`
  - [ ] Frontend: `curl http://localhost:3000`
  - [ ] MinIO: `curl http://localhost:9000/minio/health/live`
  - [ ] Redis: `redis-cli ping`

- [ ] **Test critical user flows**:
  - [ ] User registration with email verification
  - [ ] Login/logout
  - [ ] Vault creation
  - [ ] Dweller management
  - [ ] Room building
  - [ ] AI chat (text and audio)
  - [ ] Exploration system

### 📊 Monitoring & Observability

- [ ] **Configure logging**:
  - [ ] Set `LOG_LEVEL=INFO` in production
  - [ ] Set `LOG_JSON_FORMAT=true` for structured logs

- [ ] **Set up log aggregation** (optional but recommended):
  - [ ] CloudWatch, Datadog, or ELK stack

- [ ] **Configure alerts** (optional):
  - [ ] Disk space < 20%
  - [ ] Memory usage > 80%
  - [ ] Error rate > threshold

- [ ] **Consider Sentry integration** (future - not critical for alpha):
  - Defer to post-launch

### 📝 Documentation

- [ ] **Document deployment process** for your team
- [ ] **Create runbook** for common issues:
  - Database connection failures
  - Redis unavailable
  - MinIO bucket permissions
  - Celery worker issues
- [ ] **Prepare user guide** for alpha testers

## 🚀 Deployment Steps

### Option 1: GitHub Actions (Recommended)

1. [ ] **Commit all changes** to your repository
2. [ ] **Trigger deployment workflow**:
   - Go to Actions → "Deploy to Staging (TrueNAS)"
   - Click "Run workflow"
   - Set parameters:
     - `backend_image_tag`: v1.13
     - `frontend_image_tag`: v1.13
     - `run_migrations`: true
     - `deploy_backend`: true
     - `deploy_frontend`: true
3. [ ] **Monitor workflow execution** in GitHub Actions
4. [ ] **Review deployment logs** for errors

### Option 2: Manual Deployment

1. [ ] **SSH into server**
2. [ ] **Pull latest code**: `git pull origin master`
3. [ ] **Pull Docker images**:
   ```bash
   docker pull elerevil/fastapi:v1.13
   docker pull elerevil/vuejs:v1.13
   ```
4. [ ] **Run migrations**:
   ```bash
   docker-compose -f docker-compose.prod.yml run --rm fastapi alembic upgrade head
   ```
5. [ ] **Deploy services**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --force-recreate
   ```
6. [ ] **Wait for services to be healthy** (check `docker-compose ps`)

## ✅ Post-Deployment Verification

- [ ] **Verify all services are running**:
  ```bash
  docker-compose -f docker-compose.prod.yml ps
  ```
  Expected: All services "Up (healthy)"

- [ ] **Check health endpoints**:
  ```bash
  curl https://api.yourdomain.com/healthcheck?detailed=true
  ```
  Expected: `{"status": "ok", "services": {...}}`

- [ ] **Monitor logs for errors**:
  ```bash
  docker-compose -f docker-compose.prod.yml logs --tail=100 fastapi
  docker-compose -f docker-compose.prod.yml logs --tail=100 celery_worker
  ```

- [ ] **Test critical user paths** (end-to-end):
  - [ ] Register new user
  - [ ] Verify email
  - [ ] Create vault
  - [ ] Manage dwellers
  - [ ] Test AI chat

- [ ] **Monitor resource usage**:
  - [ ] CPU usage < 70%
  - [ ] Memory usage < 80%
  - [ ] Disk space > 20% free

- [ ] **Test with alpha users**:
  - [ ] Send invite links
  - [ ] Gather feedback
  - [ ] Monitor for crashes

## 🔙 Rollback Plan

If deployment fails:

1. [ ] **Check logs** to identify the issue
2. [ ] **Rollback to previous version**:
   ```bash
   # Option 1: Using GitHub Actions rollback workflow
   # Option 2: Manual rollback
   docker-compose -f docker-compose.prod.yml down
   docker pull elerevil/fastapi:v1.12  # Previous version
   docker pull elerevil/vuejs:v1.12
   docker-compose -f docker-compose.prod.yml up -d
   ```
3. [ ] **Restore database backup** (if migration failed):
   ```bash
   psql -h localhost -U postgres -d fallout_prod_db < backup_TIMESTAMP.sql
   ```

## 📊 Success Criteria

Deployment is successful when:

- ✅ All services are healthy for 10+ minutes
- ✅ No critical errors in logs
- ✅ Users can register, login, and create vaults
- ✅ AI chat (text and audio) works
- ✅ Background tasks are processing (check Flower dashboard)
- ✅ Email verification works
- ✅ Response times < 2 seconds for most requests

## 🎯 Next Steps (Post-Deploy)

- [ ] **Monitor for 24 hours** - watch for issues
- [ ] **Gather user feedback** from alpha testers
- [ ] **Address critical bugs** discovered in production
- [ ] **Plan v1.14 features**:
  - Resource warning UI
  - Training room UI improvements
  - Empty states
- [ ] **Consider Sentry integration** for better error tracking
- [ ] **Set up automated backups** (daily database dumps)
- [ ] **Document lessons learned** for next deployment

---

## 🆘 Emergency Contacts

- **Server Issues**: [Your name/contact]
- **Database Issues**: [DBA contact]
- **API Keys/Secrets**: [Security contact]

## 📚 Additional Resources

- [ROADMAP.md](./ROADMAP.md) - Feature roadmap and version history
- [README.md](./README.md) - Development setup
- [docker-compose.prod.yml](./docker-compose.prod.yml) - Production compose file
- [GitHub Actions Workflow](./.github/workflows/deploy.yml) - Automated deployment

---

**Last Updated**: 2026-01-09
**Version**: v1.13 (Audio Conversations & Exploration Update)

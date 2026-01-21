# ⚡ Quick Deployment Guide

**Target**: Deploy v1.13 to Staging/Production in 1-2 days

---

## 🔥 Critical Path (60-90 minutes)

### Step 1: Secure Your Environment (30 min)
```bash
# 1. Create production environment file
cp .env.prod.example .env.prod

# 2. Generate secure SECRET_KEY
openssl rand -hex 32
# Copy output and paste into .env.prod

# 3. Edit .env.prod and update ALL "CHANGE-ME" values:
# - SECRET_KEY (use value from step 2)
# - POSTGRES_PASSWORD
# - FIRST_SUPERUSER_PASSWORD
# - MINIO_ROOT_PASSWORD (min 8 chars)
# - FLOWER_PASSWORD
# - SMTP credentials (use SendGrid, AWS SES, etc.)
# - OPENAI_API_KEY or ANTHROPIC_API_KEY
# - FRONTEND_URL=https://yourdomain.com
```

### Step 2: Build & Push Images (15 min)
```bash
# Set your production API URL
export PROD_API_URL="https://api.yourdomain.com"

# Backend
docker build -t elerevil/fastapi:v1.13 ./backend
docker push elerevil/fastapi:v1.13

# Frontend
docker build --build-arg VITE_API_BASE_URL=$PROD_API_URL -t elerevil/vuejs:v1.13 ./frontend
docker push elerevil/vuejs:v1.13
```

### Step 3: Deploy (15-30 min)

#### Option A: GitHub Actions (Easier)
1. Commit and push your changes
2. Go to GitHub → Actions → "Deploy to Staging (TrueNAS)"
3. Click "Run workflow"
4. Set:
   - backend_image_tag: `v1.13`
   - frontend_image_tag: `v1.13`
   - run_migrations: ✅
   - deploy_backend: ✅
   - deploy_frontend: ✅
5. Monitor logs in GitHub Actions

#### Option B: Manual Deploy
```bash
# SSH to server
ssh your-user@your-server

# Create K8s secret (first time only)
kubectl create secret generic backend-env --from-env-file=.env.prod

# Update deployments
kubectl set image deployment/backend backend=elerevil/fastapi:v1.13
kubectl set image deployment/frontend frontend=elerevil/vuejs:v1.13

# Run migrations
kubectl get pods | grep backend
kubectl exec -it backend-XXXXX -- alembic upgrade head

# OR using docker-compose
cd /path/to/project
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml run --rm fastapi alembic upgrade head
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

### Step 4: Verify (10 min)
```bash
# Check health
curl https://api.yourdomain.com/healthcheck
# Expected: {"status":"ok"}

# Test detailed health
curl https://api.yourdomain.com/healthcheck?detailed=true

# Check frontend
curl https://yourdomain.com
```

### Step 5: Test Critical Paths (15 min)
- [ ] Open https://yourdomain.com
- [ ] Register new user
- [ ] Check email and verify
- [ ] Login
- [ ] Create vault
- [ ] Create dweller
- [ ] Build room
- [ ] Test AI chat (text)
- [ ] Test audio conversation (new v1.13 feature!)

---

## ✅ Success Checklist

Deployment is complete when:
- [ ] Health endpoint returns `{"status":"ok"}`
- [ ] All services show "healthy" status
- [ ] Users can register and verify email
- [ ] Vault creation works
- [ ] AI chat works (both text and audio)
- [ ] No critical errors in logs

---

## 🆘 Quick Troubleshooting

### Issue: Health check fails
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs --tail=100 fastapi

# Common causes:
# - Database not accessible (check POSTGRES_SERVER in .env.prod)
# - Redis not running
# - MinIO not accessible
```

### Issue: Frontend shows connection error
```bash
# Verify API URL was baked into build
docker run --rm elerevil/vuejs:v1.13 cat /app/assets/index-*.js | grep -o 'http[s]*://[^"]*'

# If wrong, rebuild with correct --build-arg
docker build --build-arg VITE_API_BASE_URL=https://api.yourdomain.com -t elerevil/vuejs:v1.13 ./frontend
docker push elerevil/vuejs:v1.13
```

### Issue: Email verification not working
```bash
# Check SMTP settings in .env.prod
# - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
# - SMTP_TLS=True for most providers

# Test SMTP connection
docker-compose exec fastapi python -c "from app.core.config import settings; print(settings.SMTP_HOST)"
```

### Issue: AI chat not working
```bash
# Check API key is set
docker-compose exec fastapi python -c "from app.core.config import settings; print(settings.AI_PROVIDER, bool(settings.OPENAI_API_KEY))"

# Try switching providers
# Edit .env.prod: AI_PROVIDER=anthropic
# Restart: docker-compose -f docker-compose.prod.yml restart fastapi
```

---

## 🔙 Rollback (if needed)
```bash
# Rollback to v1.12 (previous version)
kubectl set image deployment/backend backend=elerevil/fastapi:v1.12
kubectl set image deployment/frontend frontend=elerevil/vuejs:v1.12

# OR with docker-compose
docker pull elerevil/fastapi:v1.12
docker pull elerevil/vuejs:v1.12
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

---

## 📚 Full Documentation

For detailed information, see:
- [DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md) - Complete overview
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - Detailed checklist
- [.env.prod.example](./.env.prod.example) - Environment template

---

**Version**: v1.13
**Last Updated**: 2026-01-09
**Status**: ✅ Ready to deploy

# Fallout Shelter Game 🏠☢️

A web-based simulation game where you manage a vault full of dwellers, balancing their needs and resources to keep the
vault thriving. Built with modern Python tooling.

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-blue.svg)](https://www.postgresql.org/)
[![Vue 3.5](https://img.shields.io/badge/vue-3.5-00ff00.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.9-00ff00.svg)](https://www.typescriptlang.org/)

See [ROADMAP.md](./ROADMAP.md) for recent updates and upcoming features.

## ✨ Tech Stack

**Backend:** FastAPI · SQLModel · PostgreSQL 18 · Celery · Redis · MinIO · PydanticAI
**Frontend:** Vue 3.5 · TypeScript · Vite · Pinia · TailwindCSS v4 · Vitest
**Tooling:** uv · ruff · Rolldown · Oxlint · Docker/Podman

## 📋 Prerequisites

**Required:**
- [Python 3.12+](https://www.python.org/downloads/) (3.13 recommended)
- [Node.js 22 LTS](https://nodejs.org/)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2 - use `docker compose`, not `docker-compose`)

**Installation:**
- **uv** (Python package manager):
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **pnpm** (via Corepack): `corepack enable && corepack use pnpm@latest`

## 🚀 Quick Start (Hybrid Development)

**Recommended setup:** Run infrastructure in Docker; run backend + frontend locally for hot reload.

```bash
# 1. Clone and setup environment
git clone https://github.com/ElderEvil/falloutProject && cd falloutProject
cp .env.example .env  # Edit with your settings (keep localhost hostnames)

# 2. Start infrastructure services (PostgreSQL, Redis, MinIO, Mailpit)
docker compose -f docker-compose.infra.yml up -d

# 3. Setup and run backend (http://localhost:8000)
cd backend
cp ../.env .env
uv sync --all-extras --dev
uv run alembic upgrade head
uv run fastapi dev main.py

# 4. In separate terminals, start Celery workers
# Terminal 2:
uv run celery -A app.core.celery worker -l info

# Terminal 3:
uv run celery -A app.core.celery beat -l info --scheduler sqlalchemy_celery_beat.schedulers:DatabaseScheduler

# 5. Setup and run frontend (http://localhost:5173)
# ⚠️ IMPORTANT: Backend API must be accessible at http://localhost:8000
cd ../frontend
pnpm install
pnpm run dev
```

**Verify everything works:**
```bash
# Backend health check
curl -sf http://localhost:8000/healthcheck

# Frontend (open in browser)
# Windows (PowerShell): Start-Process http://localhost:5173
# Mac: open http://localhost:5173
# Linux: xdg-open http://localhost:5173
```

**Optional: Ollama for Local AI (Hybrid Mode)**
```bash
# Install Ollama: https://ollama.ai/download
# Pull a model (run once):
ollama pull llama2

# Ollama runs as service after install (http://localhost:11434)
# Update .env: AI_PROVIDER=ollama
```

**Platform Notes:**
- **Windows:** Use PowerShell, Git Bash, or WSL2. Commands work identically.
- **Mac/Linux:** All commands work as-is in Terminal.
- **First run:** Backend will create database schema automatically via migrations

### Alternative: Full Stack via Docker

Run everything in containers (no local Node/Python needed):

```bash
# 1. Clone and setup environment
git clone https://github.com/ElderEvil/falloutProject && cd falloutProject
cp .env.example .env  # Edit SECRET_KEY, passwords, API keys as needed

# 2. Start all services (environment overrides handled automatically)
docker compose up -d

# 3. Wait for services to be ready (30-60 seconds)
docker compose logs -f fastapi  # Watch startup (Ctrl+C to exit)
```

**Access:**
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/docs (Swagger UI)
- **Mailpit (email testing):** http://localhost:8025
- **Flower (Celery monitor):** http://localhost:5555
- **MinIO Console:** http://localhost:9001 (login: minioadmin/minioadmin)

**Notes:**
- No need to edit hostnames in `.env` - Docker Compose automatically overrides them
- First build takes 5-10 minutes (downloads images + builds backend/frontend)
- Subsequent starts are fast (~30 seconds)

## 🔧 Development

### Backend

```bash
cd backend
uv sync --all-extras --dev && prek install
uv run pytest app/tests/        # Run tests
uv run ruff check . && uv run ruff format .  # Lint & format
uv run alembic upgrade head     # Migrations
```

### Frontend

```bash
cd frontend
pnpm install
pnpm test                       # Run tests
pnpm run lint                   # Lint
pnpm run build                  # Build for production
```

See [`frontend/README.md`](./frontend/README.md) and [`frontend/STYLEGUIDE.md`](./frontend/STYLEGUIDE.md) for details.

## 🐳 Deployment

### Docker Compose Options

```bash
# Hybrid development (infra only)
docker compose -f docker-compose.infra.yml up -d

# Full stack (all services)
docker compose up -d
# Access frontend: http://localhost:3000
# Access backend: http://localhost:8000

# Local dev with hot reload
docker compose -f docker-compose.local.yml up -d

# TrueNAS staging
# See docs/deployment/TRUENAS_SETUP.md
```

### Docker Images

Pre-built images (automated by CI/CD):
- Backend: `elerevil/fo-shelter-be:latest`
- Frontend: `elerevil/fo-shelter-fe:latest`

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for complete deployment guide.

## 🔑 Environment Variables

**Environment files:**
- `.env.example` - Template with localhost hostnames (for hybrid development)
- `.env` - Your local copy (create from `.env.example`)
- `.env.local` - Used by `docker-compose.local.yml` (dev with volume mounts)
- `backend/.env` - Backend runtime requires this (copy from root `.env`)

**Configuration strategy:**
- **Hybrid mode:** Use `.env` with localhost hostnames (as-is from `.env.example`)
- **Full Docker mode:** Use `.env` as-is - Docker Compose auto-overrides hostnames
- **Do NOT manually edit** hostnames for Docker - compose files handle it

**Key variables:**
- **Required:**
  - `SECRET_KEY` - Change in production (use `openssl rand -hex 32`)
  - `POSTGRES_PASSWORD` - Database password
  - `FIRST_SUPERUSER_PASSWORD` - Admin account password
- **Optional:**
  - `AI_PROVIDER` - `openai` (default), `anthropic`, or `ollama` (local/free)
  - `OPENAI_API_KEY` - Only if using OpenAI (leave empty for ollama)
  - Database: `POSTGRES_SERVER`, `POSTGRES_DB`, `POSTGRES_USER`
  - Redis: `REDIS_HOST`, `REDIS_PORT`
  - MinIO: `MINIO_HOSTNAME`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`

**AI Setup Notes:**
- **Ollama (Free):** For Docker: already runs in `ollama` container. For hybrid: [install locally](https://ollama.ai/download)
- **OpenAI:** Set `AI_PROVIDER=openai` and add your `OPENAI_API_KEY`
- **No AI:** App works without AI (conversations/chat features disabled)

## 🔧 Troubleshooting

### Common Issues

**"Connection refused" errors in Docker:**
```bash
# Check all services are running
docker compose ps

# View logs for specific service
docker compose logs fastapi
docker compose logs db

# Restart services
docker compose restart
```

**Port already in use:**
```bash
# Check what's using port 8000 (backend)
# Linux/Mac: lsof -i :8000
# Windows: netstat -ano | findstr :8000

# Stop conflicting service or change port in docker-compose.yml
```

**Backend can't connect to database (hybrid mode):**
```bash
# Verify infrastructure is running
docker compose -f docker-compose.infra.yml ps

# Check .env has localhost (not 'db')
grep POSTGRES_SERVER .env  # Should show: POSTGRES_SERVER=localhost
```

**Frontend can't generate types:**
```bash
# Ensure backend is running and accessible
curl http://localhost:8000/docs

# If backend is in Docker, ensure port 8000 is exposed
docker compose ps fastapi  # Should show 0.0.0.0:8000->8000/tcp
```

**AI features not working:**
- Check `AI_PROVIDER` in `.env` matches your setup
- For OpenAI: Verify `OPENAI_API_KEY` is set correctly
- For Ollama: Ensure service is running (`ollama serve` or check Docker container)
- App works without AI - conversation features will be disabled

## 📚 Documentation

- [ROADMAP.md](./ROADMAP.md) - Changelog and upcoming features
- [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) - Deployment guide
- [docs/deployment/TRUENAS_SETUP.md](./docs/deployment/TRUENAS_SETUP.md) - TrueNAS staging setup
- [frontend/README.md](./frontend/README.md) - Frontend architecture
- [frontend/STYLEGUIDE.md](./frontend/STYLEGUIDE.md) - Design system

## 📄 License
 
MIT License - See LICENSE file for details.

---

Built by [ElderEvil](https://github.com/ElderEvil) · Inspired by Fallout Shelter (Bethesda)

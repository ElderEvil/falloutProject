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
cp .env.example .env  # Edit with your settings

# 2. Start infrastructure services (PostgreSQL, Redis, MinIO, Mailpit)
docker compose -f docker-compose.infra.yml up -d

# 3. Setup and run backend (http://localhost:8000)
cd backend
cp ../.env .env
uv sync --all-extras --dev
uv run alembic upgrade head
uv run fastapi dev main.py

# 4. Setup and run frontend (http://localhost:5173)
# ⚠️ IMPORTANT: Backend must be running first (frontend needs it for type generation)
cd ../frontend
pnpm install
pnpm run dev
```

**Verify everything works:**
```bash
# Backend health check
curl -sf http://localhost:8000/healthcheck

# Frontend (open in browser)
open http://localhost:5173
```

### Alternative: Full Stack via Docker

Run everything in containers (no local Node/Python needed):

```bash
# Create .env with docker-internal hostnames
cp .env.example .env
# Edit .env and set:
#   POSTGRES_SERVER=db
#   REDIS_HOST=redis
#   CELERY_BROKER_URL=redis://redis:6379/0
#   CELERY_RESULT_BACKEND=redis://redis:6379/0
#   MINIO_HOSTNAME=minio
#   SMTP_HOST=mailpit
#   OLLAMA_BASE_URL=http://ollama:11434/v1

docker compose up -d
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Mailpit (email testing): http://localhost:8025
- Flower (Celery monitor): http://localhost:5555
- MinIO Console: http://localhost:9001

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
- `.env.local` - Used by `docker-compose.local.yml` (identical to `.env.example`)
- `backend/.env` - Backend runtime requires this (copy from root `.env`)

**Key variables:**
- Database: `POSTGRES_SERVER`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Auth: `SECRET_KEY`, `FIRST_SUPERUSER_USERNAME`, `FIRST_SUPERUSER_PASSWORD`
- Redis: `REDIS_HOST`, `REDIS_PORT`
- MinIO: `MINIO_HOSTNAME`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- AI: `AI_PROVIDER` (optional - defaults to `openai`), `OPENAI_API_KEY` (optional)

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

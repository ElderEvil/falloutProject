# Fallout Shelter Game 🏠☢️

A web-based simulation game where you manage a vault full of dwellers, balancing their needs and resources to keep the
vault thriving. Built with modern Python tooling and designed for Python 3.14.

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

- Python 3.13+ · PostgreSQL 18 · Redis
- Node.js 22+ · pnpm 10.26+
- Docker/Podman (optional)

## 🚀 Quick Start

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```

### Setup & Run

```bash
# Clone and setup backend
git clone <repo-url> && cd falloutProject/backend
uv sync
cp .env.example .env  # Edit with your settings

# Start database
docker-compose up -d db  # or: createdb fallout_db && uv run alembic upgrade head

# Run backend (http://localhost:8000)
uv run fastapi dev main.py

# Run frontend (http://localhost:5173)
cd ../frontend
pnpm install && pnpm run dev
```

**Full Stack:** `docker-compose up -d` → [http://localhost:8080](http://localhost:8080)

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

### Quick Start

```bash
# Local development
docker compose up -d
# Access: http://localhost:5173

# TrueNAS staging
# See docs/deployment/TRUENAS_SETUP.md
```

### Docker Images

Pre-built images (automated by CI/CD):
- Backend: `elerevil/fo-shelter-be:latest`
- Frontend: `elerevil/fo-shelter-fe:latest`

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for complete deployment guide.

## 🔑 Environment Variables

See `.env.example` for all variables. Key ones:

- Database: `POSTGRES_SERVER`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Auth: `SECRET_KEY`, `FIRST_SUPERUSER_USERNAME`, `FIRST_SUPERUSER_PASSWORD`
- Redis: `REDIS_HOST`, `REDIS_PORT`
- MinIO: `MINIO_HOSTNAME`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`

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

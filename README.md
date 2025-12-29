# Fallout Shelter Game 🏠☢️

A web-based simulation game where you manage a vault full of dwellers, balancing their needs and resources to keep the
vault thriving. Built with modern Python tooling and designed for Python 3.14.

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-blue.svg)](https://www.postgresql.org/)
[![Vue 3.5](https://img.shields.io/badge/vue-3.5-00ff00.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.7-00ff00.svg)](https://www.typescriptlang.org/)

## ✨ Tech Stack

### Backend

- **FastAPI** + SQLModel + Pydantic v2 - Modern Python API framework
- **PostgreSQL 18** - Database with UUID v7 support
- **Celery + Redis** - Task queue and caching
- **MinIO** - Object storage
- **PydanticAI** - AI integration for dweller chat

### Frontend

- **Vue 3.5** - Composition API with TypeScript
- **Vite (rolldown-vite)** - Ultra-fast bundler with Rolldown
- **Pinia 3.0** - State management
- **TailwindCSS v4** - Utility-first CSS with custom design system
- **Custom UI Library** - 8 terminal-themed components
- **Vitest 2.1** - Unit testing (88 tests passing)

### Infrastructure

- **Docker/Podman** - Containerization
- **K3s (Kubernetes)** - Production orchestration

### Modern Tooling

This project uses cutting-edge **Rust-based** tools for maximum performance:

**Backend (Python):**

- 🦀 **[uv](https://github.com/astral-sh/uv)** - Ultra-fast package installer (replaces pip)
- 🦀 **[ruff](https://github.com/astral-sh/ruff)** - Blazingly fast linter/formatter (replaces flake8/black/isort)
- 🦀 **[prek](https://github.com/j178/prek)** - Pre-commit hook runner
- 🦀 **[ty](https://github.com/gao-artur/ty)** - Fast type checker (mypy alternative)

**Frontend (JavaScript):**

- 🦀 **[Rolldown](https://rolldown.rs/)** - Rust bundler (built into Vite)
- 🦀 **[Oxlint](https://oxc.rs/)** - 50-100x faster linter (replaces ESLint + Prettier)
- ⚡ **[Vitest](https://vitest.dev/)** - Fast unit test framework

## 📋 Prerequisites

**Backend:**

- **Python 3.13**
- **PostgreSQL 18**
- **Redis** (for Celery)

**Frontend:**

- **Node.js 22+** (required)
- **pnpm 10.26+** (recommended)

**Optional:**

- **Docker/Podman** (for containerized setup)

## 🚀 Quick Start

### 1. Install uv (Recommended)

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative (with pip):**

```bash
pip install uv
```

### 2. Clone and Setup

```bash
# Clone the repository
git clone <repo-url>
cd falloutProject

# Navigate to backend
cd backend

# Install dependencies (uv will auto-create venv)
uv sync

# Copy environment variables
cp .env.example .env
# Edit .env with your settings
```

### 3. Database Setup

**Option A: Using Docker/Podman Compose**

```bash
# From project root
docker-compose up -d db
# OR with Podman
podman-compose up -d db
```

**Option B: Local PostgreSQL 18**

```bash
# Create database
createdb fallout_db

# Run migrations
cd backend
uv run alembic upgrade head
```

### 4. Run the Application

**Backend Development Server:**

```bash
cd backend
uv run fastapi dev main.py
```

API available at [http://localhost:8000](http://localhost:8000)

**Frontend Development Server:**

```bash
cd frontend
pnpm install  # First time only
pnpm run dev
```

Frontend available at [http://localhost:5173](http://localhost:5173)

**Full Stack (with Docker/Podman):**

```bash
# From project root
docker-compose up -d
# OR
podman-compose up -d
```

Visit [http://localhost:8080](http://localhost:8080) to start playing!

## 🔧 Development

### Backend Development

**Install Development Tools:**

```bash
cd backend
uv sync --all-extras --dev
prek install  # Install pre-commit hooks
```

**Available Commands:**

```bash
# Testing
uv run pytest app/tests/
uv run pytest app/tests/ --cov=app --cov-report=html

# Code Quality
uv run ruff check .
uv run ruff format .
uv run ty check app/
uv run prek run --all-files

# Database
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Background Tasks
uv run celery -A app.core.celery worker -l info
uv run celery -A app.core.celery beat -l info
```

### Frontend Development

**Install Dependencies:**

```bash
cd frontend
pnpm install
```

**Available Commands:**

```bash
# Development
pnpm run dev          # Start dev server
pnpm run build        # Build for production
pnpm run preview      # Preview production build

# Testing
pnpm run test         # Run unit tests (88 tests)
pnpm run test -- --watch    # Watch mode

# Code Quality
pnpm run lint         # Lint with Oxlint
```

**Frontend Documentation:**

- See [`frontend/README.md`](./frontend/README.md) for detailed frontend docs
- See [`frontend/STYLEGUIDE.md`](./frontend/STYLEGUIDE.md) for design system
- See [`frontend/src/components/ui/README.md`](./frontend/src/components/ui/README.md) for UI components

### Project Structure

```
falloutProject/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── admin/             # Admin panel views
│   │   ├── api/v1/endpoints/  # API endpoints
│   │   ├── core/              # Core configuration
│   │   ├── crud/              # CRUD operations
│   │   ├── db/                # Database setup
│   │   ├── models/            # SQLModel models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── tests/             # Test suite
│   │   └── utils/             # Utilities
│   ├── alembic/               # Database migrations
│   ├── locust/                # Performance tests
│   ├── Dockerfile
│   ├── pyproject.toml         # Python dependencies
│   └── uv.lock                # Locked dependencies
├── frontend/                   # Vue 3 Frontend
│   ├── src/
│   │   ├── assets/            # Styles (TailwindCSS)
│   │   ├── components/
│   │   │   ├── ui/            # 8 custom UI components
│   │   │   ├── common/        # Shared components
│   │   │   ├── auth/          # Auth components
│   │   │   ├── vault/         # Vault components
│   │   │   └── rooms/         # Room components
│   │   ├── composables/       # Vue composables
│   │   ├── router/            # Vue Router
│   │   ├── stores/            # Pinia stores
│   │   ├── views/             # Page components
│   │   └── main.ts            # Entry point
│   ├── tests/unit/            # Unit tests (88 tests)
│   ├── package.json           # JS dependencies
│   ├── vite.config.ts         # Vite config
│   ├── STYLEGUIDE.md          # Design system
│   └── MIGRATION_GUIDE.md     # VoidZero stack docs
├── docker-compose.yml
├── podman-compose.yml
└── CONTAINER_MIGRATION.md
```

## 🐳 Container Options

### Docker Compose

```bash
docker-compose up -d
docker-compose logs -f fastapi
docker-compose down
```

### Podman Compose

For a more secure, rootless alternative:

```bash
podman-compose up -d
podman-compose logs -f fastapi
podman-compose down
```

See [CONTAINER_MIGRATION.md](./CONTAINER_MIGRATION.md) for detailed Podman migration guide.

## 🧪 Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest app/tests/ -v

# Run with coverage
uv run pytest app/tests/ --cov=app --cov-report=html

# Run specific test
uv run pytest app/tests/test_api/test_vault.py -v

# Skip slow tests
uv run pytest app/tests/ -m "not slow"
```

### Frontend Tests

```bash
cd frontend

# Run all tests (88 tests)
pnpm run test

# Watch mode
pnpm run test -- --watch

# With coverage
pnpm run test -- --coverage
```

**Test Coverage:**

- Backend: Check `backend/htmlcov/index.html` after running with `--cov`
- Frontend: 88/88 tests passing (Auth, Vault, Components, Services, Router)

## 📊 Code Quality

### Backend Quality Tools

- **Ruff** - Linting and formatting (configured in `pyproject.toml`)
- **ty** - Type checking with Python 3.14 support
- **prek** - Pre-commit hooks for automated checks
- **pytest** - Test framework with async support
- **coverage** - Code coverage reporting

### Frontend Quality Tools

- **Oxlint** - Ultra-fast linting (50-100x faster than ESLint)
- **vue-tsc** - TypeScript type checking for Vue
- **Vitest** - Fast unit testing framework
- **TailwindCSS** - Utility-first CSS with design system

All checks run automatically on:

- Pre-commit (via hooks)
- Pull requests (via GitHub Actions)
- Before deployment

## 🔑 Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=fallout_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_HOSTNAME=localhost
MINIO_PORT=9000
MINIO_ROOT_USER=adminuser
MINIO_ROOT_PASSWORD=password123

# Auth
SECRET_KEY=your-secret-key-here

# Superuser
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=changeme
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### 1. Setup Development Environment

```bash
# Clone and setup
git clone <repo-url>
cd falloutProject/backend

# Install with dev dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
uv run prek install
```

### 2. Make Your Changes

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes and ensure quality
uv run ruff check .
uv run ruff format .
uv run ty check app/
uv run pytest app/tests/
```

### 3. Submit Pull Request

1. Push your branch to GitHub
2. Open a Pull Request with a clear description
3. Ensure all CI checks pass
4. Wait for code review

### Code Standards

- **Type hints**: All functions must have type annotations
- **Docstrings**: Public APIs need docstrings
- **Tests**: New features require tests
- **Formatting**: Ruff auto-formats on save (use pre-commit hooks)
- **Linting**: No ruff errors allowed
- **Type checking**: Pass ty checks

## 🐛 Troubleshooting

### Common Issues

**uv not found:**

```bash
# Ensure uv is in PATH
export PATH="$HOME/.cargo/bin:$PATH"  # Linux/macOS
# Or reinstall
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**PostgreSQL connection errors:**

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify credentials in .env match your PostgreSQL setup
```

**SQLModel composite primary key errors:**

```
This is a known issue with SQLModel + Pydantic 2.12.
The project includes workarounds in link table models.
```

**Python 3.14 not found:**

```bash
# Install Python 3.14 via uv
uv python install 3.14

# Or manually from python.org
# Then point uv to it
uv python pin 3.14
```

**Container port conflicts:**

```bash
# Check what's using the port
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Change port in docker-compose.yml or .env
```

### Getting Help

- 📖 **Documentation**: https://app.eraser.io/workspace/yjdEyc0bpOXOKVfbGpl0
- 🐛 **Issues**: Open an issue on GitHub
- 💬 **Discussions**: Use GitHub Discussions for questions

## 📚 Additional Resources

### Backend

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Podman Migration Guide](./CONTAINER_MIGRATION.md)

### Frontend

- [Vue 3 Documentation](https://vuejs.org/)
- [Vite Documentation](https://vitejs.dev/)
- [TailwindCSS v4 Beta](https://tailwindcss.com/docs/v4-beta)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Frontend README](./frontend/README.md)
- [Frontend Styleguide](./frontend/STYLEGUIDE.md)
- [UI Components](./frontend/src/components/ui/README.md)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Credits

- **Developer**: ElderEvil
- **Inspired by**: Fallout Shelter by Bethesda Softworks
- **Modern Tooling**: Thanks to the Astral team for uv, ruff, and the Rust-Python ecosystem

---

Built with ❤️ using Python, Vue and modern tooling

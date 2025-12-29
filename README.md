# Fallout Shelter Game 🏠☢️

A web-based simulation game where you manage a vault full of dwellers, balancing their needs and resources to keep the
vault thriving. Built with modern Python tooling and designed for Python 3.14.

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-blue.svg)](https://www.postgresql.org/)
[![Coverage](https://img.shields.io/badge/coverage-check%20reports-blue.svg)](#-testing)

## ✨ Tech Stack

- **Backend**: FastAPI + SQLModel + Pydantic v2
- **Database**: PostgreSQL 18 (with UUID v7 support)
- **Task Queue**: Celery + Redis
- **Storage**: MinIO
- **Frontend**: Vue.js
- **Container**: Docker/Podman
- **Production**: K3s (Kubernetes)

### Modern Python Tooling

This project uses cutting-edge Rust-based Python tools for maximum performance:

- 🦀 **[uv](https://github.com/astral-sh/uv)** - Ultra-fast package installer and resolver (replaces pip/pip-tools)
- 🦀 **[ruff](https://github.com/astral-sh/ruff)** - Blazingly fast Python linter and formatter (replaces
  flake8/black/isort)
- 🦀 **[prek](https://github.com/j178/prek)** - Modern pre-commit hook runner
- 🦀 **[ty](https://github.com/gao-artur/ty)** - Fast type checker (mypy alternative)

## 📋 Prerequisites

- **Python 3.14** (required)
- **PostgreSQL 18** (required for UUID v7)
- **Redis** (for Celery)
- **Docker/Podman** (optional, for containerized setup)

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

**Development Server:**

```bash
cd backend
uv run fastapi dev main.py
```

Visit [http://localhost:8000](http://localhost:8000) to start playing!

**Full Stack (with Docker/Podman):**

```bash
# From project root
docker-compose up -d
# OR
podman-compose up -d
```

## 🔧 Development

### Install Development Tools

```bash
cd backend

# Install all dependencies including dev/test groups
uv sync --all-extras --dev

# Install pre-commit hooks
prek install
```

### Available Commands

```bash
# Run tests
uv run pytest app/tests/

# Run tests with coverage
uv run pytest app/tests/ --cov=app --cov-report=html

# Type checking
uv run ty check app/

# Linting and formatting
uv run ruff check .
uv run ruff format .

# Run pre-commit checks manually
uv run prek run --all-files

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Start Celery worker (for background tasks)
uv run celery -A app.core.celery worker -l info

# Start Celery beat (for scheduled tasks)
uv run celery -A app.core.celery beat -l info
```

### Project Structure

```
falloutProject/
├── backend/
│   ├── app/
│   │   ├── admin/          # Admin panel views
│   │   ├── api/            # API endpoints
│   │   │   └── v1/
│   │   │       └── endpoints/
│   │   ├── core/           # Core configuration
│   │   ├── crud/           # CRUD operations
│   │   ├── db/             # Database setup
│   │   ├── models/         # SQLModel models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── tests/          # Test suite
│   │   └── utils/          # Utilities
│   ├── alembic/            # Database migrations
│   ├── Dockerfile
│   ├── pyproject.toml      # Dependencies & config
│   └── uv.lock            # Locked dependencies
├── frontend/               # Vue.js frontend
├── docker-compose.yml
├── podman-compose.yml
└── CONTAINER_MIGRATION.md  # Docker → Podman guide
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

```bash
cd backend

# Run all tests
uv run pytest app/tests/ -v

# Run specific test file
uv run pytest app/tests/test_api/test_vault.py -v

# Run with coverage report
uv run pytest app/tests/ --cov=app --cov-report=term-missing

# Run only fast tests (skip slow integration tests)
uv run pytest app/tests/ -m "not slow"
```

## 📊 Code Quality

The project uses automated code quality tools:

- **Ruff**: Linting and formatting (configured in `pyproject.toml`)
- **ty**: Type checking with Python 3.14 support
- **prek**: Pre-commit hooks for automated checks
- **pytest**: Test framework with async support

All checks run automatically on:

- Pre-commit (via prek hooks)
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

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Podman Migration Guide](./CONTAINER_MIGRATION.md)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Credits

- **Developer**: ElderEvil
- **Inspired by**: Fallout Shelter by Bethesda Softworks
- **Modern Tooling**: Thanks to the Astral team for uv, ruff, and the Rust-Python ecosystem

---

Built with ❤️ using Python 3.14 and modern tooling

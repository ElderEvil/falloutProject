# Fallout Shelter Game 🏠☢️

A web-based simulation game where you manage a vault full of dwellers, balancing their needs and resources to keep the
vault thriving. Built with modern Python tooling and designed for production deployment.

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/charliermarsh/ruff)
[![Python 3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-blue.svg)](https://www.postgresql.org/)
[![Vue 3.5](https://img.shields.io/badge/vue-3.5-00ff00.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.9-00ff00.svg)](https://www.typescriptlang.org/)

## ✨ Tech Stack

**Backend:** FastAPI · SQLModel · PostgreSQL 18 · Celery · Redis · MinIO · PydanticAI
**Frontend:** Vue 3.5 · TypeScript · Vite · Pinia · TailwindCSS v4 · Vitest
**Tooling:** uv · ruff · Rolldown · Oxlint · Docker/Podman

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** · **PostgreSQL 18** · **Redis**
- **Node.js 22+** · **pnpm 10.26+**
- **Docker/Podman** (optional but recommended)

### 1. Clone Repository

```bash
git clone <repository-url>
cd falloutProject
```

### 2. Generate Secret Key

```bash
# Generate a secure secret key for JWT authentication
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 3. Environment Setup

```bash
# Backend environment
cd backend
cp .env.example .env

# Edit .env and add your generated SECRET_KEY:
# SECRET_KEY=your-generated-secret-key-here
# Set other required variables (database, AI provider, etc.)

# Frontend environment
cd ../frontend
cp .env.example .env.local
# Edit .env.local if needed for frontend-specific settings
```

### 4. Start Development

#### Option 1: Full Stack with Containers (Recommended)

```bash
# Start all services with Docker Compose
docker-compose up -d

# Access the application
# Frontend: http://localhost:8080
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

#### Option 2: Manual Development

```bash
# Terminal 1: Backend Setup
cd backend

# Install dependencies
uv sync

# Database setup (if running natively)
createdb fallout_db  # Create PostgreSQL database
uv run alembic upgrade head  # Run migrations

# Start FastAPI development server
uv run fastapi dev main.py

# Terminal 2: Frontend Setup
cd frontend

# Install dependencies
pnpm install

# Generate API types from running backend
pnpm run types:generate

# Start Vue development server
pnpm run dev
```

**Access Points:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (if using containers)

---

## 🔧 Development

### Backend Development

```bash
cd backend

# Full development setup
uv sync --all-extras --dev && prek install

# Run tests
uv run pytest app/tests/                           # All tests
uv run pytest app/tests/test_api/test_auth.py     # Single test file
uv run pytest -k "test_login"                     # Pattern matching
uv run pytest --cov=app                           # With coverage

# Code quality
uv run ruff check .                               # Lint
uv run ruff check --fix .                         # Auto-fix
uv run ruff format .                              # Format code
uv run prek run                                   # Pre-commit hooks

# Database operations
uv run alembic upgrade head                       # Apply migrations
uv run alembic revision --autogenerate -m "msg"   # Create migration
```

### Frontend Development

```bash
cd frontend

# Install dependencies
pnpm install

# Generate API types from backend
pnpm run types:generate

# Run tests
pnpm test                                         # All tests
pnpm test tests/unit/stores/auth.test.ts         # Single test file
pnpm test --watch                                # Watch mode
pnpm test --coverage                             # With coverage

# Code quality
pnpm run lint                                    # Lint with Oxlint

# Build
pnpm run build                                   # Production build
pnpm run build:strict                            # Build with type checking
pnpm run preview                                 # Preview production build
```

### Full Stack Development Commands

```bash
# Start both backend and frontend in parallel
docker-compose up -d

# Or run manually in separate terminals:
# Terminal 1: cd backend && uv run fastapi dev main.py
# Terminal 2: cd frontend && pnpm run dev
```

---

## 🐳 Container Development

### Using Docker

```bash
# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild services
docker-compose up -d --build

# Access containers
docker exec -it fastapi bash
docker exec -it db psql -U postgres -d fallout_db
```

### Using Podman (Rootless)

```bash
# Alternative rootless containers
podman-compose up -d

# For Podman setup, see: docs/CONTAINER_MIGRATION.md
```

---

## 🔑 Environment Variables

### Core Configuration

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
# Application Security
SECRET_KEY=your-generated-secret-key
ENVIRONMENT=local  # local, staging, production

# Database Configuration
POSTGRES_SERVER=localhost  # or db (in containers)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=fallout_db

# Cache & Message Broker
REDIS_HOST=localhost  # or redis (in containers)
REDIS_PORT=6379

# AI Provider Configuration
AI_PROVIDER=openai  # openai, anthropic, ollama
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
OLLAMA_BASE_URL=http://localhost:11434/v1

# Object Storage
MINIO_HOSTNAME=localhost  # or minio (in containers)
MINIO_PORT=9000
MINIO_ROOT_USER=adminuser
MINIO_ROOT_PASSWORD=password123
MINIO_PUBLIC_URL=http://localhost:9000  # Production: https://media.yourdomain.com

# Authentication
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_EMAIL=admin@yourdomain.com
FIRST_SUPERUSER_PASSWORD=admin-password
USERS_OPEN_REGISTRATION=True  # Set to False in production

# Email Configuration (Mailpit for development)
SMTP_HOST=localhost  # mailpit in containers
SMTP_PORT=1025
EMAIL_FROM_ADDRESS=noreply@fallout-shelter.local
```

### Security Settings

```bash
# Rate Limiting (recommended for production)
ENABLE_RATE_LIMITING=True
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

---

## 📚 Documentation

### Essential Guides
- **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** - Complete deployment guide (local & production)
- **[DEPLOYMENT_CHECKLIST.md](./docs/DEPLOYMENT_CHECKLIST.md)** - Production deployment checklist
- **[SECURITY_GUIDE.md](./docs/SECURITY_GUIDE.md)** - Security configuration and best practices
- **[EXPLORATION_SYSTEM.md](./docs/EXPLORATION_SYSTEM.md)** - Core game system documentation

### Development Documentation
- **[AUDIT_REPORT.md](./docs/AUDIT_REPORT.md)** - Codebase audit and improvement areas
- **[TWELVE_FACTOR_COMPLIANCE.md](./docs/TWELVE_FACTOR_COMPLIANCE.md)** - Architecture methodology
- **[CONTAINER_MIGRATION.md](./docs/CONTAINER_MIGRATION.md)** - Docker to Podman migration

### Agent Resources
- **[AGENTS.md](./AGENTS.md)** - Development guide for AI coding agents
- **[skills/FASTAPI_101.md](./skills/FASTAPI_101.md)** - FastAPI tips and best practices

---

## 🎯 Project Structure

```
falloutProject/
├── backend/                  # FastAPI Python application
│   ├── app/
│   │   ├── api/v1/endpoints/ # API route handlers
│   │   ├── core/             # Security, config, logging
│   │   ├── crud/             # Database operations
│   │   ├── models/           # SQLModel database models
│   │   ├── services/         # Business logic layer
│   │   ├── utils/            # Utilities and helpers
│   │   ├── agents/           # AI agent implementations
│   │   └── tests/            # Test suite
│   ├── .env.example          # Environment template
│   └── pyproject.toml        # Python configuration
├── frontend/                 # Vue 3 TypeScript application
│   ├── src/
│   │   ├── components/       # Vue components
│   │   ├── stores/          # Pinia stores (state management)
│   │   ├── services/        # API services
│   │   ├── types/           # TypeScript definitions
│   │   └── views/           # Page components
│   ├── .env.example          # Frontend environment template
│   └── package.json          # Node.js configuration
├── docs/                     # Documentation
├── skills/                   # Agent skill resources
└── docker-compose.yml        # Development containers
```

---

## 🧪 Testing

### Backend Testing

```bash
cd backend

# Run all tests
uv run pytest app/tests/

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test patterns
uv run pytest -k "test_user"
uv run pytest app/tests/test_api/
```

### Frontend Testing

```bash
cd frontend

# Run all tests
pnpm test

# Run with coverage
pnpm test --coverage

# Run in watch mode
pnpm test --watch
```

---

## 🔍 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check if database is accessible
docker exec -it db psql -U postgres -d fallout_db -c "SELECT 1;"

# Verify connection string
docker-compose logs fastapi | grep -i database
```

#### Port Conflicts
```bash
# Check what's using ports
netstat -an | grep LISTEN | grep -E "(8000|5173|5432|6379|9000)"

# Kill conflicting processes
sudo lsof -ti:8000 | xargs kill -9
```

#### Permission Issues
```bash
# Fix Docker volume permissions
sudo chown -R $USER:$USER ./data  # If using local volumes

# Fix frontend node modules permissions
rm -rf node_modules package-lock.json && pnpm install
```

### Debug Commands

```bash
# Check service status
docker-compose ps

# View service logs
docker-compose logs -f fastapi
docker-compose logs -f frontend

# Access container shells
docker exec -it fastapi bash
docker exec -it frontend sh
```

---

## 🛡️ Security

### Production Security Checklist

- [ ] Generate strong `SECRET_KEY` using provided command
- [ ] Set `USERS_OPEN_REGISTRATION=False` in production
- [ ] Enable rate limiting: `ENABLE_RATE_LIMITING=True`
- [ ] Use HTTPS with valid SSL certificates
- [ ] Configure firewall rules to restrict access
- [ ] Set up monitoring and alerting
- [ ] Regularly update dependencies
- [ ] Use secrets management for production keys

### Security Resources

- **[SECURITY_GUIDE.md](./docs/SECURITY_GUIDE.md)** - Complete security configuration
- **[DEPLOYMENT_CHECKLIST.md](./docs/DEPLOYMENT_CHECKLIST.md)** - Production security checklist

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

Ensure all tests pass and code follows project style guidelines before submitting.

---

Built by [ElderEvil](https://github.com/ElderEvil) · Inspired by Fallout Shelter (Bethesda)

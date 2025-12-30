# Container Migration Guide: Docker → Podman

This guide covers migrating from Docker to Podman for local development and testing.

## Why Podman?

- **Rootless by default**: Better security, no daemon required
- **Docker-compatible**: Drop-in replacement for most Docker commands
- **K3s aligned**: Production uses K3s, Podman integrates better
- **Resource efficient**: Lower overhead than Docker Desktop

## Prerequisites

### Install Podman

**macOS:**
```bash
brew install podman podman-compose
podman machine init
podman machine start
```

**Linux:**
```bash
# Debian/Ubuntu
sudo apt-get install podman podman-compose

# Fedora/RHEL
sudo dnf install podman podman-compose
```

**Windows:**
```powershell
# Using winget
winget install RedHat.Podman

# Or download from https://podman.io/getting-started/installation
```

### Verify Installation

```bash
podman --version
podman-compose --version
```

## Migration Steps

### 1. Use Podman Compose File

The project now includes `podman-compose.yml` with proper image registry prefixes:

```bash
# Use podman-compose instead of docker-compose
podman-compose up -d
```

### 2. Alternative: Alias Docker Commands (Optional)

If you want to keep using `docker` commands:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias docker='podman'
alias docker-compose='podman-compose'
```

Then continue using familiar commands:
```bash
docker-compose up -d
docker ps
docker logs fastapi
```

### 3. Volume Management

Podman volumes work similarly but are stored differently:

```bash
# List volumes
podman volume ls

# Inspect volume
podman volume inspect postgres-data

# Remove volumes
podman volume rm postgres-data minio_data
```

### 4. Build & Run

**Using podman-compose:**
```bash
cd /path/to/falloutProject
podman-compose -f podman-compose.yml up --build -d
```

**Using podman directly:**
```bash
# Build backend image
podman build -t fallout-backend:latest ./backend

# Run with podman run
podman run -d \
  --name fastapi \
  --env-file .env \
  -p 8000:8000 \
  fallout-backend:latest
```

## Key Differences

### Image References

Podman requires full registry paths:
- ❌ `postgres:18-alpine`
- ✅ `docker.io/library/postgres:18-alpine`

The `podman-compose.yml` includes these prefixes.

### Networking

Podman creates networks differently:

```bash
# Docker
docker network create my-network

# Podman (automatic with compose)
podman network create my-network
```

### Rootless Mode

Podman runs rootless by default. Ports < 1024 require sysctl changes:

```bash
# Allow rootless port binding
echo 'net.ipv4.ip_unprivileged_port_start=80' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## Command Equivalents

| Docker | Podman |
|--------|--------|
| `docker ps` | `podman ps` |
| `docker images` | `podman images` |
| `docker logs` | `podman logs` |
| `docker exec` | `podman exec` |
| `docker-compose up` | `podman-compose up` |
| `docker-compose down` | `podman-compose down` |

## Development Workflow

### Start Services

```bash
# Start all services
podman-compose up -d

# View logs
podman-compose logs -f fastapi

# Check status
podman-compose ps
```

### Database Access

```bash
# Connect to PostgreSQL
podman exec -it falloutproject_db_1 psql -U postgres -d fallout_db

# Verify UUID7 function
podman exec -it falloutproject_db_1 psql -U postgres -d fallout_db -c "SELECT uuidv7();"
```

### Backend Shell

```bash
# Access FastAPI container
podman exec -it fastapi bash

# Run migrations
podman exec -it fastapi alembic upgrade head

# Run tests
podman exec -it fastapi pytest app/tests
```

### Stop Services

```bash
# Stop all
podman-compose down

# Stop and remove volumes
podman-compose down -v
```

## K3s Integration

Since production uses K3s, Podman integrates seamlessly:

### Build for K3s

```bash
# Build and export image
podman build -t fallout-backend:latest ./backend
podman save fallout-backend:latest -o backend.tar

# Import to K3s
sudo k3s ctr images import backend.tar
```

### Generate K3s YAML

```bash
# Generate Kubernetes manifests from compose
podman play kube podman-compose.yml > k8s-manifests.yaml
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Or kill all podman containers
podman stop $(podman ps -aq)
```

### Permission Issues

```bash
# Reset podman
podman system reset

# Restart podman machine (macOS/Windows)
podman machine stop
podman machine start
```

### Network Issues

```bash
# Recreate network
podman network rm podman
podman network create podman
```

## Performance Tips

### Enable Podman Machine Resources (macOS/Windows)

```bash
# Increase resources
podman machine stop
podman machine set --cpus 4 --memory 8192
podman machine start
```

### Volume Performance

Use named volumes instead of bind mounts for better performance:

```yaml
volumes:
  - postgres-data:/var/lib/postgresql/data  # Fast
  # - ./data:/var/lib/postgresql/data       # Slower
```

## CI/CD Considerations

For GitHub Actions, continue using Docker for now:
- GitHub Runners have Docker pre-installed
- Podman support is experimental
- Production K3s handles deployment

## References

- [Podman Documentation](https://docs.podman.io/)
- [Podman Compose](https://github.com/containers/podman-compose)
- [Docker to Podman Migration](https://podman.io/getting-started/docker)
- [K3s Documentation](https://docs.k3s.io/)

## Need Help?

If you encounter issues:
1. Check Podman logs: `podman-compose logs`
2. Verify service health: `podman-compose ps`
3. Restart services: `podman-compose restart`
4. Full reset: `podman-compose down -v && podman-compose up -d`

# Container Migration Guide

## Docker vs Podman

This guide covers migration from Docker to Podman for rootless container development.

### Why Podman?

- **Rootless**: Run containers without root privileges
- **Daemonless**: No background daemon required
- **Compatible**: Drop-in replacement for Docker CLI
- **Secure**: Enhanced security model

### Installation

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y podman podman-compose

# Fedora/CentOS
sudo dnf install -y podman podman-compose

# macOS (via Homebrew)
brew install podman

# Windows (via Chocolatey)
choco install podman
```

### Migration Commands

| Docker Command | Podman Equivalent |
|---------------|-------------------|
| `docker` | `podman` |
| `docker compose` | `podman-compose` |
| `docker run` | `podman run` |
| `docker ps` | `podman ps` |

### Project-Specific Changes

In `docker-compose.yml`, no changes required for basic compatibility:

```yaml
services:
  db:
    image: postgres:18
    # Works with both Docker and Podman
```

### Environment Setup

```bash
# Set up Podman system
podman system init

# Enable systemd services (if using user services)
systemctl --user enable --now podman.socket

# Verify installation
podman --version
podman-compose --version
```

### Development Workflow

```bash
# Start development environment
podman-compose up -d

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

### Known Differences

1. **Port Binding**: Podman may require different port binding syntax
2. **Volume Paths**: Absolute paths work more reliably
3. **Networking**: Podman uses slirp4netns by default for rootless

### Troubleshooting

#### Port Issues
```bash
# Check available ports
podman ps

# Force port binding
podman run -p 127.0.0.1:5432:5432 postgres
```

#### Permission Issues
```bash
# Fix volume permissions
podman unshare chown -R 1000:1000 ./data
```

#### Network Issues
```bash
# Check network configuration
podman network ls
podman network inspect bridge
```

### Development Tips

- Use `podman-compose` for compose files
- Consider `podman machine` for macOS/Windows
- Enable API socket for tooling compatibility
- Use `podman generate systemd` for service management

### Production Considerations

- Podman Systemd integration for production
- Quadlet for modern unit file generation
- Consider rootless containers for enhanced security

---

*This guide covers basic migration. For advanced usage, consult the official Podman documentation.*
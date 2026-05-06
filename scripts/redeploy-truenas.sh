#!/bin/bash
set -e

APP_DIR="/mnt/dead-pool/apps/fallout-shelter/config"
COMPOSE_URL="https://raw.githubusercontent.com/ElderEvil/falloutProject/master/docs/examples/docker-compose.truenas.yml"

echo "Redeploying Fallout Shelter on TrueNAS..."

cd "$APP_DIR"

echo "Downloading latest compose file..."
curl -fsSL -o compose.yml "$COMPOSE_URL"

echo "Pulling latest images..."
docker compose pull

echo "Stopping services..."
docker compose down

echo "Starting services..."
docker compose up -d

echo "Waiting for services to start..."
sleep 10

echo "Health check..."
curl -fsSL http://localhost:8000/healthcheck || echo "Backend health check failed"

echo "Redeploy complete!"
echo ""
echo "Status:"
docker compose ps

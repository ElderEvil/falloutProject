#!/bin/bash

# Fallout Shelter k3s Deployment Script
# This script builds and deploys the Fallout Shelter application to k3s

set -e

# Configuration
NAMESPACE="fallout-shelter"
REGISTRY=${REGISTRY:-"localhost:5000"}  # Local registry, change if needed
BACKEND_IMAGE="fallout-backend"
FRONTEND_IMAGE="fallout-frontend"
VERSION=${VERSION:-"latest"}

echo "🚀 Deploying Fallout Shelter to k3s..."
echo "Namespace: $NAMESPACE"
echo "Registry: $REGISTRY"
echo "Version: $VERSION"

# Check if k3s is running
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ k3s cluster is not accessible. Please ensure k3s is running."
    exit 1
fi

# Create namespace if it doesn't exist
echo "📦 Creating namespace..."
kubectl apply -f k8s/namespace.yaml

# Build and push Docker images
echo "🏗️  Building Docker images..."

# Build backend image
echo "Building backend..."
cd backend
docker build -t ${REGISTRY}/${BACKEND_IMAGE}:${VERSION} .
docker push ${REGISTRY}/${BACKEND_IMAGE}:${VERSION} || echo "⚠️  Push failed, ensure local registry is running"

# Build frontend image
echo "Building frontend..."
cd ../frontend
docker build --build-arg VITE_API_BASE_URL=http://fallout.local/api -t ${REGISTRY}/${FRONTEND_IMAGE}:${VERSION} .
docker push ${REGISTRY}/${FRONTEND_IMAGE}:${VERSION} || echo "⚠️  Push failed, ensure local registry is running"

cd ..

# Update image references in deployment files
echo "📝 Updating deployment manifests..."
sed -i.bak "s|fallout-backend:latest|${REGISTRY}/${BACKEND_IMAGE}:${VERSION}|g" k8s/backend.yaml
sed -i.bak "s|fallout-frontend:latest|${REGISTRY}/${FRONTEND_IMAGE}:${VERSION}|g" k8s/frontend.yaml
sed -i.bak "s|fallout-backend:latest|${REGISTRY}/${BACKEND_IMAGE}:${VERSION}|g" k8s/celery.yaml

# Apply configurations
echo "⚙️  Applying configurations..."

# ConfigMaps and Secrets
echo "Applying configs..."
kubectl apply -f k8s/config.yaml

# Database and Cache
echo "Deploying database and cache..."
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s

# Additional services
echo "Deploying additional services..."
kubectl apply -f k8s/services.yaml

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
kubectl wait --for=condition=ready pod -l app=minio -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=ollama -n $NAMESPACE --timeout=300s

# Backend and Workers
echo "Deploying backend and workers..."
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/celery.yaml

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
kubectl wait --for=condition=ready pod -l app=fastapi-backend -n $NAMESPACE --timeout=300s

# Frontend
echo "Deploying frontend..."
kubectl apply -f k8s/frontend.yaml

# Wait for frontend to be ready
echo "⏳ Waiting for frontend to be ready..."
kubectl wait --for=condition=ready pod -l app=vue-frontend -n $NAMESPACE --timeout=300s

# Ingress
echo "Configuring ingress..."
kubectl apply -f k8s/ingress.yaml

# Restore original files
echo "🧹 Cleaning up..."
mv k8s/backend.yaml.bak k8s/backend.yaml
mv k8s/frontend.yaml.bak k8s/frontend.yaml
mv k8s/celery.yaml.bak k8s/celery.yaml

# Show status
echo "📊 Deployment status:"
kubectl get pods -n $NAMESPACE
kubectl get services -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

echo "✅ Deployment completed!"
echo ""
echo "🌐 Access your application:"
echo "   Frontend: http://fallout.local (add to /etc/hosts if needed)"
echo "   API: http://fallout.local/api"
echo "   API (direct): http://fallout-api.local"
echo ""
echo "🔧 Useful commands:"
echo "   View logs: kubectl logs -f deployment/fastapi-backend -n $NAMESPACE"
echo "   Scale backend: kubectl scale deployment fastapi-backend --replicas=3 -n $NAMESPACE"
echo "   Port forward: kubectl port-forward service/fastapi-service 8000:8000 -n $NAMESPACE"

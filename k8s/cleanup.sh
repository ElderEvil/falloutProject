#!/bin/bash

# Fallout Shelter k3s Cleanup Script
# This script removes the Fallout Shelter application from k3s

set -e

NAMESPACE="fallout-shelter"

echo "🧹 Cleaning up Fallout Shelter deployment from k3s..."
echo "Namespace: $NAMESPACE"

# Check if k3s is running
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ k3s cluster is not accessible."
    exit 1
fi

# Delete resources in reverse order of creation
echo "🗑️  Removing ingress..."
kubectl delete -f k8s/ingress.yaml --ignore-not-found=true

echo "🗑️  Removing applications..."
kubectl delete -f k8s/frontend.yaml --ignore-not-found=true
kubectl delete -f k8s/backend.yaml --ignore-not-found=true
kubectl delete -f k8s/celery.yaml --ignore-not-found=true

echo "🗑️  Removing additional services..."
kubectl delete -f k8s/services.yaml --ignore-not-found=true

echo "🗑️  Removing database and cache..."
kubectl delete -f k8s/redis.yaml --ignore-not-found=true
kubectl delete -f k8s/postgres.yaml --ignore-not-found=true

echo "🗑️  Removing configs..."
kubectl delete -f k8s/config.yaml --ignore-not-found=true

echo "🗑️  Removing namespace..."
kubectl delete -f k8s/namespace.yaml --ignore-not-found=true

# Force delete any remaining pods
echo "🔥 Force deleting any remaining pods..."
kubectl delete pods --all -n $NAMESPACE --force --grace-period=0 --ignore-not-found=true

# Remove any remaining PVCs
echo "📦 Removing persistent volume claims..."
kubectl delete pvc --all -n $NAMESPACE --ignore-not-found=true

echo "✅ Cleanup completed!"
echo ""
echo "💡 To completely remove everything, you may also want to:"
echo "   - Remove Docker images: docker rmi fallout-backend fallout-frontend"
echo "   - Clean up any remaining PVCs: kubectl get pvc -A"

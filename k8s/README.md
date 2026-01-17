# Fallout Shelter k3s Deployment

This directory contains Kubernetes manifests and scripts for deploying the Fallout Shelter application to a k3s cluster.

## 🚀 Quick Start

### Prerequisites

- k3s cluster running and accessible via `kubectl`
- Docker installed and running
- (Optional) Local container registry for image distribution

### 1. Configure Secrets

Edit `k8s/config.yaml` and update the base64-encoded secrets:

```bash
# Generate base64 encoded secrets
echo -n "your-secret-key" | base64
echo -n "postgres" | base64
echo -n "postgres" | base64
echo -n "fallout_db" | base64
echo -n "minioadmin" | base64
echo -n "minioadmin" | base64
```

Replace the values in the `fallout-secrets` Secret.

### 2. Deploy

```bash
# Deploy the entire application
./k8s/deploy.sh
```

### 3. Access

Add to your `/etc/hosts` file:
```
127.0.0.1 fallout.local fallout-api.local
```

Then access:
- Frontend: http://fallout.local
- API: http://fallout.local/api
- API (direct): http://fallout-api.local

## 📁 File Structure

```
k8s/
├── namespace.yaml      # Kubernetes namespace
├── config.yaml          # ConfigMaps and Secrets
├── postgres.yaml        # PostgreSQL StatefulSet and Service
├── redis.yaml          # Redis Deployment and Service
├── backend.yaml        # FastAPI backend Deployment and Service
├── frontend.yaml       # Vue.js frontend Deployment and Service
├── celery.yaml         # Celery worker/beat and Flower monitoring
├── services.yaml       # MinIO and Ollama services
├── ingress.yaml        # Ingress configuration for external access
├── deploy.sh           # Deployment script
└── cleanup.sh          # Cleanup script
```

## 🔧 Customization

### Image Registry

By default, the deployment uses `localhost:5000` as the registry. To use a different registry:

```bash
export REGISTRY="your-registry.com"
export VERSION="v1.0.0"
./k8s/deploy.sh
```

### Resource Limits

Adjust resource requests and limits in the deployment files based on your cluster capacity.

### Storage

The deployment uses PersistentVolumeClaims for:
- PostgreSQL: 10Gi
- Redis: 5Gi
- MinIO: 20Gi
- Ollama: 50Gi

Adjust these sizes based on your needs.

## 🛠️ Useful Commands

### Monitor Deployment

```bash
# Watch pod status
watch kubectl get pods -n fallout-shelter

# View logs
kubectl logs -f deployment/fastapi-backend -n fallout-shelter
kubectl logs -f deployment/vue-frontend -n fallout-shelter

# Check services
kubectl get services -n fallout-shelter

# Check ingress
kubectl get ingress -n fallout-shelter
```

### Scaling

```bash
# Scale backend
kubectl scale deployment fastapi-backend --replicas=3 -n fallout-shelter

# Scale frontend
kubectl scale deployment vue-frontend --replicas=3 -n fallout-shelter
```

### Debugging

```bash
# Port forward to local machine
kubectl port-forward service/fastapi-service 8000:8000 -n fallout-shelter
kubectl port-forward service/vue-service 3000:3000 -n fallout-shelter

# Exec into pod
kubectl exec -it deployment/fastapi-backend -n fallout-shelter -- /bin/bash
```

### Database Access

```bash
# Port forward PostgreSQL
kubectl port-forward postgres-0 5432:5432 -n fallout-shelter

# Connect with psql
psql -h localhost -U postgres -d fallout_db
```

## 🔄 Development Workflow

1. Make changes to your code
2. Build and push new images:
   ```bash
   cd backend && docker build -t localhost:5000/fallout-backend:dev .
   cd frontend && docker build -t localhost:5000/fallout-frontend:dev .
   ```
3. Update image references in deployments:
   ```bash
   kubectl set image deployment/fastapi-backend fastapi=localhost:5000/fallout-backend:dev -n fallout-shelter
   kubectl set image deployment/vue-frontend vue=localhost:5000/fallout-frontend:dev -n fallout-shelter
   ```
4. Watch rollout:
   ```bash
   kubectl rollout status deployment/fastapi-backend -n fallout-shelter
   kubectl rollout status deployment/vue-frontend -n fallout-shelter
   ```

## 🔒 Security Considerations

- All secrets are stored as Kubernetes Secrets
- Services use ClusterIP for internal communication
- Ingress provides external access to only necessary services
- Consider using NetworkPolicies for additional security
- Enable HTTPS with cert-manager in production

## 📊 Monitoring

- Flower UI: Available at `http://fallout.local:5555` (if exposed via ingress)
- MinIO Console: Available at `http://fallout.local:9001` (if exposed via ingress)
- Kubernetes metrics: Use `kubectl top pods -n fallout-shelter`

## 🧹 Cleanup

Remove the entire deployment:

```bash
./k8s/cleanup.sh
```

## 🐛 Troubleshooting

### Common Issues

1. **Images not pulling**: Ensure your registry is accessible and images are pushed
2. **Database connection failures**: Check that PostgreSQL pod is ready and secrets are correct
3. **Frontend can't reach backend**: Verify service names and ingress configuration
4. **Persistent volume issues**: Check storage class and available storage

### Logs

Check logs for each service:
```bash
kubectl logs -l app=postgres -n fallout-shelter
kubectl logs -l app=redis -n fallout-shelter
kubectl logs -l app=fastapi-backend -n fallout-shelter
kubectl logs -l app=vue-frontend -n fallout-shelter
kubectl logs -l app=celery-worker -n fallout-shelter
kubectl logs -l app=minio -n fallout-shelter
kubectl logs -l app=ollama -n fallout-shelter
```

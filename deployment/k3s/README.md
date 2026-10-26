# k3s production manifests

These manifests are the Git baseline. `.github/workflows/deploy-hetzner.yml` sets the
release image tags with `kubectl set image`; the `:latest` tags here are only for a
fresh apply.

## Required external services

- **PostgreSQL** — the manifest includes a single-node Postgres. Production may use an
  external managed instance instead; confirm the actual major version and data layout
  before changing the image. Connection settings come from the `backend-env` secret.
- **Redis** — required by the API and the worker; it is not defined in this directory
  and is provisioned separately. It must be reachable at `REDIS_HOST` / `REDIS_PORT`
  from `backend-env`.
- **Object storage (RustFS/S3)** — optional; image/audio uploads degrade when it is
  unconfigured. Configure it through `RUSTFS_*` in `backend-env`.
- **SMTP** — optional; it is not part of readiness.

Only key names are documented here. Never commit `backend-env`, `postgres-secret`,
tokens or kubeconfig.

## Probes

- **Liveness:** `GET /healthcheck` — process responsiveness only.
- **Readiness:** `GET /readiness` — PostgreSQL and Redis only. Optional RustFS, local
  AI, SMTP and the worker broker do not remove an API pod from service.
- `/readiness` returns HTTP 503 when a critical dependency is unavailable. Do not point
  the liveness probe at it.

## Deploy order

`.github/workflows/deploy-hetzner.yml` stops the API/worker, backs up the database, runs
a release-image migration Job (`alembic current`, `upgrade head`, `current --check-heads`),
and only then rolls out backend, worker and frontend. Do not move migrations after the
rollout; an application rollback does not revert a migration.

## Worker

`dramatiq-worker-deployment.yaml` runs Periodiq and Dramatiq in one pod. Keep
`replicas: 1` until scheduler ownership is separated: multiple Periodiq instances can
enqueue duplicate periodic ticks. The worker has no HTTP probe; Kubernetes readiness is
satisfied once the container starts, and process failure restarts the pod.

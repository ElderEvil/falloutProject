# k3s production manifests

These manifests are the Git baseline. `.github/workflows/deploy-hetzner.yml` sets the
release image tags with `kubectl set image`; the `:latest` tags here are only for a
fresh apply. Services are declared in `services.yaml` as `backend-service`,
`frontend-service` and `postgres-service`; the ingress and `backend-env` depend on those
names.

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

With `maintenance_mode: true`, `.github/workflows/deploy-hetzner.yml` stops the API/worker
and backs up the database before migration and rollout. Maintenance mode defaults to
`false`: normal deployments leave writers running and do not create that backup.

With `run_migrations: true` (the default), a release-image migration Job runs
`alembic current`, `upgrade head` and `current --check-heads` before application rollout.
Disabling `run_migrations` skips this job. Use maintenance mode for changes that require
quiesced writers; normal deployments require migrations compatible with the running
release. An application rollback does not revert a migration.

The workflow updates images but does not apply these Deployment manifests. Apply reviewed
probe and worker configuration changes explicitly to the `fallout` namespace, preserving
the selected release image tags; applying the `:latest` baseline to an existing deployment
would replace its versioned image.

## Worker

`dramatiq-worker-deployment.yaml` runs Periodiq and Dramatiq in one pod. Keep
`replicas: 1` and `strategy.type: Recreate` until scheduler ownership is separated:
multiple Periodiq instances can enqueue duplicate periodic ticks. Recreate stops the old
pod before starting its replacement during rollouts. The worker has no HTTP probe;
Kubernetes readiness is satisfied once the container starts, and process failure restarts
the pod.

`DRAMATIQ_PROCESSES` controls the Dramatiq worker-process count (default `4` in the
manifest); Periodiq remains a single scheduler regardless of process count. Apply worker
configuration changes explicitly and keep the selected release image tag.

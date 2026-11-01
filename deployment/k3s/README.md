# k3s production manifests

These manifests are the Git baseline. `.github/workflows/deploy-hetzner.yml` sets the
release image tags with `kubectl set image`; the `:latest` tags here are only for a
fresh apply. Services are declared in `services.yaml` as `backend-service`,
`frontend-service` and `postgres-service`; the ingress and `backend-env` depend on those
names.

If an existing namespace still has the old `backend` / `frontend` Services, remove them
only after the new Services are ready:

```bash
kubectl apply -n fallout -f deployment/k3s/services.yaml
kubectl delete -n fallout service backend frontend --ignore-not-found
```

## Live state versus the Git baseline

Everything below is the **Git baseline** unless the live snapshot says otherwise. The deploy
workflow replaces the `:latest` baseline with a SemVer release tag and updates the `backend-env`
Secret; no image digest is pinned in Git. Confirm live values with read-only commands before
treating a repository difference as a live failure:

```bash
kubectl -n fallout get deployment,pod,job,svc,pvc,ingress
kubectl -n fallout get deployment backend dramatiq-worker frontend postgres \
  -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image
kubectl -n fallout get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].imageID}{"\n"}{end}'
kubectl get nodes -o wide
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.kubeletVersion}{"\n"}{end}'
```

Do not `kubectl apply` this directory over a live release. The baseline tags are only for a
fresh apply; applying them to an existing deployment would replace its versioned images.

### Live snapshot (2026-11-01)

```text
release:   v2.284.3
backend:   fo-shelter-be:v2.284.3 @ sha256:2afa9206ad47131c7ce88245cd2f0eccba3711254ecb739675a9701770bc7b4c
worker:    fo-shelter-be:v2.284.3 (same digest); 1 pod; replicas=1; strategy=Recreate
frontend:  fo-shelter-fe:v2.284.3 @ sha256:82dbb2268f81738c579a08148e9f171d3046996dcd4463e64d651dc6b9a7356b
postgres:  postgres:18-alpine @ sha256:54451ecb8ab38c24c3ec123f2fd501303a3a1856a5c66e98cecf2460d5e1e9d7
redis:     redis:alpine (in-cluster Deployment, not defined here) @ sha256:69f2c586c8a7e9cce4ae1ee9bbaf60bc4bb5f4bb3880e4ed022b1fd758a7cab9
node:      debian-8gb-hel1-1, k3s v1.29.6+k3s2, containerd 1.7.17-k3s1, Debian 12
storage:   postgres-pvc 10Gi local-path Bound; backend-logs-pvc 1Gi local-path Bound
ingress:   fallout.evillab.tech / fallout-api.evillab.tech (Traefik)
scheduler: exactly one long-lived periodiq process in the one worker pod
usage:     worker 106m/1,459Mi; backend 2m/299Mi; frontend 1m/5Mi; postgres 71m/1,491Mi; node 630m/6,564Mi
```

The live scheduler check used `kubectl exec deployment/dramatiq-worker` and scanned
`/proc/*/cmdline`; the shell wrapper and its child both contain the string, so the invariant is
one scheduler process plus its wrapper.


## Workload inventory (Git baseline)

| Workload | Kind | Replicas | Baseline image | Ports | Storage |
| --- | --- | ---: | --- | --- | --- |
| `backend` | Deployment | 1 | `elerevil/fo-shelter-be:latest` | 8000 | `backend-logs-pvc` → `/var/log/fallout_shelter` |
| `dramatiq-worker` | Deployment | 1 (`Recreate`) | `elerevil/fo-shelter-be:latest` | none | none |
| `frontend` | Deployment | 1 | `elerevil/fo-shelter-fe:latest` | 3000 | none |
| `postgres` | Deployment | 1 | `postgres:18-alpine` | 5432 | `postgres-pvc` → `/var/lib/postgresql` (PGDATA `/var/lib/postgresql/18/docker`) |
| `image-cleanup` | Job | one-shot | `alpine:3.22` | none | hostPath `/` (privileged) |
| `fallout-migrate-<run_id>-<attempt>` | Job (transient) | one-shot | release `fo-shelter-be` image | none | none |

`backend`, `dramatiq-worker`, `frontend` and `postgres` have no `namespace` in their files and
are applied to `fallout`. The migration Job is not checked in; the deploy workflow creates it
from the backend pod template with the target release image (`alembic current`, `upgrade head`,
`current --check-heads`, `ttlSecondsAfterFinished: 86400`). A live `backend` Deployment may also
carry a `run-migrations` init container set by an older workflow version.

The deploy workflow's `kubectl set image` replaces the baseline tags with `vX.Y.Z` release tags;
`image-cleanup-job.yaml` is run as a one-shot Job after a successful rollout.

### Services, ingress and PVCs

| Object | Type | Detail |
| --- | --- | --- |
| `backend-service` | ClusterIP | 8000 → 8000, selector `app=backend` |
| `frontend-service` | ClusterIP | 3000 → 3000, selector `app=frontend` |
| `postgres-service` | ClusterIP | 5432 → 5432, selector `app=postgres` |
| `fallout-ingress` | Ingress (traefik) | `fallout.evillab.tech` → frontend, `fallout-api.evillab.tech` → backend; TLS secret `fallout-ingress-tls` via cert-manager `letsencrypt` |
| `postgres-pvc` | PVC | 10 Gi, `ReadWriteOnce`, no `storageClassName` (cluster default) |
| `backend-logs-pvc` | PVC | 1 Gi, `ReadWriteOnce`, no `storageClassName` (cluster default) |

Traefik is configured through the `traefik` `HelmChartConfig` in `kube-system`. cert-manager and
the k3s datastore are cluster-level dependencies that are not defined in this directory.

### Probes

| Workload | Liveness | Readiness | Startup |
| --- | --- | --- | --- |
| `backend` | `GET /healthcheck`, initial 30s, period 10s, timeout 5s, 3 failures | `GET /readiness`, initial 10s, period 5s, timeout 3s, 3 failures (HTTP 503 when PostgreSQL or Redis is unavailable) | none |
| `frontend` | none | none | none |
| `dramatiq-worker` | none | none; Kubernetes marks it ready when the container starts, and a process exit restarts the pod | none |
| `postgres` | none | none | none |

No workload has a startup probe. Optional RustFS, local AI, SMTP and the worker broker are
excluded from readiness, so they cannot remove an otherwise healthy API pod from service.
`/readiness` is deliberately not the liveness endpoint: a dependency outage removes the API from
service without restarting it.

## Required external services

- **PostgreSQL** — `postgres-deployment.yaml` is the in-cluster baseline (single replica,
  `postgres:18-alpine`, PGDATA `/var/lib/postgresql/18/docker`). Production may use an external managed instance
  instead; in that case this manifest is not authoritative. Confirm the live major version, data
  layout and provider backup policy before changing anything. Connection settings come from the
  `backend-env` Secret.
- **Redis** — required by the API and the worker; readiness-critical. It is not defined in this
  directory and is provisioned separately. It must be reachable at `REDIS_HOST` / `REDIS_PORT`
  from `backend-env`. Losing it can drop queued messages and tick leases; it is not a source of
  durable game data and has no backup here.
- **Object storage (RustFS/S3)** — optional; image/audio uploads degrade when it is
  unconfigured. Configure it through `RUSTFS_*` in `backend-env`. It is not part of readiness and
  is not backed up by this repository; inventory its buckets and lifecycle separately.
- **SMTP** — optional; not part of readiness. See [Production Email](../../docs/DEPLOYMENT.md#production-email-mailcow-on-hetzner).

Only key names are documented here. Never commit `backend-env`, `postgres-secret`, tokens or
kubeconfig.

## Backup and restore boundaries

| Data | Backup in this repository | Restore path |
| --- | --- | --- |
| Application PostgreSQL | Only a `maintenance_mode=true` deploy creates a custom-format dump on the server at `~/fallout-backups/pre-<tag>-<run_id>.dump`; verified with `pg_restore --list` only. No off-host copy, rotation or retention. | Restore drill required: [`scripts/restore-drill.sh`](../../scripts/restore-drill.sh) and [Isolated restore drill](../../docs/DEPLOYMENT.md#isolated-restore-drill). Never restore over production. |
| `postgres-pvc` | Not a backup; no volume snapshot is defined here. | Depends on the cluster's PV/storage provider. |
| `backend-logs-pvc` | Logs only; 14-day rotation. Not application data. | Not restored. |
| Redis | No backup. | Rebuilt empty; queued work and leases are lost. |
| Object storage (RustFS/S3) | Not covered by this repository. | Provider/bucket policy only; verify separately. |
| k3s datastore and server token | Not covered by this repository. | Follow [k3s datastore backup/restore](https://docs.k3s.io/datastore/backup-restore). |
| Container images | Release images remain in the registry; the cleanup Job keeps two release tags locally. | Re-pull from the registry. |

The deploy workflow's archive listing checks readability, not full restoreability. A production
dump must pass the isolated drill before it is treated as a recovery asset.


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

## Worker and scheduler ownership

`dramatiq-worker-deployment.yaml` is the **only checked-in k3s workload** that starts a periodic
scheduler. Its command starts exactly one `periodiq app.core.dramatiq app.api.tasks` process and
one Dramatiq consumer process group:

```text
periodiq app.core.dramatiq app.api.tasks &   # one scheduler
dramatiq --processes "$DRAMATIQ_PROCESSES" …  # 2 consumer processes (baseline)
```

The backend image's default command is the API (`uvicorn`); `frontend-deployment.yaml` and
`postgres-deployment.yaml` start no scheduler. `PeriodiqMiddleware` is registered on the
Dramatiq broker, but it only validates/processes scheduled messages in consumers; enqueueing is
done by the dedicated `periodiq` CLI process. `DRAMATIQ_PROCESSES` controls consumer
concurrency only; it does not create additional schedulers. The manifest baseline is **2**
consumer processes.

Keep both of these invariants until scheduler ownership is separated:

- `spec.replicas: 1` — a second worker pod would start a second Periodiq and could enqueue
  the same periodic tick twice.
- `strategy.type: Recreate` — the old pod stops before its replacement starts during a
  rollout, so two schedulers do not overlap.

Read-only live check:

```bash
kubectl -n fallout get deployment dramatiq-worker \
  -o jsonpath='{.spec.replicas}{" "}{.spec.strategy.type}{"\n"}'
kubectl -n fallout get pods -l app=dramatiq-worker -o name
kubectl -n fallout exec deployment/dramatiq-worker -- \
  sh -c 'for p in /proc/[0-9]*; do c=$(tr "\0" " " < "$p/cmdline" 2>/dev/null); printf "%s\n" "$c" | grep -q "[p]eriodiq" && echo "${p#/proc/}: $c"; done'
```

Expected: one worker pod, `replicas` 1, `Recreate`, and exactly one `periodiq` process.
`backend/app/tests/test_infra/test_k3s_manifests.py` fails if another checked-in workload
invokes `periodiq` or if the worker stops using `replicas: 1` / `Recreate`.

The game tick has a recent-tick-id duplicate guard and some tick paths take PostgreSQL advisory
locks, but those reduce duplicate *processing* side effects; they do not prevent duplicate
*enqueueing* or the wasted worker capacity and repeated logs it causes. Before scaling, choose
one of:

1. **Split ownership (preferred).** Add a separate scheduler Deployment with `replicas: 1`
   and `Recreate` that runs only `periodiq`, and a consumer Deployment that runs only
   `dramatiq` at `N` replicas. Remove `periodiq` from the consumer command.
2. **Keep the combined pod at `replicas: 1`.** Scale consumers by raising
   `DRAMATIQ_PROCESSES` within the existing memory/CPU limits, not by adding pods.

Do not add a second `periodiq` invocation to a sidecar, init container or replica. The worker
has no HTTP probe; Kubernetes readiness is satisfied once the container starts, and process
failure restarts the pod. Apply worker configuration changes explicitly and keep the selected
release image tag.


## Image cleanup

`image-cleanup-job.yaml` is a one-shot privileged Job. It mounts the host root, selects
only `fo-shelter-be` / `fo-shelter-fe` tags, and keeps the latest **two** releases
(current + previous) before deleting older tags through the host's `k3s crictl`. It validates
`KEEP_RELEASES`, skips tags referenced by running containers, and has no service
account token or access to unrelated repositories.

The deploy workflow runs it after a successful rollout. Apply it manually with:

```bash
kubectl delete -n fallout job image-cleanup --ignore-not-found
kubectl apply -n fallout -f deployment/k3s/image-cleanup-job.yaml
kubectl -n fallout wait --for=condition=complete job/image-cleanup --timeout=180s
kubectl -n fallout logs job/image-cleanup
kubectl -n fallout delete job image-cleanup
```

The Job is intentionally privileged and host-root mounted; treat it as a controlled
cleanup primitive, not a general-purpose pod. On a multi-node cluster it only cleans the
node where it schedules.

## Issue #885 closure evidence

This section maps the issue's prioritized checklist to repository evidence. It deliberately
separates verified repository facts from live-cluster facts. A maintainer-facing index of the
same checklist with the recorded drill output is
[`docs/planning/ISSUE_885_EVIDENCE.md`](../../docs/planning/ISSUE_885_EVIDENCE.md).

| Checklist item | Status | Evidence |
| --- | --- | --- |
| Inventory live workloads, image versions, dependencies, storage, probes and node topology | **Done — live snapshot recorded 2026-11-01** | Live snapshot above plus the workload/service/PVC/probe tables. |
| Check in worker configuration and align manifests/image selection with the release workflow; document external dependencies | **Done** | Checked-in `dramatiq-worker-deployment.yaml`; baseline images are `fo-shelter-be` / `fo-shelter-fe`; deploy workflow sets versioned tags; Redis, optional S3/SMTP and possible external PostgreSQL are documented above. |
| Release-image migration Job and explicit migration/rollout/rollback sequence; migration failure prevents rollout | **Done** | `.github/workflows/deploy-hetzner.yml` runs the target image in a dedicated Job (`alembic current`, `upgrade head`, `current --check-heads`) before application rollout and aborts on failure; `docs/DEPLOYMENT.md` documents the maintenance/backup/rollback sequence. |
| Separate readiness from liveness; dependency failure removes API without restart storms | **Done** | `backend-deployment.yaml` uses `/healthcheck` for liveness and `/readiness` for readiness; `/readiness` returns 503 for PostgreSQL/Redis failure and excludes optional integrations (`backend/main.py`); guarded by `test_k3s_manifests.py`. |
| Verify scheduler ownership and safe API/worker scaling independently | **Done — one live scheduler process and one worker pod** | Exactly one checked-in `periodiq` invoker, `replicas: 1`, `Recreate`; manifest test enforces it. The live `/proc` scan confirmed one long-lived scheduler. |
| Confirm worker and other workload requests/limits against measured usage | **Partial** | Backend and worker have requests/limits; image-cleanup requests 10m/16Mi with 100m/64Mi limits; frontend and postgres have none. Actual live usage was not measured for this evidence, so frontend/postgres budgets remain open. |
| Document backups and demonstrate recovery of cluster state, PostgreSQL and assets in isolation | **Production PostgreSQL dump + application readiness demonstrated; cluster state and assets pending** | Production `pg_dump -Fc` restored locally and API readiness passed ([Production drill](../../docs/DEPLOYMENT.md#drill-evidence-2026-11-01-production-data)). k3s datastore/server-token and RustFS/S3 restore were not demonstrated; this repository has no backup automation for them. |

Remaining before closing #885:

1. Record the read-only live inventory (replicas, image tags/digests, PVC binding/storage class,
   Redis and object-storage providers, node topology).
2. Confirm off-host retention for the k3s datastore and server token, PostgreSQL dumps, and
   object storage, then rehearse the k3s datastore and asset restore in isolation.
3. Re-run `scripts/restore-drill.sh` with the latest **production** dump and the matching
   release image. The recorded local drill used a current-schema synthetic dump, not production
   data.
4. Record measured worker/frontend/postgres usage and add requests/limits where the measurement
   justifies them.

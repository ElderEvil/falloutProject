# Issue #885 closeout evidence

Status as of 2026-11-01, branch `chore/k3s-recovery-885` based on `origin/master` (`4892faae`).
This page is the maintainer-facing index; the detailed inventory, scheduler contract and live
commands live in [`deployment/k3s/README.md`](../../deployment/k3s/README.md#issue-885-closure-evidence).
The restore runbook lives in [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md#isolated-restore-drill).

## Checklist

| #885 checklist item | State | Where to verify |
| --- | --- | --- |
| Inventory live workloads, image versions, dependencies, storage, probes, node topology | **Done — live snapshot recorded 2026-11-01** | [inventory][k3s-inventory], [live snapshot][k3s-live] |
| Check in worker configuration; align manifests/image selection with the release workflow; document external dependencies | Done | [worker][k3s-worker], [external services][k3s-ext] |
| Release-image migration Job before rollout; explicit migration/rollout/rollback sequence | Done | `.github/workflows/deploy-hetzner.yml`; `docs/DEPLOYMENT.md` |
| Separate readiness from liveness; dependency failure removes API without restart storms | Done | `deployment/k3s/backend-deployment.yaml`; `backend/main.py` |
| Verify scheduler ownership and safe API/worker scaling | **Done — one live Periodiq process, one worker pod, `Recreate`** | [scheduler ownership][k3s-sched]; `test_k3s_manifests.py` |
| Confirm worker/other workload requests and limits against measured usage | Partial | [closure table][k3s-close]; frontend and Postgres have no budgets |
| Document backups and demonstrate recovery in isolation | **PostgreSQL production dump + application readiness demonstrated; cluster state and assets pending** | [restore drill][drill]; evidence below |

[k3s-inventory]: ../../deployment/k3s/README.md#workload-inventory-git-baseline
[k3s-live]: ../../deployment/k3s/README.md#live-state-versus-the-git-baseline
[k3s-worker]: ../../deployment/k3s/README.md#worker-and-scheduler-ownership
[k3s-ext]: ../../deployment/k3s/README.md#required-external-services
[k3s-sched]: ../../deployment/k3s/README.md#worker-and-scheduler-ownership
[k3s-close]: ../../deployment/k3s/README.md#issue-885-closure-evidence
[drill]: ../DEPLOYMENT.md#isolated-restore-drill

## Isolated restore drill evidence

Run locally with Podman 5.8.9, `postgres:18-alpine`, and a custom-format dump created by running
all current Alembic migrations against a scratch PostgreSQL 18.6 container (not production data):

```text
command:   ./scripts/restore-drill.sh --dump /tmp/drill-source.dump \
             --expected-revision d1f3a5c7e9b2 \
             --app-command 'cd backend && exec uv run uvicorn main:app --host 127.0.0.1 --port "$DRILL_APP_PORT"'
dump:      drill-source.dump, 172,277 bytes
sha256:    f68f025b617813c32aee7bd992bdd2654e337b71832ad7fd1953cd48dfca6a91
revision:  d1f3a5c7e9b2
result:    archive entries=433; restore ok; tables=46; vaults=1; users=1; dwellers=0
readiness: HTTP 200 status=ready postgres=healthy redis=healthy
RESULT:    PASS
```

The script rejects invalid archives before starting a database, rejects a revision mismatch, and
cleans up its containers, network and host process on exit. No production database, cluster or
image was touched.

## Live production snapshot (2026-11-01)

Read-only from `hetzner` (`kubectl`), production release **v2.284.3**:

```text
workloads: backend 1/1, dramatiq-worker 1/1, frontend 1/1, postgres 1/1, redis 1/1
images:    fo-shelter-be:v2.284.3 (sha256:2afa9206…), fo-shelter-fe:v2.284.3 (sha256:82dbb226…)
postgres:  postgres:18-alpine (sha256:54451ecb…), PGDATA /var/lib/postgresql/18/docker
node:      debian-8gb-hel1-1, k3s v1.29.6+k3s2, containerd 1.7.17-k3s1, Debian 12
storage:   postgres-pvc 10Gi local-path Bound; backend-logs-pvc 1Gi local-path Bound
ingress:   fallout.evillab.tech / fallout-api.evillab.tech (Traefik)
scheduler: deployment replicas=1, strategy=Recreate; 2 Dramatiq processes; one periodiq process in the worker pod
usage:     worker ~510m/1,171Mi; backend ~72m/312Mi; frontend ~1m/5Mi; postgres ~20m/1,221Mi
```

The live check used a read-only `kubectl exec` scan of `/proc/*/cmdline`; the only long-lived
`periodiq` process was the worker's scheduler. The command also sees the shell wrapper's own
`periodiq` string, so the invariant is one scheduler process plus its wrapper, not one line.

## Production-data restore drill (2026-11-01)

A read-only `pg_dump -Fc` was streamed from the production PostgreSQL pod and restored locally
with the same script. This is the first drill against actual production data, not a synthetic
current-schema dump:

```text
dump:      /tmp/fallout-prod-20261101.dump, 3,268,036 bytes
sha256:    b7948568ed74a0ab674322e464e8790fe41adff883782e2b4b57653e0bd5e417
revision:  d1f3a5c7e9b2
result:    archive entries=435; restore ok; tables=46; vaults=80; users=38; dwellers=2447
readiness: HTTP 200 status=ready postgres=healthy redis=healthy
RESULT:    PASS
```

## Remaining before closing

1. Confirm off-host retention and rehearse restore for the k3s datastore/server token and
   RustFS/S3 assets; neither is automated in this repository today.
2. Measure frontend/Postgres resource usage and add justified requests/limits (the live sample is
   recorded above; the manifests still have no budgets for those two workloads).

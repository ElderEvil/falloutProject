#!/usr/bin/env bash
# Restore a verified PostgreSQL custom-format backup into an isolated scratch
# database, verify its schema, and optionally prove the application becomes
# ready against it. Nothing in this script can address a database outside the
# containers it creates itself: there is no target-connection option.
#
# Usage:
#   scripts/restore-drill.sh --dump /path/to/pre-v2.284.0-123.dump \
#     --expected-revision <alembic-head> \
#     --app-image elerevil/fo-shelter-be:v2.284.0
#
# or, for an application process already running on the host:
#   scripts/restore-drill.sh --dump backup.dump \
#     --app-command 'cd backend && uv run uvicorn main:app --host 127.0.0.1 --port "$DRILL_APP_PORT"'
#
# See docs/DEPLOYMENT.md ("Isolated restore drill") for the runbook.

set -euo pipefail

PROGRAM="restore-drill"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:18-alpine}"
REDIS_IMAGE="${REDIS_IMAGE:-redis:alpine}"
DUMP=""
EXPECTED_REVISION=""
APP_IMAGE=""
APP_COMMAND=""
APP_PORT=""
TIMEOUT_SECONDS=180
KEEP=0
ENGINE=""

log() { printf '[%s] %s\n' "$PROGRAM" "$*"; }
die() {
  printf '[%s] error: %s\n' "$PROGRAM" "$*" >&2
  exit 1
}

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --dump FILE             pg_dump custom-format (-Fc) archive to restore (required)
  --expected-revision REV Assert alembic_version.version_num equals REV
  --app-image IMAGE       Start this backend image plus scratch Redis and poll /readiness
  --app-command CMD       Run CMD on the host against the scratch DB/Redis and poll /readiness
                          (CMD receives DRILL_APP_PORT, DRILL_POSTGRES_*, DRILL_REDIS_*)
  --app-port PORT         Host port for the readiness endpoint (default: random free port)
  --timeout SECONDS       Readiness timeout (default: 180)
  --engine podman|docker  Container engine (default: auto-detect)
  --keep                  Keep scratch containers and network for inspection
  -h, --help              Show this help

Safety: the only writable database this script can reach is the scratch
container it creates. It never accepts a database URL. The dump is read only.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump) DUMP="${2:-}"; shift 2 ;;
    --expected-revision) EXPECTED_REVISION="${2:-}"; shift 2 ;;
    --app-image) APP_IMAGE="${2:-}"; shift 2 ;;
    --app-command) APP_COMMAND="${2:-}"; shift 2 ;;
    --app-port) APP_PORT="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="${2:-}"; shift 2 ;;
    --engine) ENGINE="${2:-}"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
done

[[ -n "$DUMP" ]] || die "--dump is required"
[[ -f "$DUMP" ]] || die "dump not found: $DUMP"
[[ -r "$DUMP" ]] || die "dump not readable: $DUMP"
[[ -s "$DUMP" ]] || die "dump is empty: $DUMP"
[[ -z "$APP_IMAGE" || -z "$APP_COMMAND" ]] || die "--app-image and --app-command are mutually exclusive"

if [[ -z "$ENGINE" ]]; then
  if command -v podman >/dev/null 2>&1; then
    ENGINE=podman
  elif command -v docker >/dev/null 2>&1; then
    ENGINE=docker
  else
    die "neither podman nor docker is installed"
  fi
fi
command -v "$ENGINE" >/dev/null 2>&1 || die "container engine not found: $ENGINE"
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUFFIX="$$"
NETWORK="${PROGRAM}-${SUFFIX}"
PG_CONTAINER="${PROGRAM}-pg-${SUFFIX}"
REDIS_CONTAINER="${PROGRAM}-redis-${SUFFIX}"
APP_CONTAINER="${PROGRAM}-app-${SUFFIX}"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/${PROGRAM}.XXXXXX")"
PG_PASSWORD="drill-$(python3 -c 'import secrets;print(secrets.token_hex(16))')"
PG_DB="fallout_restore"
APP_PID=""

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

free_port() {
  python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

wait_for_postgres() {
  local deadline=$((SECONDS + 60))
  # Wait for the target database, not just the server: the entrypoint starts
  # PostgreSQL before its init scripts have created POSTGRES_DB.
  until "$ENGINE" exec "$PG_CONTAINER" psql -U postgres -d "$PG_DB" -tAc 'SELECT 1' >/dev/null 2>&1; do
    ((SECONDS < deadline)) || return 1
    sleep 1
  done
}

psql_scalar() {
  "$ENGINE" exec "$PG_CONTAINER" psql -U postgres -d "$PG_DB" -v ON_ERROR_STOP=1 -tAc "$1"
}

cleanup() {
  local status=$?
  if [[ -n "$APP_PID" ]]; then
    # The host app is started with setsid, so its PID is its process-group id.
    kill -- -"$APP_PID" >/dev/null 2>&1 || kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP" -eq 0 ]]; then
    for container in "$APP_CONTAINER" "$REDIS_CONTAINER" "$PG_CONTAINER"; do
      "$ENGINE" rm -f "$container" >/dev/null 2>&1 || true
    done
    "$ENGINE" network rm "$NETWORK" >/dev/null 2>&1 || true
    rm -rf "$WORKDIR"
  else
    log "kept containers: $PG_CONTAINER ${REDIS_CONTAINER} ${APP_CONTAINER}"
    log "diagnostic logs in: $WORKDIR"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

start_postgres() {
  "$ENGINE" run -d --rm \
    --name "$PG_CONTAINER" \
    --network "$NETWORK" \
    -e POSTGRES_PASSWORD="$PG_PASSWORD" \
    -e POSTGRES_DB="$PG_DB" \
    -p "127.0.0.1:${PG_HOST_PORT}:5432" \
    "$POSTGRES_IMAGE" >/dev/null
  wait_for_postgres || {
    "$ENGINE" logs "$PG_CONTAINER" >&2 || true
    die "scratch PostgreSQL did not become ready"
  }
}

start_redis() {
  "$ENGINE" run -d --rm \
    --name "$REDIS_CONTAINER" \
    --network "$NETWORK" \
    -p "127.0.0.1:${REDIS_HOST_PORT}:6379" \
    "$REDIS_IMAGE" >/dev/null
}

readiness_json() {
  curl -fsS --max-time 5 "$1" 2>/dev/null
}

wait_for_readiness() {
  local url="$1" deadline=$((SECONDS + TIMEOUT_SECONDS)) body=""
  until body="$(readiness_json "$url")"; do
    ((SECONDS < deadline)) || {
      log "last readiness response: ${body:-<none>}"
      return 1
    }
    sleep 2
  done
  printf '%s' "$body"
}

# ---------------------------------------------------------------------------
# drill
# ---------------------------------------------------------------------------

log "engine: $ENGINE"
log "archive: $DUMP ($(wc -c <"$DUMP") bytes)"

"$ENGINE" network create "$NETWORK" >/dev/null
PG_HOST_PORT="$(free_port)"
REDIS_HOST_PORT="$(free_port)"
APP_PORT="${APP_PORT:-$(free_port)}"

# 1. Verify the archive is readable before spending time on a cluster. Reading
#    through stdin avoids a host bind mount and its SELinux relabel requirement.
log "verifying custom-format archive with pg_restore --list"
if ! "$ENGINE" run --rm -i "$POSTGRES_IMAGE" pg_restore --list \
  <"$DUMP" >"$WORKDIR/archive.list" 2>"$WORKDIR/archive.err"; then
  cat "$WORKDIR/archive.err" >&2
  die "pg_restore cannot read $DUMP (not a valid custom-format backup?)"
fi
log "archive entries: $(awk '!/^;/ && NF' "$WORKDIR/archive.list" | wc -l)"

# 2. Restore into the scratch database. --single-transaction keeps a failed
#    restore from leaving a half-populated database that looks usable.
log "starting isolated PostgreSQL ($POSTGRES_IMAGE) in network $NETWORK"
start_postgres
log "restoring into scratch database $PG_DB"
"$ENGINE" exec -i "$PG_CONTAINER" pg_restore \
  --no-owner --no-privileges --exit-on-error --single-transaction \
  -U postgres -d "$PG_DB" <"$DUMP"
log "restore: ok"

# 3. Verify schema.
tables="$(psql_scalar "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"
missing="$(psql_scalar "SELECT string_agg(name, ',') FROM (VALUES ('alembic_version'), ('vault'), ('\"user\"'), ('dweller')) AS required(name) WHERE to_regclass('public.' || required.name) IS NULL")"
[[ -z "$missing" ]] || die "restored schema is missing tables: $missing"
revisions="$(psql_scalar "SELECT count(*) FROM alembic_version")"
[[ "$revisions" == "1" ]] || die "expected exactly one alembic_version row, got $revisions"
revision="$(psql_scalar "SELECT version_num FROM alembic_version")"
[[ -n "$revision" ]] || die "alembic_version is empty"
if [[ -n "$EXPECTED_REVISION" && "$revision" != "$EXPECTED_REVISION" ]]; then
  die "restored schema revision $revision != expected $EXPECTED_REVISION"
fi
vaults="$(psql_scalar "SELECT count(*) FROM vault")"
users="$(psql_scalar "SELECT count(*) FROM \"user\"")"
dwellers="$(psql_scalar "SELECT count(*) FROM dweller")"
log "schema: tables=$tables revision=$revision vaults=$vaults users=$users dwellers=$dwellers"

# 4. Application readiness against the restored database.
if [[ -n "$APP_IMAGE" || -n "$APP_COMMAND" ]]; then
  log "starting scratch Redis ($REDIS_IMAGE)"
  start_redis
  app_url="http://127.0.0.1:${APP_PORT}/readiness"

  if [[ -n "$APP_IMAGE" ]]; then
    log "checking that app image is available: $APP_IMAGE"
    "$ENGINE" image inspect "$APP_IMAGE" >/dev/null 2>&1 || "$ENGINE" pull "$APP_IMAGE" >/dev/null
    log "starting isolated app container in network $NETWORK"
    "$ENGINE" run -d \
      --name "$APP_CONTAINER" \
      --network "$NETWORK" \
      -p "127.0.0.1:${APP_PORT}:8000" \
      -e ENVIRONMENT=local \
      -e ENABLE_RATE_LIMITING=false \
      -e SECRET_KEY=restore-drill-not-a-production-secret \
      -e EMAIL_TEST_USER=drill@example.com \
      -e FIRST_SUPERUSER_USERNAME=drill \
      -e FIRST_SUPERUSER_EMAIL=drill@example.com \
      -e FIRST_SUPERUSER_PASSWORD=drill-not-a-production-password \
      -e USERS_OPEN_REGISTRATION=false \
      -e POSTGRES_SERVER="$PG_CONTAINER" \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_PASSWORD="$PG_PASSWORD" \
      -e POSTGRES_DB="$PG_DB" \
      -e REDIS_HOST="$REDIS_CONTAINER" \
      -e REDIS_PORT=6379 \
      "$APP_IMAGE" >/dev/null
  else
    command -v setsid >/dev/null 2>&1 || die "setsid is required for --app-command cleanup"
    log "running app command against scratch DB/Redis"
    export DRILL_APP_PORT="$APP_PORT"
    export DRILL_POSTGRES_SERVER=127.0.0.1
    export DRILL_POSTGRES_PORT="$PG_HOST_PORT"
    export DRILL_POSTGRES_USER=postgres
    export DRILL_POSTGRES_PASSWORD="$PG_PASSWORD"
    export DRILL_POSTGRES_DB="$PG_DB"
    export DRILL_REDIS_HOST=127.0.0.1
    export DRILL_REDIS_PORT="$REDIS_HOST_PORT"
    # The application has no POSTGRES_PORT setting; pin the explicit URL to the
    # random host port. Redis does support a host/port pair.
    export ASYNC_DATABASE_URI="postgresql+asyncpg://postgres:${PG_PASSWORD}@127.0.0.1:${PG_HOST_PORT}/${PG_DB}"
    export POSTGRES_SERVER="$DRILL_POSTGRES_SERVER"
    export POSTGRES_USER="$DRILL_POSTGRES_USER"
    export POSTGRES_PASSWORD="$DRILL_POSTGRES_PASSWORD"
    export POSTGRES_DB="$DRILL_POSTGRES_DB"
    export REDIS_HOST="$DRILL_REDIS_HOST"
    export REDIS_PORT="$DRILL_REDIS_PORT"
    # Required application settings for an isolated API process.
    export ENVIRONMENT=local
    export ENABLE_RATE_LIMITING=false
    export SECRET_KEY=restore-drill-not-a-production-secret
    export EMAIL_TEST_USER=drill@example.com
    export FIRST_SUPERUSER_USERNAME=drill
    export FIRST_SUPERUSER_EMAIL=drill@example.com
    export FIRST_SUPERUSER_PASSWORD=drill-not-a-production-password
    export USERS_OPEN_REGISTRATION=false
    (
      cd "$REPO_ROOT"
      exec setsid bash -c "$APP_COMMAND"
    ) >"$WORKDIR/app.log" 2>&1 &
    APP_PID=$!
  fi

  if ! body="$(wait_for_readiness "$app_url")"; then
    if [[ -n "$APP_IMAGE" ]]; then
      "$ENGINE" logs "$APP_CONTAINER" >&2 || true
    fi
    [[ -s "$WORKDIR/app.log" ]] && tail -n 50 "$WORKDIR/app.log" >&2 || true
    die "application did not become ready against the restored database"
  fi
  printf '%s' "$body" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
assert payload.get("status") == "ready", payload
services = payload.get("services", {})
for name in ("postgresql", "redis"):
    assert services.get(name, {}).get("status") == "healthy", (name, services.get(name))
print("readiness: HTTP 200 status=ready postgres=healthy redis=healthy")
' || die "readiness payload is not ready"
fi

log "RESULT: PASS — restore, schema and application readiness verified in isolation"
log "restored revision: $revision"

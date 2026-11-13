#!/usr/bin/env bash
# Snapshot and rehearse the k3s datastore and server token in isolation.
#
# Usage:
#   scripts/k3s-datastore-drill.sh detect [--data-dir DIR]
#   sudo scripts/k3s-datastore-drill.sh snapshot --out DIR --confirm-downtime
#   scripts/k3s-datastore-drill.sh rehearse --snapshot DIR
#
# See docs/DEPLOYMENT.md ("k3s datastore and token drill") for the runbook.

set -euo pipefail

PROGRAM="k3s-datastore-drill"
DATA_DIR="/var/lib/rancher/k3s"
TIMEOUT_SECONDS=240
ENGINE=""
IMAGE=""
PULL=0
KEEP=0
OUT=""
SNAPSHOT=""
CONFIRM_DOWNTIME=0
NO_STOP=0
FORCE=0
K3S_STOPPED=0
WORKDIR=""
NETWORK=""
VOLUME=""
CREATED_CONTAINERS=()

log() { printf '[%s] %s\n' "$PROGRAM" "$*"; }
warn() { printf '[%s] warning: %s\n' "$PROGRAM" "$*" >&2; }
die() {
  printf '[%s] error: %s\n' "$PROGRAM" "$*" >&2
  exit 1
}

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Commands:
  detect     Classify the datastore and report the local k3s identity
  snapshot   Copy the datastore and server token into a snapshot directory
  rehearse   Restore a snapshot into an isolated container and verify it

Common options:
  --data-dir DIR          k3s data directory (default: /var/lib/rancher/k3s)
  --engine podman|docker  Container engine for rehearse (default: auto-detect)
  -h, --help              Show this help

snapshot options:
  --out DIR               Snapshot output directory (required)
  --confirm-downtime      Accept the brief k3s stop for a consistent SQLite copy
  --no-stop               Copy SQLite without stopping k3s (records the caveat)
  --force                 Replace snapshot artifacts already in --out

rehearse options:
  --snapshot DIR          Snapshot directory produced by snapshot (required)
  --image IMAGE           Override the rancher/k3s image derived from the snapshot
  --pull                  Pull the image when it is not present
  --timeout SECONDS       Readiness timeout (default: 240)
  --keep                  Keep containers, volume and network for inspection

rehearse never reads a production kubeconfig and never starts an agent, so
restored workloads cannot run. The server token is never printed.
EOF
}

classify_datastore() {
  local dir="$1"
  if [[ -e "$dir/server/db/state.db" ]]; then
    printf 'sqlite'
  elif [[ -e "$dir/server/db/etcd/member/wal" ]]; then
    printf 'etcd'
  else
    printf 'unknown'
  fi
}

k3s_version_token() {
  command -v k3s >/dev/null 2>&1 || return 0
  k3s --version 2>/dev/null | head -n1 |
    awk '{for (i = 1; i <= NF; i++) if ($i ~ /^v[0-9]/) {print $i; exit}}' || true
}

systemd_unit_text() {
  command -v systemctl >/dev/null 2>&1 || return 0
  systemctl cat k3s 2>/dev/null || true
}

emit_detect_json() {
  local datastore="$1" version node unit token_present
  version="$(k3s_version_token)"
  node="$(hostname 2>/dev/null || uname -n)"
  unit="$(systemd_unit_text)"
  if [[ -e "$DATA_DIR/server/token" ]]; then
    token_present=true
  else
    token_present=false
  fi
  KDD_DATASTORE="$datastore" KDD_VERSION="$version" KDD_NODE="$node" \
  KDD_DATA_DIR="$DATA_DIR" KDD_UNIT="$unit" KDD_TOKEN="$token_present" \
    python3 - <<'PY'
import json
import os
import re

unit = os.environ.get("KDD_UNIT", "")
match = re.search(r"--datastore-endpoint(?:=|\s+)(\S+)", unit)
payload = {
    "datastore": os.environ["KDD_DATASTORE"],
    "k3s_version": os.environ["KDD_VERSION"],
    "node_name": os.environ["KDD_NODE"],
    "token_present": os.environ["KDD_TOKEN"] == "true",
    "data_dir": os.environ["KDD_DATA_DIR"],
    "cluster_init": "--cluster-init" in unit,
    "datastore_endpoint": match.group(1) if match else "",
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

cmd_detect() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown argument: $1 (try --help)" ;;
    esac
  done
  local datastore
  datastore="$(classify_datastore "$DATA_DIR")"
  emit_detect_json "$datastore"
  if [[ "$datastore" == "unknown" ]]; then
    warn "datastore could not be classified under $DATA_DIR"
    exit 1
  fi
}

snapshot_exists() {
  [[ -e "$OUT/snapshot.meta.json" ]] && return 0
  [[ -e "$OUT/sqlite-db.tar.gz" ]] && return 0
  [[ -e "$OUT/etcd-snapshot.db" ]] && return 0
  compgen -G "$OUT/etcd-*.db" >/dev/null && return 0
  compgen -G "$OUT/sqlite-*.tar.gz" >/dev/null && return 0
  return 1
}

cleanup_snapshot() {
  local status=$?
  if [[ "$K3S_STOPPED" -eq 1 ]]; then
    log "restarting k3s"
    systemctl start k3s >/dev/null 2>&1 || warn "failed to start k3s; run: systemctl start k3s"
    K3S_STOPPED=0
  fi
  if [[ -n "$WORKDIR" ]]; then
    rm -rf "$WORKDIR"
  fi
  exit "$status"
}

snapshot_sqlite() {
  local artifact="$OUT/sqlite-db.tar.gz" staging
  if [[ "$NO_STOP" -eq 0 ]]; then
    [[ "$CONFIRM_DOWNTIME" -eq 1 ]] || die "--confirm-downtime is required for a stopped SQLite snapshot"
    log "stopping k3s for a consistent SQLite copy"
    systemctl stop k3s
    K3S_STOPPED=1
    tar -czf "$artifact" -C "$DATA_DIR" server/db
    log "restarting k3s"
    systemctl start k3s
    K3S_STOPPED=0
  else
    warn "--no-stop: the copy is not crash-consistent; verify the restore before relying on it"
    staging="$WORKDIR/sqlite/server/db"
    mkdir -p "$staging"
    if command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "$DATA_DIR/server/db/state.db" ".backup '$staging/state.db'"
    else
      warn "sqlite3 is not installed; falling back to a live file copy"
      cp -a "$DATA_DIR/server/db/." "$staging/"
    fi
    tar -czf "$artifact" -C "$WORKDIR/sqlite" server/db
  fi
  [[ -s "$artifact" ]] || die "SQLite snapshot is empty: $artifact"
}

snapshot_etcd() {
  local stamp="$1" name="drill-$stamp" source
  local -a args=(etcd-snapshot save --name "$name")
  [[ "$DATA_DIR" == "/var/lib/rancher/k3s" ]] || args+=(--data-dir "$DATA_DIR")
  log "saving etcd snapshot $name"
  k3s "${args[@]}" >/dev/null || die "k3s etcd-snapshot save failed"
  source="$DATA_DIR/server/db/snapshots/$name"
  if [[ ! -f "$source" ]]; then
    source="$(find "$DATA_DIR/server/db/snapshots" -maxdepth 1 -name "$name*" -type f 2>/dev/null | head -n1 || true)"
  fi
  [[ -n "$source" && -f "$source" ]] || die "cannot find the etcd snapshot produced by k3s"
  cp -a "$source" "$OUT/etcd-snapshot.db" || die "cannot copy the etcd snapshot"
  [[ -s "$OUT/etcd-snapshot.db" ]] || die "etcd snapshot is empty"
}

copy_token() {
  install -m 0600 "$DATA_DIR/server/token" "$OUT/server-token" || die "cannot copy the server token"
}

marker_uid() {
  k3s kubectl "$@" -o jsonpath='{.metadata.uid}' 2>/dev/null || true
}

read_markers() {
  local default_ns kube_system_ns root_ca
  default_ns="$(marker_uid get namespace default)"
  kube_system_ns="$(marker_uid get namespace kube-system)"
  root_ca="$(marker_uid -n kube-system get configmap kube-root-ca.crt)"
  if [[ -z "$default_ns" || -z "$kube_system_ns" || -z "$root_ca" ]]; then
    warn "kube API unavailable; missing marker UIDs are recorded as null"
  fi
  printf '%s\n%s\n%s\n' "$default_ns" "$kube_system_ns" "$root_ca"
}

write_snapshot_meta() {
  local datastore="$1" created_at="$2" markers="$3"
  KDD_OUT="$OUT" KDD_DATASTORE="$datastore" KDD_CREATED="$created_at" \
  KDD_VERSION="$(k3s_version_token)" KDD_NODE="$(hostname 2>/dev/null || uname -n)" \
  KDD_DATA_DIR="$DATA_DIR" KDD_MARKERS="$markers" \
    python3 - <<'PY'
import hashlib
import json
import os

out = os.environ["KDD_OUT"]
artifact = "sqlite-db.tar.gz" if os.environ["KDD_DATASTORE"] == "sqlite" else "etcd-snapshot.db"
files = []
for name in (artifact, "server-token"):
    digest = hashlib.sha256()
    with open(os.path.join(out, name), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    files.append({"path": name, "sha256": digest.hexdigest()})
markers = (os.environ.get("KDD_MARKERS") or "").splitlines()
while len(markers) < 3:
    markers.append("")
payload = {
    "datastore": os.environ["KDD_DATASTORE"],
    "k3s_version": os.environ["KDD_VERSION"],
    "node_name": os.environ["KDD_NODE"],
    "data_dir": os.environ["KDD_DATA_DIR"],
    "created_at": os.environ["KDD_CREATED"],
    "files": files,
    "token_sha256": next(item["sha256"] for item in files if item["path"] == "server-token"),
    "markers": {
        "default_namespace": markers[0] or None,
        "kube_system_namespace": markers[1] or None,
        "kube_root_ca_configmap": markers[2] or None,
    },
}
with open(os.path.join(out, "snapshot.meta.json"), "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

cmd_snapshot() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out) OUT="${2:-}"; shift 2 ;;
      --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
      --confirm-downtime) CONFIRM_DOWNTIME=1; shift ;;
      --no-stop) NO_STOP=1; shift ;;
      --force) FORCE=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown argument: $1 (try --help)" ;;
    esac
  done
  [[ -n "$OUT" ]] || die "--out is required"
  [[ "$(id -u)" -eq 0 ]] || die "snapshot must run as root (it stops k3s and reads server/token)"
  command -v systemctl >/dev/null 2>&1 || die "systemd is not available; snapshot needs systemctl"
  [[ -d /run/systemd/system ]] || die "systemd is not running; snapshot needs systemctl"
  systemctl cat k3s >/dev/null 2>&1 || die "systemd unit k3s not found"
  local datastore probe
  datastore="$(classify_datastore "$DATA_DIR")"
  [[ "$datastore" != "unknown" ]] || die "cannot classify the datastore under $DATA_DIR"
  [[ -e "$DATA_DIR/server/token" ]] || die "server token not found: $DATA_DIR/server/token"

  mkdir -p "$OUT" || die "cannot create output directory: $OUT"
  probe="$(mktemp "$OUT/.write-test.XXXXXX")" || die "output directory is not writable: $OUT"
  rm -f "$probe"
  if snapshot_exists; then
    [[ "$FORCE" -eq 1 ]] || die "output directory already contains a snapshot: $OUT (use --force)"
    rm -f "$OUT/snapshot.meta.json" "$OUT/sqlite-db.tar.gz" "$OUT/etcd-snapshot.db" "$OUT/server-token"
  fi

  WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/${PROGRAM}.XXXXXX")"
  trap cleanup_snapshot EXIT

  local stamp created_at
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  case "$datastore" in
    sqlite) snapshot_sqlite ;;
    etcd) snapshot_etcd "$stamp" ;;
  esac
  copy_token
  write_snapshot_meta "$datastore" "$created_at" "$(read_markers)"
  log "RESULT: PASS — snapshot=$OUT datastore=$datastore"
}

read_snapshot_meta() {
  python3 - "$SNAPSHOT/snapshot.meta.json" <<'PY'
import json
import sys

meta = json.load(open(sys.argv[1], encoding="utf-8"))
markers = meta.get("markers") or {}
fields = {
    "datastore": meta.get("datastore") or "",
    "k3s_version": meta.get("k3s_version") or "",
    "default_namespace": markers.get("default_namespace") or "",
    "kube_system_namespace": markers.get("kube_system_namespace") or "",
    "kube_root_ca_configmap": markers.get("kube_root_ca_configmap") or "",
}
for key, value in fields.items():
    print(f"{key}\t{value}")
PY
}

verify_snapshot_files() {
  python3 - "$SNAPSHOT" <<'PY'
import hashlib
import json
import os
import sys

root = sys.argv[1]
with open(os.path.join(root, "snapshot.meta.json"), encoding="utf-8") as handle:
    meta = json.load(handle)
for item in meta.get("files", []):
    path = os.path.join(root, item["path"])
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != item["sha256"]:
        sys.exit(f"snapshot file hash mismatch: {item['path']}")
PY
}

cleanup_rehearse() {
  local status=$?
  if [[ -n "$ENGINE" ]]; then
    if [[ "$KEEP" -eq 0 ]]; then
      for container in ${CREATED_CONTAINERS[@]+"${CREATED_CONTAINERS[@]}"}; do
        "$ENGINE" rm -f "$container" >/dev/null 2>&1 || true
      done
      if [[ -n "$VOLUME" ]]; then
        "$ENGINE" volume rm -f "$VOLUME" >/dev/null 2>&1 || true
      fi
      if [[ -n "$NETWORK" ]]; then
        "$ENGINE" network rm "$NETWORK" >/dev/null 2>&1 || true
      fi
      if [[ -n "$WORKDIR" ]]; then
        rm -rf "$WORKDIR"
      fi
    else
      log "kept containers: ${CREATED_CONTAINERS[*]:-none}"
      log "kept volume: ${VOLUME:-none}"
      log "kept network: ${NETWORK:-none}"
      log "workdir: $WORKDIR"
    fi
  fi
  exit "$status"
}

create_network_and_volume() {
  NETWORK="$PROGRAM-net-$$"
  VOLUME="$PROGRAM-data-$$"
  "$ENGINE" network create --internal "$NETWORK" >/dev/null || die "cannot create network: $NETWORK"
  "$ENGINE" volume create "$VOLUME" >/dev/null || die "cannot create volume: $VOLUME"
}

wait_for_prep() {
  local container="$1" deadline=$((SECONDS + 30))
  until "$ENGINE" exec "$container" /bin/sh -c true >/dev/null 2>&1; do
    ((SECONDS < deadline)) || die "prep container did not start"
    sleep 1
  done
}

wait_for_readyz() {
  local container="$1" deadline=$((SECONDS + TIMEOUT_SECONDS))
  until "$ENGINE" exec "$container" k3s kubectl get --raw '/readyz?verbose' >/dev/null 2>&1; do
    if ! "$ENGINE" inspect -f '{{.State.Running}}' "$container" 2>/dev/null | grep -q true; then
      "$ENGINE" logs "$container" >&2 || true
      die "k3s server container exited before becoming ready"
    fi
    ((SECONDS < deadline)) || {
      "$ENGINE" logs "$container" >&2 || true
      die "k3s server did not become ready within ${TIMEOUT_SECONDS}s"
    }
    sleep 2
  done
  log "readyz: OK"
}

assert_restored_datastore() {
  local container="$1" expected="$2"
  case "$expected" in
    sqlite)
      "$ENGINE" exec "$container" test -f /var/lib/rancher/k3s/server/db/state.db ||
        die "restored datastore does not contain state.db"
      ;;
    etcd)
      "$ENGINE" exec "$container" test -d /var/lib/rancher/k3s/server/db/etcd/member/wal ||
        die "restored datastore does not contain etcd/member/wal"
      ;;
  esac
  log "datastore: $expected restored"
}

container_marker() {
  local container="$1"
  shift
  "$ENGINE" exec "$container" k3s kubectl "$@" -o jsonpath='{.metadata.uid}' 2>/dev/null || true
}

assert_marker() {
  local container="$1" label="$2" expected="$3"
  shift 3
  local got
  got="$(container_marker "$container" "$@")"
  if [[ -z "$expected" ]]; then
    warn "$label marker not recorded in snapshot.meta.json; skipping comparison"
    return 0
  fi
  [[ "$got" == "$expected" ]] || die "$label UID mismatch: $got != $expected"
  log "marker $label: OK"
}

assert_logs_clean_file() {
  local log="$1"
  if grep -En '([Ff]ailed to (validate token|decrypt)|[Ii]nvalid token|[Tt]oken (is )?(invalid|mismatch|expired)|[Dd]ecryption failed)' \
    "$log" >"$WORKDIR/log-failures.txt" 2>/dev/null; then
    head -n 5 "$WORKDIR/log-failures.txt" >&2
    die "restored server reported a token or decryption failure"
  fi
}

assert_logs_clean() {
  local container="$1" log="$WORKDIR/server.log"
  "$ENGINE" logs "$container" >"$log" 2>&1 || true
  assert_logs_clean_file "$log"
}

assert_markers() {
  local container="$1"
  assert_marker "$container" "default namespace" "$MARKER_DEFAULT" get namespace default
  assert_marker "$container" "kube-system namespace" "$MARKER_KUBE_SYSTEM" get namespace kube-system
  assert_marker "$container" "kube-root-ca configmap" "$MARKER_ROOT_CA" -n kube-system get configmap kube-root-ca.crt
}

rehearse_sqlite() {
  local prep="$PROGRAM-prep-$$" server="$PROGRAM-server-$$"
  log "extracting the SQLite datastore into the scratch volume"
  "$ENGINE" create --name "$prep" --network "$NETWORK" \
    --mount "type=volume,source=$VOLUME,destination=/var/lib/rancher/k3s" \
    --entrypoint /bin/sh "$IMAGE" -c 'sleep 1800' >/dev/null
  CREATED_CONTAINERS+=("$prep")
  "$ENGINE" start "$prep" >/dev/null
  wait_for_prep "$prep"
  "$ENGINE" exec -i "$prep" tar -xzf - -C /var/lib/rancher/k3s <"$SNAPSHOT/sqlite-db.tar.gz" ||
    die "cannot extract sqlite-db.tar.gz"
  "$ENGINE" rm -f "$prep" >/dev/null 2>&1 || true

  "$ENGINE" create --name "$server" --network "$NETWORK" \
    --mount "type=volume,source=$VOLUME,destination=/var/lib/rancher/k3s" \
    "$IMAGE" server --token-file /drill-token --disable-agent >/dev/null
  CREATED_CONTAINERS+=("$server")
  "$ENGINE" cp "$SNAPSHOT/server-token" "$server:/drill-token"
  "$ENGINE" start "$server" >/dev/null
  wait_for_readyz "$server"
  assert_restored_datastore "$server" sqlite
  assert_markers "$server"
  assert_logs_clean "$server"
}

rehearse_etcd() {
  local reset="$PROGRAM-reset-$$" server="$PROGRAM-server-$$" reset_log exit_code
  reset_log="$WORKDIR/etcd-reset.log"
  log "resetting etcd from the snapshot"
  "$ENGINE" create --name "$reset" --network "$NETWORK" \
    --mount "type=volume,source=$VOLUME,destination=/var/lib/rancher/k3s" \
    "$IMAGE" server --cluster-reset \
    --cluster-reset-restore-path=/snapshots/etcd-snapshot.db \
    --token-file /drill-token --disable-agent >/dev/null
  CREATED_CONTAINERS+=("$reset")
  "$ENGINE" cp "$SNAPSHOT/etcd-snapshot.db" "$reset:/snapshots/etcd-snapshot.db"
  "$ENGINE" cp "$SNAPSHOT/server-token" "$reset:/drill-token"
  "$ENGINE" start -a "$reset" >"$reset_log" 2>&1 || true
  exit_code="$("$ENGINE" inspect -f '{{.State.ExitCode}}' "$reset" 2>/dev/null || echo 1)"
  [[ "$exit_code" == "0" ]] || {
    tail -n 20 "$reset_log" >&2 || true
    die "etcd cluster-reset container exited with code $exit_code"
  }
  grep -qF 'Managed etcd cluster membership has been reset, restart without --cluster-reset flag now.' \
    "$reset_log" || {
    tail -n 20 "$reset_log" >&2 || true
    die "etcd cluster-reset did not report a successful membership reset"
  }
  assert_logs_clean_file "$reset_log"
  "$ENGINE" rm -f "$reset" >/dev/null 2>&1 || true

  "$ENGINE" create --name "$server" --network "$NETWORK" \
    --mount "type=volume,source=$VOLUME,destination=/var/lib/rancher/k3s" \
    "$IMAGE" server --token-file /drill-token --disable-agent >/dev/null
  CREATED_CONTAINERS+=("$server")
  "$ENGINE" cp "$SNAPSHOT/server-token" "$server:/drill-token"
  "$ENGINE" start "$server" >/dev/null
  wait_for_readyz "$server"
  assert_restored_datastore "$server" etcd
  assert_markers "$server"
  assert_logs_clean "$server"
}

cmd_rehearse() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --snapshot) SNAPSHOT="${2:-}"; shift 2 ;;
      --image) IMAGE="${2:-}"; shift 2 ;;
      --engine) ENGINE="${2:-}"; shift 2 ;;
      --timeout) TIMEOUT_SECONDS="${2:-}"; shift 2 ;;
      --pull) PULL=1; shift ;;
      --keep) KEEP=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown argument: $1 (try --help)" ;;
    esac
  done
  [[ -n "$SNAPSHOT" ]] || die "--snapshot is required"
  [[ -d "$SNAPSHOT" ]] || die "snapshot directory not found: $SNAPSHOT"
  [[ -f "$SNAPSHOT/snapshot.meta.json" ]] || die "snapshot.meta.json not found in $SNAPSHOT"
  [[ "$(id -u)" -ne 0 ]] || die "rehearse must not run as root; run it as an unprivileged user"

  if [[ -z "$ENGINE" ]]; then
    if command -v podman >/dev/null 2>&1; then
      ENGINE=podman
    elif command -v docker >/dev/null 2>&1; then
      ENGINE=docker
    else
      die "neither podman nor docker is installed"
    fi
  fi
  [[ "$ENGINE" == "podman" || "$ENGINE" == "docker" ]] || die "unsupported engine: $ENGINE"
  command -v "$ENGINE" >/dev/null 2>&1 || die "container engine not found: $ENGINE"
  command -v python3 >/dev/null 2>&1 || die "python3 is required"

  local meta key value datastore k3s_version
  meta="$(read_snapshot_meta)" || die "snapshot metadata is not valid JSON"
  while IFS=$'\t' read -r key value; do
    case "$key" in
      datastore) datastore="$value" ;;
      k3s_version) k3s_version="$value" ;;
      default_namespace) MARKER_DEFAULT="$value" ;;
      kube_system_namespace) MARKER_KUBE_SYSTEM="$value" ;;
      kube_root_ca_configmap) MARKER_ROOT_CA="$value" ;;
    esac
  done <<<"$meta"
  [[ -n "$datastore" ]] || die "snapshot.meta.json has no datastore"
  case "$datastore" in
    sqlite)
      [[ -f "$SNAPSHOT/sqlite-db.tar.gz" ]] ||
        die "datastore types disagree: meta says sqlite but sqlite-db.tar.gz is missing"
      ;;
    etcd)
      [[ -f "$SNAPSHOT/etcd-snapshot.db" ]] ||
        die "datastore types disagree: meta says etcd but etcd-snapshot.db is missing"
      ;;
    *) die "unsupported datastore in snapshot.meta.json: $datastore" ;;
  esac
  verify_snapshot_files || die "snapshot integrity check failed"

  if [[ -z "$IMAGE" ]]; then
    [[ -n "$k3s_version" ]] || die "cannot derive the k3s image: k3s_version is missing (use --image)"
    IMAGE="rancher/k3s:${k3s_version//+/-}"
  fi
  if ! "$ENGINE" image inspect "$IMAGE" >/dev/null 2>&1; then
    [[ "$PULL" -eq 1 ]] || die "image is not pre-pulled: $IMAGE (pull it, or pass --pull)"
    "$ENGINE" pull "$IMAGE" >/dev/null || die "cannot pull $IMAGE"
  fi

  WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/${PROGRAM}.XXXXXX")"
  trap cleanup_rehearse EXIT
  create_network_and_volume
  case "$datastore" in
    sqlite) rehearse_sqlite ;;
    etcd) rehearse_etcd ;;
  esac
  log "RESULT: PASS — snapshot=$SNAPSHOT datastore=$datastore image=$IMAGE"
}

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi
shift
case "$COMMAND" in
  detect) cmd_detect "$@" ;;
  snapshot) cmd_snapshot "$@" ;;
  rehearse) cmd_rehearse "$@" ;;
  -h|--help|help) usage; exit 0 ;;
  *) die "unknown command: $COMMAND (try --help)" ;;
esac

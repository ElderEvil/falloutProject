#!/usr/bin/env bash
set -euo pipefail

# dev-up.sh — Start full Fallout Shelter dev environment (infra + BE + FE)
# Usage: ./scripts/dev-up.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── Detect container runtime ────────────────────────────────────────────
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  DCR=docker
elif command -v podman &>/dev/null && podman info &>/dev/null 2>&1; then
  DCR=podman
else
  echo "❌ Neither docker nor podman available."
  exit 1
fi

COMPOSE="$(command -v "${DCR}-compose" 2>/dev/null || echo "${DCR} compose")"

echo "🔧 Container runtime: $DCR  |  Compose: $COMPOSE"

# ── Stop prior tmux sessions if running ─────────────────────────────────
for s in fallout-be fallout-fe; do
  tmux has-session -t "$s" 2>/dev/null && tmux send-keys -t "$s" C-c C-d 2>/dev/null || true
  tmux kill-session -t "$s" 2>/dev/null || true
done

# ── Step 1: Infra ───────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  1/4  Starting infrastructure services (PostgreSQL, Redis…)  "
echo "═══════════════════════════════════════════════════════════════"
$COMPOSE -f docker-compose.infra.yml up -d
echo ""

# ── Step 2: Wait for DB ─────────────────────────────────────────────────
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
  if $DCR exec falloutproject_db_1 pg_isready -U postgres -d fallout_db &>/dev/null 2>&1; then
    echo "   PostgreSQL ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "❌ PostgreSQL not ready after 30s."
    exit 1
  fi
  sleep 1
done

# ── Step 3: Alembic migrations ──────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  2/4  Running Alembic migrations                             "
echo "═══════════════════════════════════════════════════════════════"
cd "$ROOT/backend"
uv run alembic upgrade head
echo ""

# ── Step 4: Backend (tmux) ──────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  3/4  Starting Backend (uvicorn) on :8000 (tmux: fallout-be)"
echo "═══════════════════════════════════════════════════════════════"
tmux new-session -d -s fallout-be -c "$ROOT/backend" \
  'uv run uvicorn main:app --host 0.0.0.0 --port 8000'
echo ""

# ── Step 5: Dramatiq workers (if not already running) ───────────────────
if ! pgrep -f 'dramatiq.*app.api.tasks' >/dev/null 2>&1; then
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo "  (background) Starting Dramatiq workers …                    "
  echo "═══════════════════════════════════════════════════════════════"
  cd "$ROOT/backend"
  nohup uv run periodiq app.core.dramatiq app.api.tasks \
    &>/tmp/dramatiq-periodiq.log &
  nohup uv run dramatiq app.api.tasks \
    &>/tmp/dramatiq-worker.log &
fi

# ── Step 6: Frontend (tmux) ─────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  4/4  Starting Frontend (Vite) on :5173 (tmux: fallout-fe)  "
echo "═══════════════════════════════════════════════════════════════"
cd "$ROOT/frontend"
tmux new-session -d -s fallout-fe -c "$ROOT/frontend" \
  'pnpm run dev'
echo ""

# ── Verification ─────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Waiting for services to come up …                           "
echo "═══════════════════════════════════════════════════════════════"

sleep 4

BE_OK=false
FE_OK=false

for i in $(seq 1 15); do
  if [ "$BE_OK" = false ] && curl -sf http://localhost:8000/healthcheck >/dev/null 2>&1; then
    echo "✅ Backend (localhost:8000) — healthy"
    BE_OK=true
  fi
  if [ "$FE_OK" = false ] && curl -sf http://localhost:5173 >/dev/null 2>&1; then
    echo "✅ Frontend (localhost:5173) — serving"
    FE_OK=true
  fi
  $BE_OK && $FE_OK && break
  sleep 1
done

echo ""
if [ "$BE_OK" = true ] && [ "$FE_OK" = true ]; then
  echo "✅ All services are up!"
  echo "   Backend  → http://localhost:8000  (tmux: fallout-be)"
  echo "   Frontend → http://localhost:5173  (tmux: fallout-fe)"
  echo ""
  echo "   To view backend logs:  tmux attach -t fallout-be"
  echo "   To view frontend logs: tmux attach -t fallout-fe"
  echo "   To stop everything:    tmux kill-session -t fallout-be; tmux kill-session -t fallout-fe"
else
  echo "⚠️  Some services may still be starting:"
  $BE_OK || echo "   ❌ Backend (check: tmux attach -t fallout-be)"
  $FE_OK || echo "   ❌ Frontend (check: tmux attach -t fallout-fe)"
fi

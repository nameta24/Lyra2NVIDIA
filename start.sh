#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# EventPulse Venue Intelligence — One-Command Launch
# Usage:  bash start.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${CYAN}[EventPulse]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo -e "${GREEN}"
echo "  ███████╗██╗   ██╗███████╗███╗   ██╗████████╗██████╗ ██╗   ██╗██╗     ███████╗███████╗"
echo "  ██╔════╝██║   ██║██╔════╝████╗  ██║╚══██╔══╝██╔══██╗██║   ██║██║     ██╔════╝██╔════╝"
echo "  █████╗  ██║   ██║█████╗  ██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║     ███████╗█████╗  "
echo "  ██╔══╝  ╚██╗ ██╔╝██╔══╝  ██║╚██╗██║   ██║   ██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝  "
echo "  ███████╗ ╚████╔╝ ███████╗██║ ╚████║   ██║   ██║     ╚██████╔╝███████╗███████║███████╗"
echo "  ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝"
echo "                              VENUE INTELLIGENCE AI"
echo -e "${NC}"

# ── 1. Check prerequisites ────────────────────────────────────────────────────
info "Checking prerequisites…"

command -v python3 &>/dev/null || error "Python 3 is required. Install from https://python.org"
success "Python $(python3 --version | cut -d' ' -f2)"

command -v node &>/dev/null || error "Node.js is required. Install from https://nodejs.org"
success "Node $(node --version)"

command -v npm &>/dev/null || error "npm is required (comes with Node.js)"
success "npm $(npm --version)"

# ── 2. Copy .env if missing ───────────────────────────────────────────────────
if [ ! -f .env ]; then
  warn ".env not found — copying from .env.example"
  cp .env.example .env
  warn "Edit .env and add your MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, HF_TOKEN"
  warn "Then re-run this script."
  echo ""
  warn "Opening .env for editing…"
  sleep 1
  ${EDITOR:-nano} .env || true
fi

# Source env vars
set -o allexport
source .env
set +o allexport

# ── 3. Python venv + backend deps ─────────────────────────────────────────────
info "Setting up Python environment…"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  success "Created .venv"
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt
success "Backend Python dependencies installed"

# ── 4. Generate fallback scene ────────────────────────────────────────────────
if [ ! -f sample_scenes/concession_fallback.ply ]; then
  info "Generating fallback golf course scene…"
  mkdir -p sample_scenes
  python3 scripts/generate_fallback_ply.py
  success "Fallback scene generated → sample_scenes/concession_fallback.ply"
else
  success "Fallback scene already exists"
fi

# ── 5. Frontend deps ──────────────────────────────────────────────────────────
if [ ! -d node_modules ]; then
  info "Installing frontend dependencies…"
  npm install --silent
  success "Frontend dependencies installed"
else
  success "Frontend dependencies already installed"
fi

# ── 6. Modal setup ────────────────────────────────────────────────────────────
if [ -n "$MODAL_TOKEN_ID" ] && [ "$MODAL_TOKEN_ID" != "your_modal_token_id_here" ]; then
  info "Deploying Modal endpoint…"
  if modal deploy modal_app/lyra_endpoint.py 2>&1; then
    success "Modal endpoint deployed ✓"
  else
    warn "Modal deploy failed — app will run in Demo Mode (fallback scene)"
  fi
else
  warn "No Modal credentials found — running in Demo Mode"
  warn "Add MODAL_TOKEN_ID and MODAL_TOKEN_SECRET to .env to enable real Lyra processing"
fi

# ── 7. Start servers ──────────────────────────────────────────────────────────
info "Starting backend (port 8000)…"
# Run uvicorn from the project root so relative paths resolve correctly
(source .venv/bin/activate && PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!
success "Backend PID: $BACKEND_PID"

sleep 2   # Give FastAPI a moment to boot

info "Starting frontend (port 3000)…"
npm run dev &
FRONTEND_PID=$!
success "Frontend PID: $FRONTEND_PID"

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  EventPulse is running!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "  Frontend:  ${CYAN}http://localhost:3000${NC}"
echo -e "  Backend:   ${CYAN}http://localhost:8000${NC}"
echo -e "  API docs:  ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all servers"
echo ""

# Open browser (macOS)
sleep 2
open "http://localhost:3000" 2>/dev/null || true

# Wait for Ctrl+C and clean up
trap "info 'Stopping servers…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; deactivate; exit 0" INT TERM
wait

#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# EventPulse — Public Deployment Script
# Supports: Railway (recommended) · Fly.io · Raw Ubuntu VPS
# ══════════════════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${CYAN}[deploy]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo -e "${GREEN}EventPulse Deployment Script${NC}"
echo ""

# Load env
[ -f .env ] && source .env

DEPLOY_TARGET="${1:-railway}"

case "$DEPLOY_TARGET" in

# ─────────────────────────────────────────────────────────────────────────────
# RAILWAY (easiest — recommended for demos)
# ─────────────────────────────────────────────────────────────────────────────
railway)
  info "Deploying to Railway.app…"

  command -v railway &>/dev/null || {
    info "Installing Railway CLI…"
    npm install -g @railway/cli
  }

  railway whoami &>/dev/null || {
    warn "Not logged in. Opening Railway login…"
    railway login
  }

  # Build frontend
  info "Building frontend…"
  npm install --silent
  npm run build

  # Set env vars on Railway
  info "Setting environment variables…"
  [ -n "$MODAL_TOKEN_ID"     ] && railway variables --set "MODAL_TOKEN_ID=$MODAL_TOKEN_ID"
  [ -n "$MODAL_TOKEN_SECRET" ] && railway variables --set "MODAL_TOKEN_SECRET=$MODAL_TOKEN_SECRET"
  [ -n "$HF_TOKEN"           ] && railway variables --set "HF_TOKEN=$HF_TOKEN"

  # Deploy
  railway up --detach

  DEPLOY_URL=$(railway domain 2>/dev/null || echo "Check Railway dashboard")
  success "Backend deployed!"
  echo -e "  URL: ${CYAN}$DEPLOY_URL${NC}"
  echo ""
  info "Now update frontend/viewer.js — change API_BASE to your Railway URL:"
  echo -e "  ${YELLOW}const API_BASE = 'https://$DEPLOY_URL';${NC}"
  ;;

# ─────────────────────────────────────────────────────────────────────────────
# FLY.IO
# ─────────────────────────────────────────────────────────────────────────────
fly)
  info "Deploying to Fly.io…"

  command -v fly &>/dev/null || {
    info "Installing Fly CLI…"
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
  }

  fly auth whoami &>/dev/null || fly auth login

  # Create app if it doesn't exist
  fly apps list | grep -q "eventpulse-venue" || {
    fly apps create eventpulse-venue --machines
  }

  # Set secrets
  info "Setting secrets…"
  fly secrets set \
    MODAL_TOKEN_ID="$MODAL_TOKEN_ID" \
    MODAL_TOKEN_SECRET="$MODAL_TOKEN_SECRET" \
    HF_TOKEN="$HF_TOKEN" \
    --app eventpulse-venue

  # Deploy
  fly deploy --app eventpulse-venue --remote-only

  DEPLOY_URL="https://eventpulse-venue.fly.dev"
  success "Deployed to $DEPLOY_URL"
  ;;

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DOCKER (test production config locally)
# ─────────────────────────────────────────────────────────────────────────────
docker)
  info "Building and running with Docker Compose…"

  command -v docker &>/dev/null || error "Docker not installed"

  # Build frontend first
  npm install --silent
  npm run build

  docker compose build
  docker compose up -d

  success "Running locally via Docker"
  echo -e "  Frontend: ${CYAN}http://localhost:3000${NC}"
  echo -e "  Backend:  ${CYAN}http://localhost:8000${NC}"
  ;;

# ─────────────────────────────────────────────────────────────────────────────
# RAW VPS (Ubuntu 22.04)
# ─────────────────────────────────────────────────────────────────────────────
vps)
  VPS_HOST="${VPS_HOST:-}"
  VPS_USER="${VPS_USER:-ubuntu}"

  [ -z "$VPS_HOST" ] && error "Set VPS_HOST env var (your server IP)"

  info "Deploying to VPS $VPS_HOST…"

  # Rsync code
  rsync -avz --exclude 'node_modules' --exclude '.venv' --exclude 'dist' \
    ./ "$VPS_USER@$VPS_HOST:/opt/eventpulse/"

  # Remote setup
  ssh "$VPS_USER@$VPS_HOST" bash << 'REMOTE'
    set -e
    cd /opt/eventpulse

    # Install deps if needed
    command -v docker &>/dev/null || {
      curl -fsSL https://get.docker.com | sh
      systemctl enable docker && systemctl start docker
    }

    command -v npm &>/dev/null || {
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
      apt-get install -y nodejs
    }

    # Build frontend
    npm install && npm run build

    # Start stack
    docker compose up -d --build
    echo "Deployed!"
REMOTE

  success "VPS deployment complete"
  echo -e "  App: ${CYAN}http://$VPS_HOST${NC}"
  ;;

*)
  echo "Usage: bash deploy.sh [railway|fly|docker|vps]"
  echo ""
  echo "  railway  — Deploy backend to Railway.app (recommended, free tier)"
  echo "  fly      — Deploy to Fly.io"
  echo "  docker   — Run locally with Docker Compose"
  echo "  vps      — Deploy to raw Ubuntu VPS (set VPS_HOST=your-ip)"
  ;;
esac

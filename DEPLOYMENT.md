# EventPulse — Complete Deployment Guide
### Get a public URL your client can open from anywhere

---

## Overview

You need TWO URLs:
| Service | What it hosts | Cost |
|---------|--------------|------|
| **Fly.io** | FastAPI backend (API + PLY serving) | Free tier ($0) |
| **Vercel** | Vite frontend (the browser app) | Free tier ($0) |

Both have free tiers that are more than enough for this demo.

Total time to deploy: **~20 minutes**

---

## STEP 1 — Deploy Modal GPU Endpoint

This only needs to be done once. It uploads the Lyra worker to Modal's servers.

```bash
# Make sure you have Modal installed and credentials in .env
source .venv/bin/activate
modal deploy modal_app/lyra_endpoint.py
```

You'll see output like:
```
✓ Created objects.
├── 🔨 Created function LyraEndpoint.load_model.
└── 🔨 Created function LyraEndpoint.infer.
✓ App deployed! 🎉
```

**Also set your HuggingFace token as a Modal secret:**
```bash
modal secret create huggingface-token HF_TOKEN=your_hf_token_here
```

---

## STEP 2 — Deploy Backend to Fly.io

### 2a. Install Fly CLI
```bash
curl -L https://fly.io/install.sh | sh
export PATH="$HOME/.fly/bin:$PATH"
```

### 2b. Login
```bash
fly auth login
# Opens browser — sign up at fly.io (free)
```

### 2c. Create and deploy the app
```bash
fly apps create eventpulse-venue
```

Set your secrets (Modal + HuggingFace tokens):
```bash
fly secrets set \
  MODAL_TOKEN_ID="your_modal_token_id" \
  MODAL_TOKEN_SECRET="your_modal_token_secret" \
  HF_TOKEN="your_hf_token" \
  --app eventpulse-venue
```

Deploy:
```bash
fly deploy --app eventpulse-venue
```

Wait ~3 minutes for the first deploy. When done:
```bash
fly status --app eventpulse-venue
```

Your backend URL will be: `https://eventpulse-venue.fly.dev`

Test it:
```bash
curl https://eventpulse-venue.fly.dev/api/health
# Should return: {"status":"ok","modal_available":true,...}
```

---

## STEP 3 — Deploy Frontend to Vercel

### 3a. Install Vercel CLI
```bash
npm install -g vercel
```

### 3b. Update backend URL in vercel.json

Edit `vercel.json` — replace the placeholder with your real Fly.io URL:
```json
"destination": "https://eventpulse-venue.fly.dev/api/$1"
```

### 3c. Build the frontend with your backend URL
```bash
VITE_API_BASE=https://eventpulse-venue.fly.dev npm run build
```

### 3d. Deploy to Vercel
```bash
vercel --prod
```

Follow the prompts:
- Set up and deploy? **Y**
- Which scope? Choose your account
- Link to existing project? **N**
- Project name: `eventpulse-venue`
- Directory: `./` (root)
- Override build settings? **N**

Your frontend URL will be: `https://eventpulse-venue.vercel.app`

---

## STEP 4 — Test the Full Stack

Open your Vercel URL in Chrome. Run through this checklist:

```
□ Page loads — dark cinematic UI appears
□ "Launch Demo Scene" button works — 3D viewer loads in ~3 seconds
□ Drop-in → flyover → walkthrough auto-sequence plays
□ Phase nav buttons (Drop In / Flyover / Walkthrough) all work
□ WASD movement works in walkthrough mode
□ Click on canvas → pointer lock activates → mouse look works
□ ESC releases pointer lock
□ Demo Mode badge visible (yellow "⚠ DEMO MODE")
□ Telemetry HUD shows altitude, mode, phase timer

□ Upload a JPEG photo of a golf course (or any outdoor space)
□ Processing screen appears with progress bar
□ Progress advances every 2 seconds
□ After 3-4 minutes — 3D viewer loads with real Lyra reconstruction
□ No "Demo Mode" badge (real scene)
```

---

## Troubleshooting

### Backend health check fails
```bash
fly logs --app eventpulse-venue
```
Look for Python errors. Common issues:
- Missing secrets → `fly secrets list --app eventpulse-venue`
- Import error → check requirements.txt has all packages

### PLY loads as black screen
- Open browser console (F12 → Console)
- Look for Three.js errors
- Usually means the PLY has no `color` attribute — the viewer handles this with a green fallback colour

### Modal inference times out
- Lyra can take 4-5 min on first cold start (model loading)
- The progress ticker will keep showing progress
- The result will still appear when Modal finishes
- A100 cold start is ~60-90 seconds extra on top of inference

### "Modal not configured" in health check
```bash
fly secrets set MODAL_TOKEN_ID="..." MODAL_TOKEN_SECRET="..." --app eventpulse-venue
fly deploy --app eventpulse-venue
```

### Frontend shows CORS errors
Make sure `vercel.json` rewrite points to your real Fly.io URL, then redeploy:
```bash
VITE_API_BASE=https://eventpulse-venue.fly.dev npm run build
vercel --prod
```

---

## Cost Summary

| Service | Usage | Cost |
|---------|-------|------|
| Fly.io backend | ~0 hrs/month idle (scales to zero) | $0 |
| Vercel frontend | Static hosting | $0 |
| Modal A100 GPU | ~3 min per inference | ~$0.40/run |
| Modal Volume | 15 GB weight storage | ~$0.23/month |

**Total for 10 demo runs: ~$4.20**

---

## Quick Reference URLs

After deployment:
- **Frontend (share this):** `https://eventpulse-venue.vercel.app`
- **Backend API:** `https://eventpulse-venue.fly.dev`
- **API Docs:** `https://eventpulse-venue.fly.dev/docs`
- **Health:** `https://eventpulse-venue.fly.dev/api/health`
- **Demo PLY:** `https://eventpulse-venue.fly.dev/api/demo-scene`

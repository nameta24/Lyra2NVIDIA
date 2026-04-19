# EventPulse Venue Intelligence AI
### 3D Venue Renderer — NVIDIA Lyra 2.0 + Three.js + Modal.com

Drop a venue photo. Explore a 3D world.

---

## What It Does

1. You drag a venue photo onto the browser
2. The image is sent to a Modal A100 GPU running **NVIDIA Lyra 2.0**
3. Lyra reconstructs a **3D point cloud** from the single image (~3–4 min)
4. The browser streams the `.ply` file and renders a cinematic sequence:
   - **Satellite Drop-In** — spiral descent from 450 ft to ground level
   - **Cinematic Flyover** — left-to-right sweep above the venue
   - **First-Person Walkthrough** — WASD + mouse to explore on foot
5. A polished HUD shows live telemetry, branding, and camera controls

---

## Quick Start

### Prerequisites
| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | python.org |
| Node.js | 18+ | nodejs.org |
| npm | 9+ | (bundled with Node) |
| Modal CLI | latest | `pip install modal` |

### Accounts Required
- **Modal.com** — free account at modal.com → Settings → Tokens
- **HuggingFace** — accept Lyra license at huggingface.co/nvidia/Lyra

### Setup

```bash
# 1. Clone / unzip the project
cd eventpulse-venue

# 2. Run everything with one command
bash start.sh
```

`start.sh` will:
- Create a Python virtual environment
- Install all backend + frontend dependencies  
- Generate the fallback demo scene
- Deploy the Modal GPU endpoint
- Start the FastAPI backend (port 8000) and Vite frontend (port 3000)
- Open your browser automatically

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
MODAL_TOKEN_ID=your_token_id
MODAL_TOKEN_SECRET=your_token_secret
HF_TOKEN=your_huggingface_token
```

> **No Modal credentials?** The app still works in **Demo Mode** using a pre-generated synthetic golf course scene.

---

## File Structure

```
eventpulse-venue/
├── modal_app/
│   └── lyra_endpoint.py          # GPU worker — Lyra 2.0 inference on A100
├── backend/
│   ├── main.py                   # FastAPI server
│   └── requirements.txt
├── frontend/
│   ├── index.html                # Single-page app
│   ├── viewer.js                 # Three.js renderer + camera system
│   ├── hud.js                    # HUD overlay module
│   └── style.css                 # Cinematic dark UI
├── sample_scenes/
│   └── concession_fallback.ply   # Pre-generated demo scene (auto-created)
├── scripts/
│   └── generate_fallback_ply.py  # Synthetic golf course generator
├── package.json
├── vite.config.js
├── .env.example
├── start.sh                      # One-command launcher
└── README.md
```

---

## API Reference

### `POST /api/process-venue`
Upload a venue image to start processing.

**Request:** `multipart/form-data`
- `file` — image file (JPEG, PNG, WEBP, max 20 MB)

**Response:**
```json
{ "job_id": "uuid-string" }
```

---

### `GET /api/job/{job_id}`
Poll job status and progress.

**Response:**
```json
{
  "status":      "queued | processing | done",
  "progress":    0-100,
  "demo_mode":   false,
  "error":       null,
  "point_count": 48213,
  "bbox":        [-100, -5, -100, 100, 20, 100]
}
```

Poll every 2 seconds. When `status === "done"`, load the scene.

---

### `GET /api/scene/{job_id}/scene.ply`
Download the generated point cloud.

**Response:** Binary PLY file (`application/octet-stream`)

---

### `GET /api/health`
Health check.

---

## Camera Controls

### Drop-In (automatic)
Spiral descent from 450 ft → ground level over 8 seconds.

### Flyover (automatic)
Cinematic left-to-right sweep 70 ft above terrain over 12 seconds.

### Walkthrough
| Key / Action | Effect |
|---|---|
| `W` | Move forward |
| `S` | Move backward |
| `A` | Strafe left |
| `D` | Strafe right |
| `Mouse` | Look around |
| `Click` | Lock cursor (enables full mouse look) |
| `ESC` | Release cursor |

**Phase nav buttons** at the bottom of the screen let you jump between modes at any time.

---

## Modal GPU Endpoint

The `LyraEndpoint` class in `modal_app/lyra_endpoint.py`:

- Runs on an **NVIDIA A100** (40 GB VRAM)
- Caches model weights in a **Modal Volume** (downloaded once, ~15 GB)
- Returns base64-encoded binary PLY + metadata JSON
- Falls back to a synthetic point cloud if Lyra weights fail to load

### Deploy manually:
```bash
modal deploy modal_app/lyra_endpoint.py
```

### Test locally (requires Modal):
```bash
modal run modal_app/lyra_endpoint.py --image-path path/to/venue.jpg
```

---

## Cost Estimate

| Component | Cost |
|---|---|
| Modal A100 (per inference, ~3 min) | ~$0.30–$0.50 |
| Modal weight download (one-time) | ~$0.05 |
| Modal Volume storage (15 GB/month) | ~$0.23/month |
| **Per demo run** | **~$0.35–$0.55** |

> Weights are cached in the Modal Volume — only downloaded once.

---

## Demo Mode

When Modal is unavailable (no credentials, network error, or inference failure):
- The app automatically loads `sample_scenes/concession_fallback.ply`
- A **⚠ DEMO MODE** badge appears in the HUD
- All camera modes still work normally
- The synthetic scene is a realistic golf course (~50,000 points)

---

## Troubleshooting

**`bash start.sh` fails on Python step**
→ Make sure `python3` points to Python 3.10+: `python3 --version`

**Modal deploy fails**
→ Check your `.env` credentials. Run `modal token set` manually.

**PLY file doesn't load in browser**
→ Open browser console (F12). Check the network tab for `/api/scene/` errors.

**Black screen in viewer**
→ Your GPU may not support WebGL. Try Chrome or Firefox on a modern machine.

**Walkthrough mouse doesn't work**
→ Click on the 3D canvas to request pointer lock, then move the mouse.

---

## Architecture Notes

- **Lyra 2.0 output** is a **Gaussian splat / point cloud**, not a traditional mesh. This means no triangle connectivity — each vertex is an independent 3D point with position and colour. The Three.js `PointsMaterial` renderer is used (not `MeshStandardMaterial`) because there are no faces to shade.
- The PLY loader auto-centres and auto-scales the cloud to fit within a 200-unit cube, making camera positioning deterministic regardless of input scale.
- Job state is stored in-memory (`dict`). For production, replace with Redis or a database.

---

© 2026 EventPulse Inc. — Venue Intelligence Platform

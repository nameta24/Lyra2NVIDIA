"""
EventPulse Venue Intelligence — FastAPI Backend (v2 — production ready)
Endpoints:
  POST /api/process-venue         → accepts image, returns job_id
  GET  /api/job/{job_id}          → returns {status, progress, error}
  GET  /api/scene/{job_id}/scene.ply → serves the generated PLY file
  GET  /api/health                → health-check
  GET  /api/demo-scene            → serves fallback PLY directly (for testing)
"""

import asyncio
import base64
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="EventPulse Venue API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ── Paths — resolve relative to THIS file so they work from any cwd ──────────
HERE         = Path(__file__).parent
ROOT         = HERE.parent
SCENES_DIR   = Path(os.getenv("SCENES_DIR", str(HERE / "scenes")))
FALLBACK_PLY = Path(os.getenv("FALLBACK_PLY", str(ROOT / "sample_scenes" / "concession_fallback.ply")))

SCENES_DIR.mkdir(parents=True, exist_ok=True)

# ── In-memory job store ───────────────────────────────────────────────────────
JOBS: dict[str, dict] = {}


# ── Startup: ensure fallback scene exists ─────────────────────────────────────
@app.on_event("startup")
async def startup():
    if not FALLBACK_PLY.exists():
        gen = ROOT / "scripts" / "generate_fallback_ply.py"
        if gen.exists():
            print("[startup] Generating fallback PLY…")
            subprocess.run(["python3", str(gen)], check=False)
    else:
        print(f"[startup] Fallback scene ready: {FALLBACK_PLY.stat().st_size:,} bytes")
    print(f"[startup] Modal available: {_modal_available()}")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status":          "ok",
        "time":            time.time(),
        "modal_available": _modal_available(),
        "fallback_exists": FALLBACK_PLY.exists(),
        "jobs_active":     len(JOBS),
    }


# ── Demo scene (direct download) ──────────────────────────────────────────────
@app.get("/api/demo-scene")
async def demo_scene():
    if not FALLBACK_PLY.exists():
        raise HTTPException(status_code=404, detail="Fallback scene not yet generated")
    return FileResponse(str(FALLBACK_PLY), media_type="application/octet-stream", filename="demo_scene.ply")


# ── POST /api/process-venue ───────────────────────────────────────────────────
@app.post("/api/process-venue")
async def process_venue(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG, PNG, WEBP)")

    image_bytes = await file.read()
    if len(image_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 25 MB)")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status":      "queued",
        "progress":    0,
        "filename":    file.filename,
        "file_size":   len(image_bytes),
        "error":       None,
        "demo_mode":   False,
        "point_count": None,
        "bbox":        None,
        "created_at":  time.time(),
    }

    background_tasks.add_task(_run_inference, job_id, image_bytes)
    return {"job_id": job_id, "status": "queued"}


# ── GET /api/job/{job_id} ─────────────────────────────────────────────────────
@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── GET /api/scene/{job_id}/scene.ply ─────────────────────────────────────────
@app.get("/api/scene/{job_id}/scene.ply")
async def get_scene(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Scene not ready (status: {job['status']})")

    ply_path = SCENES_DIR / f"{job_id}.ply"
    if ply_path.exists():
        return FileResponse(str(ply_path), media_type="application/octet-stream", filename="scene.ply")
    if FALLBACK_PLY.exists():
        return FileResponse(str(FALLBACK_PLY), media_type="application/octet-stream", filename="scene.ply")
    raise HTTPException(status_code=500, detail="Scene file missing")


# ── Background inference ──────────────────────────────────────────────────────
async def _run_inference(job_id: str, image_bytes: bytes):
    job = JOBS[job_id]
    job["status"] = "processing"
    ticker_task = None

    try:
        ticker_task = asyncio.create_task(_progress_ticker(job_id, 5, 88, 200))

        if _modal_available():
            result = await _call_modal(image_bytes)
        else:
            raise RuntimeError("Modal credentials not configured")

        ticker_task.cancel()

        ply_b64 = result.get("ply_b64")
        if not ply_b64:
            raise RuntimeError(f"Modal returned no PLY. Error: {result.get('error')}")

        ply_bytes = base64.b64decode(ply_b64)
        ply_path  = SCENES_DIR / f"{job_id}.ply"
        ply_path.write_bytes(ply_bytes)

        job.update({
            "status":      "done",
            "progress":    100,
            "point_count": result.get("point_count"),
            "bbox":        result.get("bbox"),
            "demo_mode":   not result.get("used_real_lyra", True),
            "error":       result.get("error"),
        })
        print(f"[job {job_id}] Done — {result.get('point_count')} pts, demo={job['demo_mode']}")

    except Exception as exc:
        if ticker_task:
            ticker_task.cancel()
        print(f"[job {job_id}] FAILED: {exc} — fallback activated")
        _copy_fallback(job_id)
        job.update({"status": "done", "progress": 100, "demo_mode": True, "error": str(exc)})


async def _progress_ticker(job_id: str, start: int, end: int, duration_s: float):
    steps = max(int(duration_s / 2), 1)
    for i in range(steps):
        await asyncio.sleep(2)
        if JOBS.get(job_id, {}).get("status") != "processing":
            break
        pct = int(start + (end - start) * (i + 1) / steps)
        JOBS[job_id]["progress"] = pct


async def _call_modal(image_bytes: bytes) -> dict:
    loop = asyncio.get_event_loop()

    def _sync():
        import sys
        project_root = str(ROOT)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import modal
        fn = modal.Function.lookup("eventpulse-lyra", "LyraEndpoint.infer")
        return fn.remote(image_bytes)

    return await loop.run_in_executor(None, _sync)


def _modal_available() -> bool:
    return bool(os.getenv("MODAL_TOKEN_ID", "").strip() and os.getenv("MODAL_TOKEN_SECRET", "").strip())


def _copy_fallback(job_id: str):
    dst = SCENES_DIR / f"{job_id}.ply"
    if FALLBACK_PLY.exists() and not dst.exists():
        shutil.copy(FALLBACK_PLY, dst)

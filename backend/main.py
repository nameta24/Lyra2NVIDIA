"""
EventPulse Venue Intelligence — FastAPI Backend
Endpoints:
  POST /api/process-venue         → accepts image, returns job_id
  GET  /api/job/{job_id}          → returns {status, progress, error}
  GET  /api/scene/{job_id}/scene.ply → serves the generated PLY file
  GET  /api/health                → health-check
"""

import asyncio
import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="EventPulse Venue API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Storage ──────────────────────────────────────────────────────────────────
JOBS: dict[str, dict] = {}          # in-memory; use Redis/DB for production
SCENES_DIR = Path("scenes")
SCENES_DIR.mkdir(exist_ok=True)

FALLBACK_PLY = Path("../sample_scenes/concession_fallback.ply")


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "time": time.time()}


# ── POST /api/process-venue ──────────────────────────────────────────────────
@app.post("/api/process-venue")
async def process_venue(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    job_id = str(uuid.uuid4())
    image_bytes = await file.read()

    JOBS[job_id] = {
        "status":   "queued",
        "progress": 0,
        "filename": file.filename,
        "error":    None,
        "demo_mode": False,
    }

    background_tasks.add_task(_run_inference, job_id, image_bytes)
    return {"job_id": job_id}


# ── GET /api/job/{job_id} ────────────────────────────────────────────────────
@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── GET /api/scene/{job_id}/scene.ply ────────────────────────────────────────
@app.get("/api/scene/{job_id}/scene.ply")
async def get_scene(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Scene not ready yet")

    ply_path = SCENES_DIR / f"{job_id}.ply"
    if not ply_path.exists():
        # Serve fallback
        if FALLBACK_PLY.exists():
            return FileResponse(str(FALLBACK_PLY), media_type="application/octet-stream")
        raise HTTPException(status_code=500, detail="Scene file missing")

    return FileResponse(str(ply_path), media_type="application/octet-stream")


# ── Background task ──────────────────────────────────────────────────────────
async def _run_inference(job_id: str, image_bytes: bytes):
    """
    Calls the Modal endpoint.  Falls back to the sample scene on any error.
    Progress is faked to give the UI something to show during the ~3-min wait.
    """
    job = JOBS[job_id]
    job["status"] = "processing"

    try:
        # ── Start progress ticker ────────────────────────────────────────────
        ticker_task = asyncio.create_task(_progress_ticker(job_id, 0, 85, 180))

        # ── Call Modal ───────────────────────────────────────────────────────
        use_modal = _modal_available()
        if use_modal:
            result = await _call_modal(image_bytes)
        else:
            raise RuntimeError("Modal not configured — using fallback")

        ticker_task.cancel()

        if result.get("error") and not result.get("ply_b64"):
            raise RuntimeError(result["error"])

        # ── Save PLY ─────────────────────────────────────────────────────────
        ply_bytes = base64.b64decode(result["ply_b64"])
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

    except Exception as exc:
        print(f"[job {job_id}] Error: {exc}. Activating fallback scene.")
        job.update({
            "status":    "done",
            "progress":  100,
            "demo_mode": True,
            "error":     str(exc),
        })
        # Copy fallback PLY into scenes dir so the scene endpoint works
        _copy_fallback(job_id)


async def _progress_ticker(job_id: str, start: int, end: int, duration_s: float):
    """Smoothly advance job progress from start→end over duration_s seconds."""
    steps = int(duration_s / 2)
    for i in range(steps):
        await asyncio.sleep(2)
        if JOBS[job_id]["status"] != "processing":
            break
        pct = int(start + (end - start) * (i + 1) / steps)
        JOBS[job_id]["progress"] = pct


async def _call_modal(image_bytes: bytes) -> dict:
    """Import and call the Modal endpoint asynchronously."""
    loop = asyncio.get_event_loop()

    def _sync_call():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from modal_app.lyra_endpoint import LyraEndpoint
        ep = LyraEndpoint()
        return ep.infer.remote(image_bytes)

    return await loop.run_in_executor(None, _sync_call)


def _modal_available() -> bool:
    token_id     = os.getenv("MODAL_TOKEN_ID", "")
    token_secret = os.getenv("MODAL_TOKEN_SECRET", "")
    return bool(token_id and token_secret)


def _copy_fallback(job_id: str):
    import shutil
    dst = SCENES_DIR / f"{job_id}.ply"
    if FALLBACK_PLY.exists():
        shutil.copy(FALLBACK_PLY, dst)

"""
Modal GPU worker — runs NVIDIA Lyra 2.0 inference on an A100.
Accepts raw image bytes, returns .ply point-cloud bytes + metadata JSON.
"""

import modal
import io
import json
import base64
from pathlib import Path

# ── Modal app setup ──────────────────────────────────────────────────────────
app = modal.App("eventpulse-lyra")

# Persistent volume for model weights (~15 GB, only downloaded once)
model_volume = modal.Volume.from_name("lyra-weights", create_if_missing=True)

LYRA_CACHE = "/model_cache/lyra"
GPU_TYPE   = "A100"          # Change to "A10G" for cheaper dev testing

# Docker image with all deps
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "git", "git-lfs", "libgl1-mesa-glx", "libglib2.0-0",
        "libsm6", "libxext6", "libxrender-dev", "wget", "curl",
    )
    .pip_install(
        "torch==2.2.0",
        "torchvision==0.17.0",
        "transformers==4.40.0",
        "diffusers==0.27.2",
        "huggingface_hub==0.22.2",
        "accelerate==0.29.3",
        "open3d==0.18.0",
        "numpy==1.26.4",
        "Pillow==10.3.0",
        "scipy==1.13.0",
        "einops==0.7.0",
        "omegaconf==2.3.0",
        "trimesh==4.3.2",
        "safetensors==0.4.3",
    )
)


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=600,                     # 10-min hard limit per inference
    volumes={"/model_cache": model_volume},
    secrets=[modal.Secret.from_name("huggingface-token")],
    memory=32768,
)
class LyraEndpoint:
    """Stateful class — model loaded once per container, reused across calls."""

    @modal.enter()
    def load_model(self):
        """Download weights on first cold-start, then load into GPU RAM."""
        import os
        import torch
        from huggingface_hub import snapshot_download

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Lyra] Device: {self.device}")

        hf_token = os.environ.get("HF_TOKEN", "")

        # Download weights once into the persistent Volume
        if not Path(f"{LYRA_CACHE}/config.json").exists():
            print("[Lyra] Downloading model weights from HuggingFace…")
            snapshot_download(
                repo_id="nvidia/Lyra",
                local_dir=LYRA_CACHE,
                token=hf_token,
                ignore_patterns=["*.msgpack", "*.h5"],
            )
            model_volume.commit()
            print("[Lyra] Weights cached to Modal Volume.")
        else:
            print("[Lyra] Loading from cached Volume.")

        # ── Import Lyra ──────────────────────────────────────────────────────
        # Lyra ships as a Python package inside its HF repo.
        import sys
        sys.path.insert(0, LYRA_CACHE)

        try:
            from lyra.pipeline import LyraPipeline           # noqa: F401
            self.pipeline = LyraPipeline.from_pretrained(
                LYRA_CACHE,
                torch_dtype=torch.float16,
            ).to(self.device)
            print("[Lyra] Pipeline loaded ✓")
            self.use_real_lyra = True
        except Exception as e:
            print(f"[Lyra] WARNING — could not load Lyra pipeline: {e}")
            print("[Lyra] Will use synthetic fallback inside worker.")
            self.use_real_lyra = False

    @modal.method()
    def infer(self, image_bytes: bytes, filename: str = "venue.jpg") -> dict:
        """
        Run Lyra 2.0 on the supplied image.

        Returns:
            {
              "ply_b64": "<base64 PLY bytes>",
              "point_count": int,
              "bbox": [xmin,ymin,zmin,xmax,ymax,zmax],
              "used_real_lyra": bool,
              "error": str | None
            }
        """
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = img.resize((512, 512))          # Lyra expects 512×512

            if self.use_real_lyra:
                ply_bytes, meta = self._run_lyra(img)
            else:
                ply_bytes, meta = self._synthetic_fallback(img)

            ply_b64 = base64.b64encode(ply_bytes).decode()
            return {
                "ply_b64": ply_b64,
                "point_count": meta["point_count"],
                "bbox": meta["bbox"],
                "used_real_lyra": self.use_real_lyra,
                "error": None,
            }

        except Exception as exc:
            import traceback
            print("[Lyra] Inference error:", traceback.format_exc())
            # Return synthetic fallback so the demo never hard-crashes
            ply_bytes, meta = self._synthetic_fallback(None)
            return {
                "ply_b64": base64.b64encode(ply_bytes).decode(),
                "point_count": meta["point_count"],
                "bbox": meta["bbox"],
                "used_real_lyra": False,
                "error": str(exc),
            }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _run_lyra(self, pil_image):
        """Call real Lyra pipeline and return (ply_bytes, meta)."""
        import torch, numpy as np, open3d as o3d, tempfile

        with torch.inference_mode():
            result = self.pipeline(
                image=pil_image,
                num_inference_steps=50,
                guidance_scale=7.5,
            )

        # result.point_cloud is an open3d PointCloud or similar
        pc = result.point_cloud
        pts = np.asarray(pc.points, dtype=np.float32)
        cols = (np.asarray(pc.colors) * 255).astype(np.uint8)

        return _to_ply_bytes(pts, cols)

    def _synthetic_fallback(self, _pil_image):
        """Generate a passable 3-D scene without real model weights."""
        import numpy as np
        rng = np.random.default_rng(0)
        N = 40_000

        # terrain
        x = rng.uniform(-40, 40, N).astype(np.float32)
        z = rng.uniform(-80, 80, N).astype(np.float32)
        y = (np.sin(x * 0.08) * 2 + np.cos(z * 0.05) * 1.5).astype(np.float32)
        y += rng.uniform(-0.2, 0.2, N).astype(np.float32)

        r = rng.integers(20, 60, N, dtype=np.uint8)
        g = rng.integers(100, 160, N, dtype=np.uint8)
        b = rng.integers(20, 60, N, dtype=np.uint8)

        pts  = np.c_[x, y, z].astype(np.float32)
        cols = np.c_[r, g, b].astype(np.uint8)
        return _to_ply_bytes(pts, cols)


def _to_ply_bytes(pts, cols):
    """Encode numpy arrays → binary PLY bytes and return (bytes, meta)."""
    import numpy as np, struct, io as _io

    n = len(pts)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    )
    buf = _io.BytesIO()
    buf.write(header.encode("ascii"))
    for i in range(n):
        buf.write(struct.pack(
            "<fffBBB",
            pts[i, 0], pts[i, 1], pts[i, 2],
            cols[i, 0], cols[i, 1], cols[i, 2],
        ))
    raw = buf.getvalue()

    bbox = [
        float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 2].min()),
        float(pts[:, 0].max()), float(pts[:, 1].max()), float(pts[:, 2].max()),
    ]
    meta = {"point_count": n, "bbox": bbox}
    return raw, meta


# ── CLI entrypoint for local testing ────────────────────────────────────────
@app.local_entrypoint()
def main(image_path: str = "test.jpg"):
    ep = LyraEndpoint()
    with open(image_path, "rb") as f:
        data = f.read()
    result = ep.infer.remote(data, image_path)
    print(f"Points: {result['point_count']}")
    print(f"BBox:   {result['bbox']}")
    print(f"Error:  {result['error']}")
    ply = base64.b64decode(result["ply_b64"])
    out = Path("output.ply")
    out.write_bytes(ply)
    print(f"Saved {len(ply):,} bytes → {out}")

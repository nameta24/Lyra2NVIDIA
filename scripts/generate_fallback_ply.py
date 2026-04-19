"""
Generate a synthetic golf course point cloud for fallback/demo mode.
Produces ~50,000 points saved to sample_scenes/concession_fallback.ply
"""

import numpy as np
import struct
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_scenes", "concession_fallback.ply")


def write_ply(path, points, colors):
    """Write binary PLY file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = len(points)
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
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        for (x, y, z), (r, g, b) in zip(points, colors):
            f.write(struct.pack("<fffBBB", x, y, z, r, g, b))
    print(f"Wrote {n} points to {path}")


def generate_golf_course():
    rng = np.random.default_rng(42)
    all_pts = []
    all_cols = []

    def add(pts, cols):
        all_pts.append(pts)
        all_cols.append(cols)

    # ── Fairway (flat green rectangle) ──────────────────────────────────────
    n = 18000
    x = rng.uniform(-30, 30, n)
    z = rng.uniform(-80, 80, n)
    y = rng.uniform(-0.1, 0.1, n) + np.sin(x * 0.1) * 0.3 + np.cos(z * 0.05) * 0.2
    r = rng.integers(30, 60, n, dtype=np.uint8)
    g = rng.integers(120, 160, n, dtype=np.uint8)
    b = rng.integers(20, 50, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Putting green (circular, slightly raised) ────────────────────────────
    n = 4000
    theta = rng.uniform(0, 2 * np.pi, n)
    rad = rng.uniform(0, 8, n) ** 0.5 * 8
    x = rad * np.cos(theta)
    z = rad * np.sin(theta) + 65
    y = 0.15 + rng.uniform(-0.05, 0.05, n)
    r = np.full(n, 40, dtype=np.uint8)
    g = rng.integers(170, 210, n, dtype=np.uint8)
    b = np.full(n, 30, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Sand bunkers ─────────────────────────────────────────────────────────
    for cx, cz in [(-18, 40), (18, 40), (0, -55)]:
        n = 1500
        theta = rng.uniform(0, 2 * np.pi, n)
        rad = rng.uniform(0, 1, n) ** 0.5 * 6
        x = rad * np.cos(theta) + cx
        z = rad * np.sin(theta) + cz
        y = rng.uniform(-0.05, 0.1, n)
        r = rng.integers(210, 240, n, dtype=np.uint8)
        g = rng.integers(190, 220, n, dtype=np.uint8)
        b = rng.integers(140, 170, n, dtype=np.uint8)
        add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Water hazard (pond) ───────────────────────────────────────────────────
    n = 3000
    theta = rng.uniform(0, 2 * np.pi, n)
    rad = rng.uniform(0, 1, n) ** 0.5 * 10
    x = rad * np.cos(theta) * 1.4 - 22
    z = rad * np.sin(theta) * 0.7 - 20
    y = -0.3 + rng.uniform(-0.02, 0.02, n)
    r = rng.integers(10, 30, n, dtype=np.uint8)
    g = rng.integers(80, 120, n, dtype=np.uint8)
    b = rng.integers(160, 200, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Trees (scattered vertical columns) ───────────────────────────────────
    tree_positions = [
        (-35, -60), (35, -60), (-35, 0), (35, 0), (-35, 60), (35, 60),
        (-28, 30), (28, 30), (-28, -30), (28, -30),
        (-20, -70), (20, -70), (-15, 70), (15, 70),
    ]
    for tx, tz in tree_positions:
        n = 400
        h = rng.uniform(0, 6, n)
        theta = rng.uniform(0, 2 * np.pi, n)
        spread = (1 - h / 7) * 2.5
        x = np.cos(theta) * spread * rng.uniform(0.5, 1, n) + tx + rng.uniform(-0.5, 0.5, n)
        z = np.sin(theta) * spread * rng.uniform(0.5, 1, n) + tz + rng.uniform(-0.5, 0.5, n)
        y = h
        g_val = rng.integers(80, 140, n, dtype=np.uint8)
        r_val = rng.integers(10, 50, n, dtype=np.uint8)
        b_val = rng.integers(10, 40, n, dtype=np.uint8)
        add(np.c_[x, y, z], np.c_[r_val, g_val, b_val])

    # ── Tee box ───────────────────────────────────────────────────────────────
    n = 800
    x = rng.uniform(-4, 4, n)
    z = rng.uniform(-4, 4, n) - 72
    y = 0.2 + rng.uniform(-0.02, 0.02, n)
    r = rng.integers(20, 50, n, dtype=np.uint8)
    g = rng.integers(140, 180, n, dtype=np.uint8)
    b = rng.integers(20, 40, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Clubhouse (box structure) ─────────────────────────────────────────────
    n = 2000
    x = rng.uniform(-8, 8, n) + 38
    z = rng.uniform(-6, 6, n) - 75
    y = rng.uniform(0, 5, n)
    # Keep only outer shell
    mask = (np.abs(x - 38) > 7) | (np.abs(z + 75) > 5) | (y > 4.5) | (y < 0.1)
    x, z, y = x[mask], z[mask], y[mask]
    n = len(x)
    r = rng.integers(180, 210, n, dtype=np.uint8)
    g = rng.integers(160, 185, n, dtype=np.uint8)
    b = rng.integers(140, 165, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Path/cart track ───────────────────────────────────────────────────────
    n = 2000
    t = rng.uniform(-80, 80, n)
    x = 22 + np.sin(t * 0.03) * 5 + rng.uniform(-0.5, 0.5, n)
    z = t
    y = 0.05 + rng.uniform(-0.02, 0.02, n)
    r = rng.integers(160, 185, n, dtype=np.uint8)
    g = rng.integers(155, 175, n, dtype=np.uint8)
    b = rng.integers(140, 160, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    # ── Rough (surrounding terrain) ───────────────────────────────────────────
    n = 8000
    x = rng.uniform(-60, 60, n)
    z = rng.uniform(-100, 100, n)
    # Keep only outside fairway band
    mask = (np.abs(x) > 32) | (np.abs(z) > 82)
    x, z = x[mask], z[mask]
    n = len(x)
    y = rng.uniform(-0.2, 0.4, n) + np.sin(x * 0.15) * 0.5
    r = rng.integers(40, 80, n, dtype=np.uint8)
    g = rng.integers(90, 130, n, dtype=np.uint8)
    b = rng.integers(20, 50, n, dtype=np.uint8)
    add(np.c_[x, y, z], np.c_[r, g, b])

    pts = np.vstack(all_pts).astype(np.float32)
    cols = np.vstack(all_cols).astype(np.uint8)
    return pts, cols


if __name__ == "__main__":
    print("Generating synthetic golf course point cloud…")
    pts, cols = generate_golf_course()
    print(f"Total points: {len(pts)}")
    write_ply(OUTPUT_PATH, pts, cols)
    print("Done.")

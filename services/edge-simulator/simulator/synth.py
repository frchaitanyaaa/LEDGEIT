"""Procedural hot-rolled steel surface images with NEU-DET-style defects.

Deterministic per (seed, index). Used so the full pipeline can be demoed without the dataset.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import ndimage

SIZE = 200
DEFECTS = ["scratches", "inclusion", "patches", "pitted_surface", "crazing", "rolled-in_scale"]


@dataclass
class Sample:
    index: int
    truth: str | None  # None = good surface
    jpeg: bytes


def _base(rng: np.random.Generator) -> np.ndarray:
    level = rng.uniform(95, 150)
    img = np.full((SIZE, SIZE), level, dtype=np.float32)
    img += rng.normal(0, 1, (SIZE, 1)).astype(np.float32) * 3  # rolling streaks (row-wise)
    img += ndimage.gaussian_filter(rng.normal(0, 1, (SIZE, SIZE)), 2).astype(np.float32) * 6
    img += rng.normal(0, 2.0, (SIZE, SIZE)).astype(np.float32)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    img += (xx / SIZE - 0.5) * rng.uniform(-8, 8)  # illumination gradient
    return img


def _line(img, rng, x0, y0, x1, y1, width, delta):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    mask = np.zeros_like(img)
    for x, y in zip(xs, ys):
        xi, yi = int(round(x)), int(round(y))
        if 0 <= xi < SIZE and 0 <= yi < SIZE:
            mask[yi, xi] = 1
    mask = ndimage.binary_dilation(mask, iterations=max(1, width // 2)).astype(np.float32)
    img += ndimage.gaussian_filter(mask, 0.8) * delta


def _defect(img: np.ndarray, kind: str, rng: np.random.Generator) -> None:
    if kind == "scratches":
        x0, y0 = rng.uniform(10, 190, 2)
        ang = rng.uniform(0, np.pi)
        ln = rng.uniform(70, 160)
        _line(img, rng, x0, y0, x0 + np.cos(ang) * ln, y0 + np.sin(ang) * ln, 2, rng.choice([-1, 1]) * rng.uniform(35, 60))
    elif kind == "inclusion":
        cx, cy = rng.uniform(30, 170, 2)
        blob = np.zeros_like(img)
        blob[int(cy) - 6:int(cy) + 6, int(cx) - 14:int(cx) + 14] = 1
        img -= ndimage.gaussian_filter(blob, 2.5) * rng.uniform(45, 70)
    elif kind == "patches":
        cx, cy = rng.uniform(50, 150, 2)
        yy, xx = np.mgrid[0:SIZE, 0:SIZE]
        r = rng.uniform(25, 45)
        noise = ndimage.gaussian_filter(rng.normal(0, 1, img.shape), 6) * 25
        mask = (((xx - cx) ** 2 + (yy - cy) ** 2) < (r + noise) ** 2).astype(np.float32)
        img += ndimage.gaussian_filter(mask, 3) * rng.uniform(35, 55)
    elif kind == "pitted_surface":
        for _ in range(int(rng.integers(10, 22))):
            cx, cy = rng.integers(8, 192, 2)
            img[cy - 2:cy + 3, cx - 2:cx + 3] -= rng.uniform(45, 75)
    elif kind == "crazing":
        x, y = rng.uniform(40, 160, 2)
        for _ in range(int(rng.integers(5, 9))):
            ang = rng.uniform(0, 2 * np.pi)
            ln = rng.uniform(15, 35)
            nx, ny = x + np.cos(ang) * ln, y + np.sin(ang) * ln
            _line(img, rng, x, y, nx, ny, 1, -rng.uniform(30, 45))
            x, y = nx, ny
    elif kind == "rolled-in_scale":
        for _ in range(int(rng.integers(4, 8))):
            cx, cy = rng.integers(15, 185, 2)
            flake = np.zeros_like(img)
            flake[cy - 3:cy + 3, cx - 9:cx + 9] = 1
            img -= ndimage.gaussian_filter(flake, 1.5) * rng.uniform(40, 60)


def generate(index: int, seed: int = 7, defect_rate: float = 0.35) -> Sample:
    rng = np.random.default_rng([seed, index])
    img = _base(rng)
    truth = None
    if rng.random() < defect_rate:
        truth = DEFECTS[int(rng.integers(0, len(DEFECTS)))]
        _defect(img, truth, rng)
    buf = io.BytesIO()
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), mode="L").save(buf, format="JPEG", quality=92)
    return Sample(index=index, truth=truth, jpeg=buf.getvalue())

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def load_gray(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    return np.asarray(img.convert("L"), dtype=np.float32)


def jet(x: np.ndarray) -> np.ndarray:
    """Map [0,1] -> RGB uint8 with a jet-like colormap (no matplotlib dependency)."""
    x = np.clip(x, 0, 1)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def heatmap_png(saliency: np.ndarray, base_gray: np.ndarray | None = None, alpha: float = 0.55) -> bytes:
    s = saliency - saliency.min()
    s = s / (s.max() + 1e-6)
    rgb = jet(s).astype(np.float32)
    if base_gray is not None:
        g = np.repeat(base_gray[..., None], 3, axis=-1)
        rgb = alpha * rgb + (1 - alpha) * g
    buf = io.BytesIO()
    Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).save(buf, format="PNG", optimize=True)
    return buf.getvalue()

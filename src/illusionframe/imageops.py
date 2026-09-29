"""Canvas-space image operations. Everything in illusionFrame happens on the canvas: RGB uint8,
the picture's aspect ratio, long side 512, both sides multiples of 64 (sd-turbo's native grid)."""

from __future__ import annotations

import cv2
import numpy as np

LONG_SIDE = 512
MULTIPLE = 64


def canvas_size(
    height: int, width: int, long_side: int = LONG_SIDE, multiple: int = MULTIPLE
) -> tuple[int, int]:
    scale = long_side / max(height, width)

    def snap(v: float) -> int:
        return max(multiple, int(round(v * scale / multiple)) * multiple)

    return snap(height), snap(width)


def to_canvas(image: np.ndarray, size: tuple[int, int] | None = None) -> np.ndarray:
    h, w = size or canvas_size(*image.shape[:2])
    interp = cv2.INTER_AREA if h * w < image.shape[0] * image.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(image, (w, h), interpolation=interp)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """sRGB-encoded values in [0, 1] -> linear light."""
    x = np.asarray(x, dtype=np.float32)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=np.float32), 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055).astype(np.float32)


def feather(mask: np.ndarray, radius: float) -> np.ndarray:
    """Soft alpha inside `mask`: 0 at the boundary rising to 1 at `radius` pixels in."""
    hard = mask.astype(np.float32)
    if radius <= 0:
        return hard
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    return np.clip(dist / radius, 0.0, 1.0).astype(np.float32)


def composite(base: np.ndarray, overlay: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """base * (1 - alpha) + overlay * alpha, alpha in [0, 1] per pixel."""
    a = alpha[..., None] if alpha.ndim == 2 else alpha
    out = base.astype(np.float32) * (1 - a) + overlay.astype(np.float32) * a
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def crossfade(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    t = float(np.clip(t, 0.0, 1.0))
    if t == 0.0:
        return a
    if t == 1.0:
        return b
    return np.clip(np.rint(a.astype(np.float32) * (1 - t) + b.astype(np.float32) * t), 0, 255).astype(
        np.uint8
    )


def reinhard_transfer(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Match source's per-channel Lab mean/std to reference (Reinhard et al., 2001).

    The loop uses it to pull every iteration back toward the painting's palette, which stops the
    colour drift and contrast creep that repeated img2img otherwise accumulates.
    """
    src = cv2.cvtColor(source, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref = cv2.cvtColor(reference, cv2.COLOR_RGB2LAB).astype(np.float32)
    s_mean, s_std = src.reshape(-1, 3).mean(0), src.reshape(-1, 3).std(0) + 1e-6
    r_mean, r_std = ref.reshape(-1, 3).mean(0), ref.reshape(-1, 3).std(0)
    out = (src - s_mean) / s_std * r_std + r_mean
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def frame_stats(image: np.ndarray) -> dict[str, float]:
    """Mean luma and saturation in [0, 1], and the fraction of blown-out pixels (max channel >= 250)."""
    f = image.astype(np.float32) / 255.0
    luma = float((f @ np.array([0.299, 0.587, 0.114], dtype=np.float32)).mean())
    sat = float(cv2.cvtColor(image, cv2.COLOR_RGB2HSV)[..., 1].mean() / 255.0)
    clipped = float((image.max(axis=2) >= 250).mean())
    return {"luma": round(luma, 4), "saturation": round(sat, 4), "clipped": round(clipped, 4)}

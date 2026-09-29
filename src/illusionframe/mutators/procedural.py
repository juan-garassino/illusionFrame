"""Model-free mutation: hue drift, a smooth displacement field, edge glow and a slow zoom.

Instant on a CPU, so it doubles as idle motion between diffusion keyframes. Deterministic for a
given (seed, time).
"""

from __future__ import annotations

import cv2
import numpy as np

from illusionframe.domain.enums import MutatorKind
from illusionframe.mutators.base import MutationParams, Mutator


def _flow_field(h: int, w: int, seed: int, time: float, grid: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """Smooth 2-D displacement in [-1, 1]: coarse random phases, animated by time, upsampled."""
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 2 * np.pi, size=(2, grid, grid))
    freq = rng.uniform(0.2, 0.6, size=(2, grid, grid))
    coarse = np.sin(phase + freq * time).astype(np.float32)
    dx = cv2.resize(coarse[0], (w, h), interpolation=cv2.INTER_CUBIC)
    dy = cv2.resize(coarse[1], (w, h), interpolation=cv2.INTER_CUBIC)
    return dx, dy


class ProceduralMutator(Mutator):
    kind = MutatorKind.PROCEDURAL

    def __init__(
        self, warp_px: float = 18.0, hue_degrees: float = 40.0, glow: float = 0.6, zoom: float = 0.04
    ):
        self.warp_px = warp_px
        self.hue_degrees = hue_degrees
        self.glow = glow
        self.zoom = zoom

    def mutate(self, canvas: np.ndarray, params: MutationParams) -> np.ndarray:
        s = float(np.clip(params.strength, 0, 1))
        if s == 0:
            return canvas.copy()
        h, w = canvas.shape[:2]
        dx, dy = _flow_field(h, w, params.seed, params.time)
        cx, cy = (w - 1) / 2, (h - 1) / 2
        z = 1 - self.zoom * s
        xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        map_x = cx + (xx - cx) * z + dx * self.warp_px * s
        map_y = cy + (yy - cy) * z + dy * self.warp_px * s
        out = cv2.remap(canvas, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV)
        shift = self.hue_degrees * s * np.sin(0.3 * params.time + params.seed) / 2  # OpenCV hue: 0..179
        hsv[..., 0] = ((hsv[..., 0].astype(np.float32) + shift) % 180).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

        edges = cv2.Canny(cv2.cvtColor(out, cv2.COLOR_RGB2GRAY), 60, 140)
        glow = cv2.GaussianBlur(edges.astype(np.float32) / 255.0, (0, 0), 3) * self.glow * s * 3
        tint = np.array([255, 220, 160], dtype=np.float32)
        out = out.astype(np.float32) + glow[..., None] * tint
        return np.clip(out, 0, 255).astype(np.uint8)

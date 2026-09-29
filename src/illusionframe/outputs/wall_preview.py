"""What a projection onto the painting would look like, without a projector.

A matte painting reflects light multiplicatively, so in linear light the camera sees roughly
    cam = exposure * R * (ambient + black + gain * P)
with R the painting's reflectance, P the projected image, and `black` the light a projector
still emits when showing black. Values above 1 clip, which is what a blown-out projection
looks like.
"""

from __future__ import annotations

import numpy as np

from illusionframe import imageops as ops


def project(
    painting: np.ndarray,
    projected: np.ndarray,
    ambient: float = 0.35,
    black: float = 0.03,
    gain: float = 1.0,
    exposure: float = 1.0,
    alpha: np.ndarray | None = None,
) -> np.ndarray:
    """painting/projected: RGB uint8 canvases. `alpha` limits projection to a region (mask-only mode)."""
    reflectance = ops.srgb_to_linear(painting.astype(np.float32) / 255.0)
    light = ops.srgb_to_linear(projected.astype(np.float32) / 255.0)
    if alpha is not None:
        light = light * alpha[..., None]
    cam = exposure * reflectance * (ambient + black + gain * light)
    return np.rint(ops.linear_to_srgb(np.clip(cam, 0, 1)) * 255).astype(np.uint8)

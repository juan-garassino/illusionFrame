"""Turn a MaskSpec into a bool canvas mask. Coordinates in specs are normalized (x, y) in [0, 1]."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from illusionframe.session import MaskSpec

logger = logging.getLogger(__name__)


def _pixels(points: list[list[float]], h: int, w: int) -> np.ndarray:
    return np.array([[x * w, y * h] for x, y in points], dtype=np.float32)


def polygon(spec: MaskSpec, h: int, w: int) -> np.ndarray:
    if len(spec.points) < 3:
        raise ValueError("a polygon mask needs at least 3 points")
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.rint(_pixels(spec.points, h, w)).astype(np.int32)], 1)
    return mask.astype(bool)


def grabcut(spec: MaskSpec, canvas: np.ndarray, iterations: int = 5) -> np.ndarray:
    """OpenCV GrabCut seeded by the box (or the bounding box of the clicked points). No model needed."""
    h, w = canvas.shape[:2]
    if spec.box is not None:
        x0, y0, x1, y1 = spec.box
    elif spec.points:
        xs, ys = zip(*spec.points, strict=True)
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    else:
        raise ValueError("grabcut needs a box or points")
    rect = (int(x0 * w), int(y0 * h), max(1, int((x1 - x0) * w)), max(1, int((y1 - y0) * h)))
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(
        cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR), mask, rect, bgd, fgd, iterations, cv2.GC_INIT_WITH_RECT
    )
    return np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD))


def boundarybrush(spec: MaskSpec, canvas: np.ndarray, segmenter=None) -> np.ndarray:
    """Promptable segmentation with boundaryBrush (sibling project); the segmenter can be injected."""
    try:
        from boundarybrush import Prompt, get_segmenter
    except ImportError as e:
        raise ImportError(
            "the boundarybrush mask needs boundaryBrush: uv pip install -e ../002-boundaryBrush[sam]"
        ) from e
    h, w = canvas.shape[:2]
    seg = segmenter or get_segmenter(spec.backend)
    seg.set_image(canvas)
    points = [(x * w, y * h) for x, y in spec.points]
    labels = spec.labels or [1] * len(points)
    box = None if spec.box is None else (spec.box[0] * w, spec.box[1] * h, spec.box[2] * w, spec.box[3] * h)
    return seg.predict(Prompt(points=points, labels=labels, box=box)).mask


def build_mask(spec: MaskSpec, canvas: np.ndarray, segmenter=None) -> np.ndarray | None:
    h, w = canvas.shape[:2]
    if spec.kind == "full":
        return None
    if spec.kind == "polygon":
        return polygon(spec, h, w)
    if spec.kind == "grabcut":
        return grabcut(spec, canvas)
    if spec.kind == "boundarybrush":
        return boundarybrush(spec, canvas, segmenter)
    raise ValueError(f"unknown mask kind {spec.kind!r}; use full, polygon, grabcut or boundarybrush")

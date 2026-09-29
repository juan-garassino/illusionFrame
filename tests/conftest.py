"""Shared fixtures: a synthetic 'painting' so no test needs a real image file."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def painting() -> np.ndarray:
    """300 x 400 RGB uint8: warm gradient background with a blue disc 'figure' in the middle."""
    h, w = 300, 400
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[..., 0] = (200 * xx / w + 40).astype(np.uint8)
    img[..., 1] = (120 * yy / h + 60).astype(np.uint8)
    img[..., 2] = 50
    disc = (xx - 200) ** 2 + (yy - 150) ** 2 < 70**2
    img[disc] = (40, 70, 200)
    return img

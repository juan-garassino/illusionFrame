from __future__ import annotations

import numpy as np
import pytest

from illusionframe import imageops as ops


@pytest.mark.parametrize(
    "hw,expected", [((300, 400), (384, 512)), ((1000, 500), (512, 256)), ((512, 512), (512, 512))]
)
def test_canvas_size_keeps_aspect_in_multiples_of_64(hw, expected):
    assert ops.canvas_size(*hw) == expected
    h, w = ops.canvas_size(*hw)
    assert h % 64 == 0 and w % 64 == 0 and max(h, w) == 512


def test_to_canvas_resizes(painting):
    c = ops.to_canvas(painting)
    assert c.shape == (384, 512, 3) and c.dtype == np.uint8


def test_srgb_linear_roundtrip():
    x = np.linspace(0, 1, 50, dtype=np.float32)
    assert np.allclose(ops.linear_to_srgb(ops.srgb_to_linear(x)), x, atol=1e-5)
    assert ops.srgb_to_linear(np.float32(0.5)) < 0.25  # sRGB midtone is darker in linear light


def test_feathered_mask_is_exact_away_from_the_edge():
    mask = np.zeros((100, 100), bool)
    mask[30:70, 30:70] = True
    soft = ops.feather(mask, radius=5)
    assert soft.dtype == np.float32
    assert soft[50, 50] == 1.0 and soft[5, 5] == 0.0
    assert 0 < soft[30, 50] < 1  # the edge is soft


def test_feather_zero_radius_is_hard():
    mask = np.zeros((10, 10), bool)
    mask[2:5, 2:5] = True
    assert np.array_equal(ops.feather(mask, 0), mask.astype(np.float32))


def test_composite_and_crossfade_endpoints():
    a = np.zeros((4, 4, 3), np.uint8)
    b = np.full((4, 4, 3), 200, np.uint8)
    alpha = np.zeros((4, 4), np.float32)
    alpha[:, 2:] = 1
    out = ops.composite(a, b, alpha)
    assert (out[:, :2] == 0).all() and (out[:, 2:] == 200).all()
    assert np.array_equal(ops.crossfade(a, b, 0.0), a) and np.array_equal(ops.crossfade(a, b, 1.0), b)
    assert ops.crossfade(a, b, 0.5)[0, 0, 0] == 100


def test_reinhard_transfer_matches_target_statistics(painting):
    import cv2

    rng = np.random.default_rng(0)
    source = rng.integers(0, 255, painting.shape, dtype=np.uint8)
    out = ops.reinhard_transfer(source, painting)

    def stats(img):
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(float)
        return np.concatenate([lab.mean(0), lab.std(0)])

    ref = stats(painting)
    # Lab -> RGB gamut clipping keeps it from being exact; it must close most of the gap
    assert np.linalg.norm(stats(out) - ref) < 0.3 * np.linalg.norm(stats(source) - ref)


def test_frame_stats():
    img = np.zeros((10, 10, 3), np.uint8)
    img[:5] = 255
    stats = ops.frame_stats(img)
    assert stats["clipped"] == pytest.approx(0.5)
    assert 0.4 < stats["luma"] < 0.6 and stats["saturation"] == pytest.approx(0.0)

"""DiffusionMutator against a stub pipeline — no torch model download, but real torch tensors."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from illusionframe.mutators.base import MutationParams  # noqa: E402
from illusionframe.mutators.diffusion import DiffusionMutator  # noqa: E402


class _StubPipe:
    def __init__(self, out_hw=(384, 512)):
        self.text_encoder = object()
        self.encoded, self.calls = [], []
        self.out_hw = out_hw

    def encode_prompt(self, prompt, device, num_images_per_prompt, do_classifier_free_guidance):
        assert not do_classifier_free_guidance
        self.encoded.append(prompt)
        return torch.full((1, 77, 4), float(len(self.encoded))), None

    def __call__(self, **kw):
        self.calls.append(kw)
        h, w = self.out_hw
        return SimpleNamespace(images=[np.full((h, w, 3), 0.5, dtype=np.float32)])


def _mutator(steps=2, **kw):
    m = DiffusionMutator(_StubPipe(**kw), steps=steps)
    m.prepare(["a", "b", "c"])
    return m


def test_prompts_encoded_once_and_text_encoder_released():
    m = _mutator()
    canvas = np.zeros((384, 512, 3), np.uint8)
    for i in range(3):
        m.mutate(canvas, MutationParams(prompt_index=float(i)))
    assert m.pipe.encoded == ["a", "b", "c"] and m.pipe.text_encoder is None


def test_embeddings_interpolate_between_prompts():
    m = _mutator()
    assert float(m.embeds_at(1.0).mean()) == 2.0
    assert float(m.embeds_at(1.25).mean()) == pytest.approx(2.25)
    assert float(m.embeds_at(2.5).mean()) == pytest.approx(2.0)  # wraps from "c" back to "a"


def test_effective_step_floor_and_call_arguments():
    m = _mutator(steps=2)
    m.mutate(np.zeros((384, 512, 3), np.uint8), MutationParams(strength=0.1, seed=7))
    kw = m.pipe.calls[-1]
    assert kw["strength"] == 0.5  # int(2 * 0.1) = 0 steps would be a no-op
    assert kw["guidance_scale"] == 0.0 and kw["num_inference_steps"] == 2
    assert kw["generator"].initial_seed() == 7


def test_output_is_uint8_at_canvas_size():
    m = _mutator(out_hw=(512, 512))
    out = m.mutate(np.zeros((384, 512, 3), np.uint8), MutationParams(strength=0.6))
    assert out.shape == (384, 512, 3) and out.dtype == np.uint8 and out[0, 0, 0] == 128


def test_mutate_before_prepare_raises():
    with pytest.raises(RuntimeError):
        DiffusionMutator(_StubPipe()).mutate(np.zeros((8, 8, 3), np.uint8), MutationParams())
    with pytest.raises(ValueError):
        DiffusionMutator(_StubPipe(), steps=0)

from __future__ import annotations

import time

import numpy as np
import pytest

from illusionframe.domain.enums import MutatorKind
from illusionframe.imageops import to_canvas
from illusionframe.mutators.base import MutationParams
from illusionframe.mutators.mock import MockMutator
from illusionframe.mutators.procedural import ProceduralMutator
from illusionframe.mutators.registry import get_mutator


def test_procedural_is_deterministic_and_seed_sensitive(painting):
    m, c = ProceduralMutator(), to_canvas(painting)
    a = m.mutate(c, MutationParams(strength=0.7, seed=1, time=2.0))
    b = m.mutate(c, MutationParams(strength=0.7, seed=1, time=2.0))
    other = m.mutate(c, MutationParams(strength=0.7, seed=2, time=2.0))
    later = m.mutate(c, MutationParams(strength=0.7, seed=1, time=5.0))
    assert a.shape == c.shape and a.dtype == np.uint8
    assert np.array_equal(a, b) and not np.array_equal(a, other) and not np.array_equal(a, later)


def test_procedural_strength_zero_is_identity(painting):
    c = to_canvas(painting)
    assert np.array_equal(ProceduralMutator().mutate(c, MutationParams(strength=0)), c)


def test_procedural_is_fast_enough_for_idle_motion(painting):
    m, c = ProceduralMutator(), to_canvas(painting)
    m.mutate(c, MutationParams())
    t0 = time.perf_counter()
    for i in range(5):
        m.mutate(c, MutationParams(time=float(i)))
    assert (time.perf_counter() - t0) / 5 < 0.2


def test_mock_records_calls_and_blends(painting):
    m, c = MockMutator(), to_canvas(painting)
    out = m.mutate(c, MutationParams(strength=1.0))
    assert np.array_equal(out, 255 - c) and len(m.calls) == 1


@pytest.mark.parametrize("kind", ["procedural", MutatorKind.MOCK])
def test_registry(kind):
    assert get_mutator(kind).kind == MutatorKind(kind)

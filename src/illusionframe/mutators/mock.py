from __future__ import annotations

import numpy as np

from illusionframe.domain.enums import MutatorKind
from illusionframe.mutators.base import MutationParams, Mutator


class MockMutator(Mutator):
    """Deterministic stand-in for tests: blends toward the colour negative by `strength`."""

    kind = MutatorKind.MOCK

    def __init__(self):
        self.calls: list[MutationParams] = []

    def mutate(self, canvas: np.ndarray, params: MutationParams) -> np.ndarray:
        self.calls.append(params)
        s = float(np.clip(params.strength, 0, 1))
        out = canvas.astype(np.float32) * (1 - s) + (255 - canvas.astype(np.float32)) * s
        return np.clip(np.rint(out), 0, 255).astype(np.uint8)

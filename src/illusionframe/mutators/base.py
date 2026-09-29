"""A mutator turns a canvas into a mutated canvas of the same size."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from illusionframe.domain.enums import MutatorKind


@dataclass(frozen=True)
class MutationParams:
    strength: float = 0.5  # 0 = leave as is, 1 = mutate as much as the mutator can
    seed: int = 0
    time: float = 0.0  # seconds of (virtual) time, drives procedural motion
    prompt_index: float = 0.0  # position in the prompt schedule (fractional = interpolated)


class Mutator(ABC):
    kind: MutatorKind

    @abstractmethod
    def mutate(self, canvas: np.ndarray, params: MutationParams) -> np.ndarray:
        """canvas: RGB uint8 H x W x 3 -> same shape and dtype."""

    def prepare(self, prompts: list[str]) -> None:  # noqa: B027 - optional hook
        """Called once before a run with the prompt schedule (diffusion encodes them here)."""

    def describe(self) -> dict[str, Any]:
        return {"kind": self.kind.value}

"""What each iteration asks for: which prompt (interpolated), how strong, which seed."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    index: int
    prompt_position: float  # 1.5 = halfway from prompt 1 to prompt 2 (embeddings are lerped)
    strength: float
    seed: int


@dataclass(frozen=True)
class Schedule:
    prompts: tuple[str, ...] = field(default_factory=lambda: ("a dreamlike oil painting, vivid colours",))
    iterations_per_prompt: int = 8
    strength_min: float = 0.3
    strength_max: float = 0.65
    breathe_period: int = 12  # iterations per strength cycle: restore, mutate, restore...
    seed: int = 0
    seed_hold: int = 4  # same seed for this many iterations keeps structure coherent

    def __post_init__(self):
        if not self.prompts:
            raise ValueError("the schedule needs at least one prompt")
        if not 0 <= self.strength_min <= self.strength_max <= 1:
            raise ValueError("need 0 <= strength_min <= strength_max <= 1")
        if self.iterations_per_prompt < 1 or self.breathe_period < 1 or self.seed_hold < 1:
            raise ValueError("iterations_per_prompt, breathe_period and seed_hold must be >= 1")

    def at(self, i: int) -> Step:
        position = (i / self.iterations_per_prompt) % len(self.prompts)
        wave = 0.5 - 0.5 * math.cos(2 * math.pi * i / self.breathe_period)
        strength = self.strength_min + (self.strength_max - self.strength_min) * wave
        return Step(
            index=i, prompt_position=position, strength=strength, seed=self.seed + i // self.seed_hold
        )

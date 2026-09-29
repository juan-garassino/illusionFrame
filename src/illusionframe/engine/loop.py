"""The feedback loop as a pure state machine (no threads, no IO, injected clock).

    input_i   = reinhard(lerp(reference, output_{i-1}, feedback), reference)   # drift guard
    mutated_i = mutator(input_i, schedule.at(i))
    output_i  = composite(reference, mutated_i, feathered mask)                # mask anchors the rest
    display   = crossfade(previous display, output_i) over fade_seconds

If an output blows out (too many clipped pixels), feedback is reduced so the loop cannot run away.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from illusionframe import imageops as ops
from illusionframe.domain.enums import MaskMode
from illusionframe.engine.schedule import Schedule, Step
from illusionframe.mutators.base import MutationParams, Mutator


@dataclass
class LoopConfig:
    fade_seconds: float = 2.0
    feedback: float = 0.5  # 0 = always mutate the original, 0.8 = mostly mutate the last output
    max_clipped: float = 0.05  # blown-out fraction that triggers the drift guard
    feedback_decay: float = 0.7
    reset_every: int = 0  # 0 = never go back to the reference
    mask_mode: MaskMode = MaskMode.ALL
    feather: float = 12.0
    idle_strength: float = 0.12  # procedural motion on the displayed frame between results

    def __post_init__(self):
        if not 0 <= self.feedback <= 0.8:
            raise ValueError("feedback must be in [0, 0.8]; higher runs away")
        self.mask_mode = MaskMode(self.mask_mode)


class LoopState:
    def __init__(
        self,
        reference: np.ndarray,
        mask: np.ndarray | None = None,
        config: LoopConfig | None = None,
        schedule: Schedule | None = None,
        idle: Mutator | None = None,
    ):
        self.cfg = config or LoopConfig()
        self.schedule = schedule or Schedule()
        self.reference = reference
        self.alpha = self._alpha(mask, reference.shape[:2])
        self.idle = idle
        self.feedback = self.cfg.feedback
        self.iteration = 0
        self.last_output = reference
        self._fade_from = reference
        self._fade_to = reference
        self._fade_start = 0.0

    def _alpha(self, mask: np.ndarray | None, hw: tuple[int, int]) -> np.ndarray:
        mode = self.cfg.mask_mode
        if mask is None or mode is MaskMode.ALL:
            return np.ones(hw, np.float32)
        region = mask if mode is MaskMode.INSIDE else ~mask
        return ops.feather(region, self.cfg.feather)

    def next_input(self) -> tuple[np.ndarray, Step]:
        step = self.schedule.at(self.iteration)
        reset = self.cfg.reset_every and self.iteration and self.iteration % self.cfg.reset_every == 0
        if reset:
            return self.reference, step
        x = ops.crossfade(self.reference, self.last_output, self.feedback)
        return ops.reinhard_transfer(x, self.reference), step

    def submit(self, mutated: np.ndarray, now: float, step: Step | None = None) -> dict:
        output = ops.composite(self.reference, mutated, self.alpha)
        self._fade_from = self._blend(now)  # a result arriving mid-fade starts from what is on screen
        self._fade_to = output
        self._fade_start = now
        self.last_output = output
        stats = ops.frame_stats(output)
        if stats["clipped"] > self.cfg.max_clipped:
            self.feedback *= self.cfg.feedback_decay
        record = {"iteration": self.iteration, "feedback": round(self.feedback, 4), **stats}
        if step is not None:
            record.update(
                strength=round(step.strength, 4), seed=step.seed, prompt_position=step.prompt_position
            )
        self.iteration += 1
        return record

    def _blend(self, now: float) -> np.ndarray:
        t = (now - self._fade_start) / self.cfg.fade_seconds if self.cfg.fade_seconds > 0 else 1.0
        return ops.crossfade(self._fade_from, self._fade_to, t)

    def fading(self, now: float) -> bool:
        return now - self._fade_start < self.cfg.fade_seconds

    def tick(self, now: float) -> np.ndarray:
        """The frame to show at time `now` (seconds): crossfade plus optional idle motion."""
        frame = self._blend(now)
        if self.idle is not None and self.cfg.idle_strength > 0:
            moved = self.idle.mutate(frame, MutationParams(strength=self.cfg.idle_strength, time=now))
            frame = ops.composite(frame, moved, self.alpha)
        return frame

from __future__ import annotations

from enum import StrEnum


class MutatorKind(StrEnum):
    PROCEDURAL = "procedural"
    DIFFUSION = "diffusion"
    MOCK = "mock"


class MaskMode(StrEnum):
    INSIDE = "inside"  # mutate only the masked region
    OUTSIDE = "outside"  # mutate everything but the masked region
    ALL = "all"


class ViewMode(StrEnum):
    CANVAS = "canvas"  # the mutated picture itself
    WALL = "wall"  # simulated projection onto the original painting

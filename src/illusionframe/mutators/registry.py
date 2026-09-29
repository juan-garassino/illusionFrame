from __future__ import annotations

from illusionframe.domain.enums import MutatorKind
from illusionframe.mutators.base import Mutator


def get_mutator(kind: MutatorKind | str, **kwargs) -> Mutator:
    kind = MutatorKind(kind)
    if kind is MutatorKind.PROCEDURAL:
        from illusionframe.mutators.procedural import ProceduralMutator

        return ProceduralMutator(**kwargs)
    if kind is MutatorKind.MOCK:
        from illusionframe.mutators.mock import MockMutator

        return MockMutator()
    from illusionframe.mutators.diffusion import DiffusionMutator

    return DiffusionMutator.from_pretrained(**kwargs)

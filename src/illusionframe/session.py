"""session.toml: everything that defines a run, so it can be reproduced (it is copied into the run)."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from illusionframe.domain.enums import MutatorKind
from illusionframe.engine.loop import LoopConfig
from illusionframe.engine.schedule import Schedule


@dataclass
class MaskSpec:
    kind: str = "full"  # full | polygon | grabcut | boundarybrush
    points: list[list[float]] = field(default_factory=list)  # normalized (x, y) in [0, 1] of the canvas
    labels: list[int] = field(default_factory=list)  # boundarybrush clicks: 1 include, 0 exclude
    box: list[float] | None = None  # normalized (x0, y0, x1, y1)
    backend: str = "slimsam"  # boundarybrush backend


@dataclass
class MutatorSpec:
    kind: MutatorKind = MutatorKind.PROCEDURAL
    steps: int = 2  # diffusion: denoising steps; effective steps = int(steps * strength) >= 1
    tiny_vae: bool = True  # diffusion: TAESD encode/decode (much faster on CPU)

    def __post_init__(self):
        self.kind = MutatorKind(self.kind)


@dataclass
class Session:
    schedule: Schedule = field(default_factory=Schedule)
    loop: LoopConfig = field(default_factory=LoopConfig)
    mask: MaskSpec = field(default_factory=MaskSpec)
    mutator: MutatorSpec = field(default_factory=MutatorSpec)

    @classmethod
    def from_dict(cls, d: dict) -> Session:
        sections = {"schedule": Schedule, "loop": LoopConfig, "mask": MaskSpec, "mutator": MutatorSpec}
        unknown = set(d) - set(sections)
        if unknown:
            raise ValueError(f"unknown session sections: {sorted(unknown)}")
        kwargs = {}
        for key, section_cls in sections.items():
            values = dict(d.get(key, {}))
            bad = set(values) - {f.name for f in fields(section_cls)}
            if bad:
                raise ValueError(f"unknown keys in [{key}]: {sorted(bad)}")
            if key == "schedule" and "prompts" in values:
                values["prompts"] = tuple(values["prompts"])
            kwargs[key] = section_cls(**values)
        return cls(**kwargs)

    @classmethod
    def load(cls, path: str | Path | None) -> Session:
        if path is None:
            return cls()
        with Path(path).open("rb") as f:
            return cls.from_dict(tomllib.load(f))

    def to_toml(self) -> str:
        lines = []
        for name in ("schedule", "loop", "mask", "mutator"):
            lines.append(f"[{name}]")
            for key, value in asdict(getattr(self, name)).items():
                if value is None:
                    continue
                lines.append(f"{key} = {_toml_value(value)}")
            lines.append("")
        return "\n".join(lines)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):  # includes StrEnum
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return repr(v)

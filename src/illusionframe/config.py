"""Runtime settings from ILLUSIONFRAME_* environment variables (a dataclass; no pydantic)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"ILLUSIONFRAME_{name}", default)


def _str(name: str, default: str):
    return field(default_factory=lambda: _env(name, default))


@dataclass(frozen=True)
class Settings:
    runs_dir: Path = field(default_factory=lambda: Path(_env("RUNS_DIR", "runs")))  # ILLUSIONFRAME_RUNS_DIR
    model_id: str = _str("MODEL_ID", "stabilityai/sd-turbo")  # ILLUSIONFRAME_MODEL_ID
    tiny_vae_id: str = _str("TINY_VAE_ID", "madebyollin/taesd")  # ILLUSIONFRAME_TINY_VAE_ID
    torch_threads: int = field(default_factory=lambda: int(_env("TORCH_THREADS", "3")))  # 1 core left for UI


def get_settings() -> Settings:
    return Settings()

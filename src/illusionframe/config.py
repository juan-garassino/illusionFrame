"""Runtime settings from ILLUSIONFRAME_* environment variables (a dataclass; no pydantic)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"ILLUSIONFRAME_{name}", default)


def _positive_int(name: str, default: str) -> int:
    raw = _env(name, default)
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"ILLUSIONFRAME_{name} must be a positive integer, got {raw!r}") from None
    if value < 1:
        raise ValueError(f"ILLUSIONFRAME_{name} must be a positive integer, got {raw!r}")
    return value


# Hugging Face repo id: "namespace/name", no path separators beyond the one slash, no "..".
_REPO_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")


def _repo_id(name: str, default: str) -> str:
    raw = _env(name, default)
    if not _REPO_ID.fullmatch(raw) or ".." in raw:
        raise ValueError(f"ILLUSIONFRAME_{name} must be a Hugging Face repo id 'namespace/name', got {raw!r}")
    return raw


def _nonempty_path(name: str, default: str) -> Path:
    raw = _env(name, default)
    if not raw.strip():
        raise ValueError(f"ILLUSIONFRAME_{name} must not be empty")
    return Path(raw)


def _model(name: str, default: str):
    return field(default_factory=lambda: _repo_id(name, default))


@dataclass(frozen=True)
class Settings:
    # ILLUSIONFRAME_RUNS_DIR
    runs_dir: Path = field(default_factory=lambda: _nonempty_path("RUNS_DIR", "runs"))
    model_id: str = _model("MODEL_ID", "stabilityai/sd-turbo")  # ILLUSIONFRAME_MODEL_ID
    tiny_vae_id: str = _model("TINY_VAE_ID", "madebyollin/taesd")  # ILLUSIONFRAME_TINY_VAE_ID
    # ILLUSIONFRAME_TORCH_THREADS; default 3 leaves 1 core for the UI
    torch_threads: int = field(default_factory=lambda: _positive_int("TORCH_THREADS", "3"))


def get_settings() -> Settings:
    return Settings()

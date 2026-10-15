from __future__ import annotations

from pathlib import Path

import pytest

from illusionframe.config import Settings, get_settings


def test_defaults(monkeypatch):
    for name in ("RUNS_DIR", "MODEL_ID", "TINY_VAE_ID", "TORCH_THREADS"):
        monkeypatch.delenv(f"ILLUSIONFRAME_{name}", raising=False)
    s = get_settings()
    assert s.runs_dir == Path("runs")
    assert s.model_id == "stabilityai/sd-turbo"
    assert s.tiny_vae_id == "madebyollin/taesd"
    assert s.torch_threads == 3


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("ILLUSIONFRAME_RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("ILLUSIONFRAME_MODEL_ID", "org/model")
    monkeypatch.setenv("ILLUSIONFRAME_TORCH_THREADS", "1")
    s = Settings()
    assert s.runs_dir == tmp_path
    assert s.model_id == "org/model"
    assert s.torch_threads == 1


@pytest.mark.parametrize("value", ["0", "-2", "three", ""])
def test_invalid_torch_threads_rejected_with_named_variable(monkeypatch, value):
    monkeypatch.setenv("ILLUSIONFRAME_TORCH_THREADS", value)
    with pytest.raises(ValueError, match="ILLUSIONFRAME_TORCH_THREADS"):
        Settings()

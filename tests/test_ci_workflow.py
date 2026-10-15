"""Guard against the CI smoke-import step referencing modules that do not exist."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


@pytest.mark.xfail(
    strict=True,
    reason="G-004: ci.yml imports illusionframe.imageops, which does not exist; "
    "fix needs a push with `workflow` scope (see GUARDIAN.md)",
)
def test_ci_smoke_import_targets_exist():
    text = CI.read_text()
    modules = set(re.findall(r"\billusionframe(?:\.[a-z_]+)+", text))
    missing = sorted(m for m in modules if importlib.util.find_spec(m) is None)
    assert not missing, f"ci.yml imports modules that do not exist: {missing}"

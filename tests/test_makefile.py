"""Guard against Makefile targets calling CLI verbs that are not registered."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from illusionframe.cli import build_parser

MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"


def _registered_verbs() -> set[str]:
    sub = next(a for a in build_parser()._actions if a.dest == "cmd")
    return set(sub.choices)


@pytest.mark.xfail(
    strict=True,
    reason="G-009: `make demo` / `make fetch-models` call verbs (evolve, fetch-models) not implemented yet",
)
def test_makefile_cli_verbs_are_registered():
    used = set(re.findall(r"uv run illusionframe\s+([a-z][a-z-]*)", MAKEFILE.read_text()))
    missing = sorted(used - _registered_verbs())
    assert not missing, f"Makefile calls unregistered CLI verbs: {missing}"

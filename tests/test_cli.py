from __future__ import annotations

import pytest

from illusionframe import __version__
from illusionframe.cli import build_parser, main


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_missing_subcommand_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_parser_prog_name():
    assert build_parser().prog == "illusionframe"

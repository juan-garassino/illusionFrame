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


def test_subcommand_without_handler_is_usage_error_not_crash(monkeypatch, capsys):
    """G-009: a verb registered without set_defaults(func=...) must not raise AttributeError."""
    import illusionframe.cli as cli

    real = cli.build_parser

    def parser_with_bare_verb():
        parser = real()
        sub = next(a for a in parser._actions if a.dest == "cmd")
        sub.add_parser("bare")
        return parser

    monkeypatch.setattr(cli, "build_parser", parser_with_bare_verb)
    assert cli.main(["bare"]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_every_registered_verb_has_a_handler():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    for name, verb in sub.choices.items():
        assert verb.get_default("func") is not None, f"verb {name!r} has no func"


def test_python_dash_m_entrypoint_runs():
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "illusionframe", "--version"], capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
    assert __version__ in out.stdout

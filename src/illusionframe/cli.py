"""illusionframe — a picture that mutates itself. Subcommands import their heavy modules lazily."""

from __future__ import annotations

import argparse
import logging
import sys

from illusionframe import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="illusionframe", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_subparsers(dest="cmd", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    func = getattr(args, "func", None)
    if func is None:  # verb registered without set_defaults(func=...)
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: subcommand {args.cmd!r} is not implemented yet", file=sys.stderr)
        return 2
    return func(args)

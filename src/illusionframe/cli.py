"""illusionframe — a picture that mutates itself. Subcommands import their heavy modules lazily."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from illusionframe import __version__

logger = logging.getLogger(__name__)


def _load_picture(path: str):
    import cv2

    bgr = cv2.imread(path)
    if bgr is None:
        raise SystemExit(f"cannot read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _prepare(args):
    from illusionframe.imageops import to_canvas
    from illusionframe.masks.build import build_mask
    from illusionframe.session import Session

    session = Session.load(args.session)
    if args.mutator:
        session.mutator.kind = args.mutator
        session.mutator.__post_init__()
    canvas = to_canvas(_load_picture(args.image))
    return session, canvas, build_mask(session.mask, canvas)


def _mutator(session, settings):
    from illusionframe.domain.enums import MutatorKind
    from illusionframe.mutators.registry import get_mutator

    if session.mutator.kind is MutatorKind.DIFFUSION:
        return get_mutator(
            MutatorKind.DIFFUSION,
            model_id=settings.model_id,
            tiny_vae_id=settings.tiny_vae_id if session.mutator.tiny_vae else None,
            steps=session.mutator.steps,
            threads=settings.torch_threads,
        )
    return get_mutator(session.mutator.kind)


def _cmd_evolve(args: argparse.Namespace) -> int:
    import numpy as np

    from illusionframe.config import get_settings
    from illusionframe.engine.loop import LoopState
    from illusionframe.engine.runner import render_offline
    from illusionframe.mutators.procedural import ProceduralMutator
    from illusionframe.outputs.recorder import Recorder
    from illusionframe.outputs.wall_preview import project

    settings = get_settings()
    session, canvas, mask = _prepare(args)
    run = Path(args.out) / Path(args.image).stem / time.strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    (run / "session.toml").write_text(session.to_toml())
    idle = ProceduralMutator() if session.loop.idle_strength > 0 else None
    state = LoopState(canvas, mask, session.loop, session.schedule, idle=idle)
    recorder = Recorder(run, fps=args.fps)
    sink = recorder
    if args.view == "wall":

        class _Wall:
            def write(self, frame: np.ndarray) -> None:
                recorder.write(project(canvas, frame))

            def keyframe(self, frame: np.ndarray, record: dict) -> None:
                recorder.keyframe(project(canvas, frame), record)

        sink = _Wall()
    try:
        render_offline(state, _mutator(session, settings), args.iterations, fps=args.fps, sinks=[sink])
    finally:
        recorder.close()
    print(run)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="illusionframe", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("evolve", help="render the mutation loop offline to mp4 + gif (deterministic)")
    p.add_argument("image")
    p.add_argument("--session", default=None, help="session.toml (default settings if omitted)")
    p.add_argument("--mutator", choices=["procedural", "diffusion", "mock"], default=None)
    p.add_argument("--iterations", type=int, default=30)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument(
        "--view",
        choices=["canvas", "wall"],
        default="canvas",
        help="wall = simulate projecting the result onto the painting",
    )
    p.add_argument("--out", default="runs")
    p.set_defaults(func=_cmd_evolve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    return args.func(args)

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


def _cmd_run(args: argparse.Namespace) -> int:  # pragma: no cover - needs a display
    from PIL import Image

    from illusionframe.config import get_settings
    from illusionframe.engine.loop import LoopState
    from illusionframe.engine.runner import LiveRunner
    from illusionframe.mutators.procedural import ProceduralMutator
    from illusionframe.outputs.window import LiveWindow

    settings = get_settings()
    session, canvas, mask = _prepare(args)
    snaps = Path(args.out) / "snapshots"
    idle = ProceduralMutator() if session.loop.idle_strength > 0 else None
    state = LoopState(canvas, mask, session.loop, session.schedule, idle=idle)
    window = LiveWindow(canvas, wall=args.view == "wall", feedback=session.loop.feedback)

    def snapshot(frame):
        snaps.mkdir(parents=True, exist_ok=True)
        path = snaps / f"{time.strftime('%Y%m%d-%H%M%S')}.png"
        Image.fromarray(frame).save(path)
        logger.info("saved %s", path)

    print("keys: space = mutate now, n = next prompt, v = wall preview, s = snapshot, q = quit")
    LiveRunner(
        state,
        _mutator(session, settings),
        window,
        on_record=lambda r: logger.info("%s", r),
        on_snapshot=snapshot,
    ).run()
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:  # pragma: no cover - needs a display
    from illusionframe.imageops import to_canvas
    from illusionframe.masks.build import build_mask
    from illusionframe.outputs.window import pick_points
    from illusionframe.session import MaskSpec, Session

    session = Session.load(args.session if args.session and Path(args.session).exists() else None)
    canvas = to_canvas(_load_picture(args.image))
    segmenter = None
    if args.mask == "boundarybrush":
        from boundarybrush import get_segmenter

        segmenter = get_segmenter(args.backend)

    def preview(points, labels):
        spec = MaskSpec(kind=args.mask, points=points, labels=labels, backend=args.backend)
        if args.mask == "polygon" and len(points) < 3:
            return None
        if args.mask == "grabcut" and len(points) < 2:
            return None
        return build_mask(spec, canvas, segmenter)

    print(f"{args.mask}: left click = add point (right click = exclude), enter = save, r = reset, q = quit")
    picked = pick_points(canvas, "illusionFrame setup", preview)
    if picked is None:
        print("aborted; nothing saved")
        return 1
    session.mask = MaskSpec(kind=args.mask, points=picked[0], labels=picked[1], backend=args.backend)
    Path(args.session).write_text(session.to_toml())
    print(f"saved {args.session}")
    return 0


def _cmd_fetch_models(args: argparse.Namespace) -> int:
    from illusionframe.config import get_settings
    from illusionframe.mutators.diffusion import DiffusionMutator

    settings = get_settings()
    DiffusionMutator.from_pretrained(settings.model_id, settings.tiny_vae_id)
    print(f"cached {settings.model_id} and {settings.tiny_vae_id}; runs now work with HF_HUB_OFFLINE=1")
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

    p = sub.add_parser("run", help="live window: the loop mutates the picture in front of you")
    p.add_argument("image")
    p.add_argument("--session", default=None)
    p.add_argument("--mutator", choices=["procedural", "diffusion", "mock"], default=None)
    p.add_argument("--view", choices=["canvas", "wall"], default="canvas")
    p.add_argument("--out", default="runs")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("setup", help="click a mask on the picture and save it into a session.toml")
    p.add_argument("image")
    p.add_argument("--mask", choices=["polygon", "grabcut", "boundarybrush"], default="polygon")
    p.add_argument("--backend", default="slimsam", help="boundarybrush backend (slimsam, minisam, unet)")
    p.add_argument("--session", default="session.toml", help="written (and extended if it exists)")
    p.set_defaults(func=_cmd_setup)

    p = sub.add_parser("fetch-models", help="download sd-turbo + TAESD for offline use")
    p.set_defaults(func=_cmd_fetch_models)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    return args.func(args)

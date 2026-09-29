"""Writes a run: out.mp4 (every frame), out.gif (subsampled, small), keyframes/ PNGs, metrics.jsonl."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class Recorder:
    def __init__(self, run_dir: Path, fps: int = 24, gif_fps: int = 6, gif_max_side: int = 288):
        self.run_dir = Path(run_dir)
        (self.run_dir / "keyframes").mkdir(parents=True, exist_ok=True)
        self.fps, self.gif_max_side = fps, gif_max_side
        self.gif_every = max(1, round(fps / gif_fps))
        self._palette: Image.Image | None = None
        self._video: cv2.VideoWriter | None = None
        self._gif: list[Image.Image] = []
        self._n = 0
        self._metrics = (self.run_dir / "metrics.jsonl").open("a")

    def write(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        if self._video is None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._video = cv2.VideoWriter(str(self.run_dir / "out.mp4"), fourcc, self.fps, (w, h))
        self._video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        if self._n % self.gif_every == 0:
            img = Image.fromarray(frame)
            img.thumbnail((self.gif_max_side, self.gif_max_side))
            if self._palette is None:  # one shared palette: small files, no per-frame flicker
                self._palette = img.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
            self._gif.append(img.quantize(palette=self._palette, dither=Image.Dither.FLOYDSTEINBERG))
        self._n += 1

    def keyframe(self, frame: np.ndarray, record: dict) -> None:
        Image.fromarray(frame).save(self.run_dir / "keyframes" / f"iter_{record['iteration']:04d}.png")
        self._metrics.write(json.dumps(record) + "\n")
        self._metrics.flush()

    def close(self) -> None:
        if self._video is not None:
            self._video.release()
        if self._gif:
            ms = round(1000 * self.gif_every / self.fps)
            self._gif[0].save(
                self.run_dir / "out.gif",
                save_all=True,
                append_images=self._gif[1:],
                duration=ms,
                loop=0,
            )
        self._metrics.close()
        logger.info("wrote %d frames to %s", self._n, self.run_dir)

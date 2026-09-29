"""Drive a LoopState: offline on virtual time (deterministic renders), or live with a worker thread.

Live mode keeps every OpenCV GUI call on the main thread (a macOS requirement); the worker thread
only runs mutate(), which releases the GIL inside torch/OpenCV.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

import numpy as np

from illusionframe.engine.loop import LoopState
from illusionframe.engine.mailbox import Mailbox
from illusionframe.mutators.base import MutationParams, Mutator

logger = logging.getLogger(__name__)


class FrameSink(Protocol):
    def write(self, frame: np.ndarray) -> None: ...

    def keyframe(self, frame: np.ndarray, record: dict) -> None: ...


def _params(step, now: float) -> MutationParams:
    return MutationParams(strength=step.strength, seed=step.seed, time=now, prompt_index=step.prompt_position)


def render_offline(
    state: LoopState,
    mutator: Mutator,
    iterations: int,
    fps: int = 24,
    hold_seconds: float = 0.5,
    sinks: list[FrameSink] | None = None,
) -> list[dict]:
    """Run `iterations` mutations on virtual time and stream every displayed frame to `sinks`."""
    sinks = sinks or []
    mutator.prepare(list(state.schedule.prompts))
    frames_per_iteration = max(1, round((state.cfg.fade_seconds + hold_seconds) * fps))
    now, records = 0.0, []
    for _ in range(iterations):
        x, step = state.next_input()
        t0 = time.perf_counter()
        record = state.submit(mutator.mutate(x, _params(step, now)), now, step)
        record["mutate_seconds"] = round(time.perf_counter() - t0, 3)
        records.append(record)
        logger.info("iteration %d: %s", record["iteration"], record)
        for sink in sinks:
            sink.keyframe(state.last_output, record)
        for _ in range(frames_per_iteration):
            frame = state.tick(now)
            for sink in sinks:
                sink.write(frame)
            now += 1.0 / fps
    return records


class Window(Protocol):
    def show(self, frame: np.ndarray) -> str | None:
        """Display a frame, return the key pressed (or None)."""

    def controls(self) -> dict:
        """Current UI control values, e.g. {"strength": 0.5, "feedback": 0.4}."""

    def close(self) -> None: ...


class LiveRunner:
    def __init__(
        self,
        state: LoopState,
        mutator: Mutator,
        window: Window,
        clock: Callable[[], float] = time.monotonic,
        on_record: Callable[[dict], None] | None = None,
        on_snapshot: Callable[[np.ndarray], None] | None = None,
    ):
        self.state, self.mutator, self.window, self.clock = state, mutator, window, clock
        self.on_record, self.on_snapshot = on_record, on_snapshot
        self.mailbox = Mailbox()
        self._lock = threading.Lock()
        self._request = threading.Event()
        self._stop = threading.Event()
        self._strength_scale = 1.0
        self.worker: threading.Thread | None = None

    def _work(self) -> None:
        while not self._stop.is_set():
            if not self._request.wait(timeout=0.1):
                continue
            self._request.clear()
            if self._stop.is_set():
                break
            with self._lock:
                x, step = self.state.next_input()
                scale = self._strength_scale
            params = _params(step, self.clock())
            params = MutationParams(
                min(1.0, params.strength * scale), params.seed, params.time, params.prompt_index
            )
            try:
                self.mailbox.put((self.mutator.mutate(x, params), step))
            except Exception:  # keep the window alive; surface the error in the log
                logger.exception("mutation failed")

    def _apply_controls(self) -> None:
        c = self.window.controls()
        with self._lock:
            if "feedback" in c:
                self.state.feedback = min(0.8, max(0.0, c["feedback"]))
            if "strength" in c:
                self._strength_scale = max(0.0, c["strength"]) * 2  # slider 0..1 -> 0..2 x schedule

    def run(self, max_iterations: int | None = None) -> None:
        self.mutator.prepare(list(self.state.schedule.prompts))
        self.worker = threading.Thread(target=self._work, name="mutator", daemon=True)
        self.worker.start()
        self._request.set()
        try:
            while True:
                self._apply_controls()
                item = self.mailbox.get(timeout=1 / 30)
                now = self.clock()
                if item is not None:
                    mutated, step = item
                    with self._lock:
                        record = self.state.submit(mutated, now, step)
                    if self.on_record:
                        self.on_record(record)
                    if max_iterations is not None and self.state.iteration >= max_iterations:
                        break
                    self._request.set()  # compute the next one while this one fades in
                key = self.window.show(self.state.tick(now))
                if key == "q":
                    break
                if key == " ":
                    self._request.set()
                elif key == "n":
                    with self._lock:
                        self.state.iteration += self.state.schedule.iterations_per_prompt
                elif key == "s" and self.on_snapshot:
                    self.on_snapshot(self.state.last_output)
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        self._request.set()
        self.mailbox.close()
        if self.worker is not None:
            self.worker.join(timeout=5)
        self.window.close()

from __future__ import annotations

import time

import numpy as np
import pytest

from illusionframe.domain.enums import MaskMode
from illusionframe.engine.loop import LoopConfig, LoopState
from illusionframe.engine.mailbox import Mailbox
from illusionframe.engine.runner import LiveRunner, render_offline
from illusionframe.engine.schedule import Schedule
from illusionframe.imageops import to_canvas
from illusionframe.mutators.mock import MockMutator


def test_schedule_breathes_holds_seed_and_interpolates():
    s = Schedule(
        prompts=("a", "b"),
        iterations_per_prompt=4,
        strength_min=0.2,
        strength_max=0.6,
        breathe_period=8,
        seed=10,
        seed_hold=3,
    )
    steps = [s.at(i) for i in range(16)]
    assert steps[0].strength == pytest.approx(0.2) and steps[4].strength == pytest.approx(0.6)
    assert all(0.2 - 1e-9 <= st.strength <= 0.6 + 1e-9 for st in steps)
    assert [st.seed for st in steps[:7]] == [10, 10, 10, 11, 11, 11, 12]
    assert steps[2].prompt_position == pytest.approx(0.5) and steps[8].prompt_position == pytest.approx(0.0)


def test_schedule_validation():
    with pytest.raises(ValueError):
        Schedule(prompts=())
    with pytest.raises(ValueError):
        Schedule(strength_min=0.8, strength_max=0.2)


def test_loop_config_rejects_runaway_feedback():
    with pytest.raises(ValueError):
        LoopConfig(feedback=0.95)


def _state(painting, **cfg):
    return LoopState(to_canvas(painting), config=LoopConfig(**cfg))


def test_crossfade_reaches_target_after_fade(painting):
    st = _state(painting, fade_seconds=2.0, idle_strength=0)
    ref = st.reference
    new = np.zeros_like(ref)
    st.submit(new, now=10.0)
    assert np.array_equal(st.tick(10.0), ref)
    assert np.array_equal(st.tick(12.0), new)
    mid = st.tick(11.0).astype(int)
    assert abs(mid.mean() - ref.mean() / 2) < 2


def test_result_arriving_mid_fade_restarts_from_the_blend(painting):
    st = _state(painting, fade_seconds=2.0, idle_strength=0)
    st.submit(np.zeros_like(st.reference), now=0.0)
    on_screen = st.tick(1.0)
    st.submit(np.full_like(st.reference, 255), now=1.0)
    assert np.array_equal(st.tick(1.0), on_screen)  # no jump


def test_drift_guard_lowers_feedback_on_blowout(painting):
    st = _state(painting, feedback=0.6, max_clipped=0.05, feedback_decay=0.5)
    record = st.submit(np.full_like(st.reference, 255), now=0.0)
    assert record["clipped"] == 1.0 and st.feedback == pytest.approx(0.3)


def test_inside_mask_leaves_the_rest_of_the_painting_alone(painting):
    canvas = to_canvas(painting)
    mask = np.zeros(canvas.shape[:2], bool)
    mask[100:250, 150:350] = True
    st = LoopState(canvas, mask, LoopConfig(mask_mode=MaskMode.INSIDE, feather=4))
    st.submit(np.zeros_like(canvas), now=0.0)
    out = st.last_output
    assert np.array_equal(out[:50], canvas[:50]) and out[170:180, 240:260].max() == 0


def test_zero_feedback_mutates_the_original(painting):
    st = _state(painting, feedback=0.0)
    st.submit(np.zeros_like(st.reference), now=0.0)
    x, _ = st.next_input()
    assert np.abs(x.astype(int) - st.reference.astype(int)).mean() < 2


def test_mailbox_is_latest_wins():
    box = Mailbox()
    assert box.get(timeout=0.01) is None
    box.put(1)
    box.put(2)
    assert box.get() == 2 and box.get() is None


class _Sink:
    def __init__(self):
        self.frames, self.keys = [], []

    def write(self, frame):
        self.frames.append(frame)

    def keyframe(self, frame, record):
        self.keys.append(record["iteration"])


def test_render_offline_is_deterministic_and_counts_frames(painting):
    def run():
        sink = _Sink()
        st = _state(painting, fade_seconds=1.0, idle_strength=0)
        recs = render_offline(st, MockMutator(), iterations=3, fps=4, hold_seconds=0.5, sinks=[sink])
        return sink, recs

    a, recs = run()
    b, _ = run()
    assert len(a.frames) == 3 * 6 and a.keys == [0, 1, 2] and [r["iteration"] for r in recs] == [0, 1, 2]
    assert all(np.array_equal(x, y) for x, y in zip(a.frames, b.frames, strict=True))


class _SlowMock(MockMutator):
    def mutate(self, canvas, params):
        time.sleep(0.02)
        return super().mutate(canvas, params)


class _StubWindow:
    def __init__(self, strength=0.5):
        self.shown, self.closed, self.strength = 0, False, strength

    def show(self, frame):
        self.shown += 1
        return "q" if self.shown > 2000 else None

    def controls(self):
        return {"strength": self.strength, "feedback": 0.3}

    def close(self):
        self.closed = True


def test_live_runner_runs_and_shuts_down_cleanly(painting):
    records = []
    mut, win = _SlowMock(), _StubWindow()
    runner = LiveRunner(_state(painting, fade_seconds=0.01), mut, win, on_record=records.append)
    runner.run(max_iterations=3)
    assert len(records) == 3 and win.closed and not runner.worker.is_alive()
    assert records[-1]["feedback"] == pytest.approx(0.3)  # UI control applied

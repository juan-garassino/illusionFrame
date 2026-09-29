from __future__ import annotations

import tomllib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from illusionframe.cli import main
from illusionframe.domain.enums import MaskMode, MutatorKind
from illusionframe.imageops import to_canvas
from illusionframe.masks.build import build_mask
from illusionframe.outputs.wall_preview import project
from illusionframe.session import MaskSpec, Session

SESSION = """
[schedule]
prompts = ["a stained glass window", "a coral reef"]
iterations_per_prompt = 2
seed = 3
[loop]
fade_seconds = 0.5
mask_mode = "inside"
[mask]
kind = "polygon"
points = [[0.3, 0.2], [0.7, 0.2], [0.7, 0.8], [0.3, 0.8]]
[mutator]
kind = "mock"
"""


def test_session_parse_roundtrip_and_validation(tmp_path):
    s = Session.from_dict(tomllib.loads(SESSION))
    assert s.schedule.prompts == ("a stained glass window", "a coral reef")
    assert s.loop.mask_mode is MaskMode.INSIDE and s.mutator.kind is MutatorKind.MOCK
    again = Session.from_dict(tomllib.loads(s.to_toml()))
    assert again == s
    with pytest.raises(ValueError):
        Session.from_dict({"loop": {"fedback": 0.2}})
    with pytest.raises(ValueError):
        Session.from_dict({"extra": {}})


def test_polygon_and_full_masks(painting):
    canvas = to_canvas(painting)
    assert build_mask(MaskSpec(), canvas) is None
    m = build_mask(MaskSpec(kind="polygon", points=[[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]]), canvas)
    assert m.shape == canvas.shape[:2] and 0.2 < m.mean() < 0.3
    with pytest.raises(ValueError):
        build_mask(MaskSpec(kind="polygon", points=[[0, 0], [1, 1]]), canvas)


def test_grabcut_finds_the_disc(painting):
    canvas = to_canvas(painting)  # disc centred at (0.5, 0.5), radius ~0.175 of the width
    mask = build_mask(MaskSpec(kind="grabcut", box=[0.25, 0.2, 0.75, 0.8]), canvas)
    h, w = canvas.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    disc = (xx - w / 2) ** 2 + (yy - h / 2) ** 2 < (70 * w / 400) ** 2
    iou = (mask & disc).sum() / (mask | disc).sum()
    assert iou > 0.9


class _StubSegmenter:
    def __init__(self):
        self.calls = []

    def set_image(self, image):
        self.calls.append(("set_image", image.shape))

    def predict(self, prompt):
        self.calls.append(("predict", prompt))
        from types import SimpleNamespace

        return SimpleNamespace(mask=np.ones((384, 512), bool))


def test_boundarybrush_adapter_uses_canvas_pixels(painting, monkeypatch):
    import sys
    import types

    fake = types.ModuleType("boundarybrush")

    class Prompt:
        def __init__(self, points, labels, box):
            self.points, self.labels, self.box = points, labels, box

    fake.Prompt, fake.get_segmenter = Prompt, lambda backend: None
    monkeypatch.setitem(sys.modules, "boundarybrush", fake)
    seg = _StubSegmenter()
    mask = build_mask(
        MaskSpec(kind="boundarybrush", points=[[0.5, 0.25]]), to_canvas(painting), segmenter=seg
    )
    assert mask.all()
    assert seg.calls[0] == ("set_image", (384, 512, 3))
    prompt = seg.calls[1][1]
    assert prompt.points == [(256.0, 96.0)] and prompt.labels == [1]


def test_wall_preview_light_model():
    painting = np.full((4, 4, 3), 180, np.uint8)
    dark = project(painting, np.zeros_like(painting))
    lit = project(painting, np.full_like(painting, 255))
    blown = project(painting, np.full_like(painting, 255), gain=10)
    assert dark.mean() < painting.mean() < blown.mean() + 1 and dark.mean() < lit.mean()
    assert blown.max() == 255


@pytest.mark.parametrize("view", ["canvas", "wall"])
def test_evolve_writes_a_run(tmp_path, painting, capsys, view):
    img = tmp_path / "painting.png"
    Image.fromarray(painting).save(img)
    session = tmp_path / "s.toml"
    session.write_text(SESSION)
    code = main(
        [
            "evolve",
            str(img),
            "--session",
            str(session),
            "--iterations",
            "3",
            "--fps",
            "6",
            "--out",
            str(tmp_path / "runs"),
            "--view",
            view,
        ]
    )
    assert code == 0
    run = Path(capsys.readouterr().out.strip().splitlines()[-1])
    for name in ("out.mp4", "out.gif", "metrics.jsonl", "session.toml"):
        assert (run / name).exists(), name
    assert len(list((run / "keyframes").glob("*.png"))) == 3


def test_parser_has_all_commands():
    from illusionframe.cli import build_parser

    parser = build_parser()
    for argv in (
        ["run", "x.jpg", "--view", "wall"],
        ["setup", "x.jpg", "--mask", "grabcut"],
        ["fetch-models"],
    ):
        assert parser.parse_args(argv).func is not None

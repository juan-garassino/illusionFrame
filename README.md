# illusionFrame

A picture that mutates itself: segmentation plus generative AI in a feedback loop, aimed at projection mapping.

> **Status: early scaffold (v0.1.0).** Tooling, CI and a written design spec exist. The mutation engine, masks, and `setup` / `evolve` / `run` commands described below are **not implemented yet**.

## What and why

The idea is an on-device app that takes a picture (for example a painting), masks a region of it, and repeatedly mutates that region with a generative model, feeding each output back as the next input. The longer-term goal is art interventions and projection mapping, where the mutating image is projected back onto the original painting. The v1.0 target is a local prototype that works from a single picture on CPU; camera, projector and Arduino hardware are roadmap items. The full plan is in the [design spec](docs/superpowers/specs/2026-09-28-illusionframe-v1-design.md).

## Planned design (from the spec)

- Everything happens in canvas space: mask, mutation, compositing, crossfade and recording share one canvas (long side 512, sides multiples of 64).
- Two mutators behind one interface: a model-free procedural mutator (also used as idle motion) and a diffusion mutator using `stabilityai/sd-turbo` with the TAESD tiny VAE.
- Drift guard: the input is blended with the reference image and colour-matched in Lab space, and feedback is lowered when output clipping exceeds 5%.
- Masks: full image, clicked polygon, GrabCut, or an optional sibling segmenter (boundaryBrush).
- Planned commands: `setup`, `evolve` (offline render to MP4/GIF), `run` (live window), `fetch-models`.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 or 3.12.

```bash
git clone https://github.com/juan-garassino/illusionFrame
cd illusionFrame
make install          # uv sync --extra dev  (numpy, OpenCV, Pillow; no torch)
uv run illusionframe --version   # prints "illusionframe 0.1.0"
make lint             # ruff
```

`make install-diffusion` adds CPU torch 2.2.2 and diffusers; it is only exercised by the CI import smoke test, since no diffusion code exists yet. Verified in a CPU sandbox: install, `--version` and lint work. `make demo` and `make fetch-models` will fail for now (no subcommands, no `examples/` directory), and the test suite has no tests yet.

## Project structure

```
src/illusionframe/
  cli.py        argparse entry point (no subcommands registered yet)
  config.py     Settings dataclass from ILLUSIONFRAME_* env vars (RUNS_DIR, MODEL_ID, TINY_VAE_ID, TORCH_THREADS)
docs/superpowers/specs/   v1.0 design spec
.github/workflows/ci.yml  lint + tests; diffusion-stack import smoke test; CPU-only lockfile check
pyproject.toml, uv.lock   uv project, optional extras: diffusion, dev
Makefile                  install, test, lint, demo, fetch-models targets
```

## Results

None yet. No demo outputs, metrics or timings exist in the repo.

## Tech stack

Python 3.11/3.12, uv, NumPy, OpenCV, Pillow; planned: PyTorch 2.2.2 (CPU), diffusers, sd-turbo; pytest, ruff, GitHub Actions.

## Roadmap

1. v1.0: image ops, procedural and diffusion mutators, masks, `evolve` and live `run` (see spec phases 0-8).
2. v1.1+: webcam source, projector output with corner-pin, Arduino controls and LED matrix, ESP32-CAM.

## License

[MIT](LICENSE)

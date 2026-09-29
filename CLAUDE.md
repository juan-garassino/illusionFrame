# illusionFrame

A picture that mutates itself: segmentation + generative AI in a feedback loop, toward projection
mapping (festival-of-lights style, or onto one of Juan's paintings). v1.0 is picture-only; camera,
projector and Arduino are in ROADMAP.md.

## Commands

- `make install` (core, no torch) · `make install-diffusion` · `make test` · `make lint`
- `uv run illusionframe evolve examples/painting.jpg --session examples/session.toml`
- `uv run illusionframe run IMAGE [--mutator diffusion] [--view wall]` · `setup IMAGE --mask grabcut`

## Invariants

- **Everything happens in canvas space**: RGB uint8, the picture's aspect, long side 512, sides
  multiples of 64 (`imageops.canvas_size`). Only future sources/outputs use homographies.
- The loop (`engine/loop.py`) is pure: no threads, no IO, time passed in. `render_offline` drives it
  on virtual time (deterministic renders); `LiveRunner` keeps all OpenCV GUI calls on the main
  thread (macOS requirement) and mutates on one worker thread through a latest-wins `Mailbox`.
- Feedback is capped at 0.8; blown-out outputs (clipped > 5%) shrink it; Reinhard transfer anchors
  colours to the reference every iteration.
- Torch stays out of core: the procedural mutator needs only numpy + OpenCV.

## Module map

- `imageops.py` canvas sizing, sRGB/linear, feather, composite, crossfade, Reinhard, frame stats
- `domain/enums.py` MutatorKind, MaskMode, ViewMode · `session.py` session.toml ⇄ dataclasses
- `mutators/` base (Mutator, MutationParams), procedural, diffusion (SD-Turbo + TAESD), mock, registry
- `engine/` schedule (prompt lerp, strength breathing, seed hold), loop (state machine), mailbox, runner
- `masks/build.py` full / polygon / grabcut / boundarybrush (lazy import of the sibling project)
- `outputs/` recorder (mp4, gif, keyframes, metrics.jsonl), wall_preview (projection simulator),
  window (live view, click-to-mask tool)
- `cli.py` evolve, run, setup, fetch-models

## Pins (Intel Mac, macOS 12)

opencv-python 4.10.0.84 (newest macOS-12 x86_64 wheel), torch 2.2.2, diffusers 0.35.x (0.36+ calls
`torch.xpu`), transformers < 5, huggingface-hub < 1. Measured on the 2014 MBP under heavy load:
sd-turbo 512px img2img ≈ 48 s with TAESD vs ≈ 180 s with the full VAE (384px: ≈ 29 s vs ≈ 80 s).

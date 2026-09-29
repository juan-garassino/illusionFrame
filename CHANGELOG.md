# Changelog

## [1.0.0] — unreleased

First release: the picture-only prototype.

- Canvas-space feedback loop: feedback mix, Reinhard colour anchoring, blow-out drift guard, feathered
  masks, crossfades; pure state machine with an injected clock.
- Mutators: procedural (model-free, real time) and SD-Turbo img2img tuned for CPU (TAESD, prompt
  embeddings precomputed and interpolated, text encoder released, effective-step floor).
- Masks: polygon, GrabCut, boundaryBrush promptable segmentation (optional).
- `illusionframe evolve` (offline, deterministic mp4/gif), `run` (live window with trackbars and
  keys), `setup` (click a mask), `fetch-models`; `--view wall` simulates projecting onto the painting.

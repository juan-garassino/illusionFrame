# Part B — illusionFrame v1.0 — a picture that mutates itself

## Context

Juan's idea: "an easy app that runs on device, using computer vision and generative AI to mutate what it
sees in a loop" — for art interventions / Festival-of-Lights projection mapping, and at home: map one of
his paintings and let generative AI transform it. The old GitHub repo `ilussionFrame` (archived) is a
verbatim copy of HF diffusers 0.2.4 with no original code — nothing to port; it stays archived.

Juan owns **no hardware yet** (no projector, external camera, LEDs, pots) and asked: **"first a prototype
that works with a picture locally."** So v1.0 = picture in → mask → mutation loop → live window + rendered
MP4/GIF, on this CPU. Camera, projector, Arduino (Uno controls + LED matrix + standalone mode) and
ESP32-CAM are a written v1.1+ roadmap; v1.0 keeps the seams (source/output ABCs) so they bolt on.

## What v1.0 delivers

```
illusionframe setup painting.jpg                 # click a mask (polygon / GrabCut / boundaryBrush) → session.toml
illusionframe evolve painting.jpg --session s.toml --mutator procedural|diffusion --iterations 60
                                                 # offline render on virtual time → runs/<ts>/{frames/, out.mp4, out.gif, metrics.jsonl}
illusionframe run painting.jpg --session s.toml  # live window: loop + crossfades; trackbars strength/feedback;
                                                 # keys: space mutate-now, n next prompt, v view (canvas / on-the-wall preview), s snapshot, q quit
illusionframe fetch-models                       # sd-turbo + TAESD into the HF cache, so runs work offline
```

**Invariant (goes into CLAUDE.md):** everything happens in *canvas space* — mask, mutation, compositing,
crossfade, feedback, recording. Canvas = the picture's aspect, long side 512, both sides multiples of 64
(sd-turbo native). Only future sources (camera→canvas) and outputs (canvas→projector) use homographies.

## Layout (new repo `004-creative-tools/010-illusionFrame`, package `illusionframe`)

```
src/illusionframe/
  __init__.py __main__.py cli.py config.py      # dataclass config + ILLUSIONFRAME_* env; torch threads 3, cv2 threads 1
  domain/enums.py    MutatorKind, MaskMode(inside/outside/all), ViewMode(canvas/wall)
  domain/models.py   Keyframe, Schedule, Session (dataclasses, validated)
  session.py         tomllib load/validate; copied into runs/<ts>/
  imageops.py        canvas sizing, sRGB↔linear, feathered mask (cv2.distanceTransform), composite,
                     crossfade, Reinhard colour transfer in Lab, frame stats (luma, saturation, clipped %)
  sources/base.py file.py                         # FileSource only in v1.0 (camera = v1.1)
  masks/base.py full.py polygon.py grabcut.py boundarybrush.py   # boundaryBrush adapter = lazy import
  mutators/base.py registry.py mock.py procedural.py diffusion.py
  engine/schedule.py  keyframe prompt-embedding lerp, strength "breathing", seed hold/advance
  engine/loop.py      sans-IO LoopState.tick(now, result) -> DisplayFrame; drift guard; injected clock
  engine/mailbox.py   latest-wins slot (Lock), not Queue
  engine/runner.py    main thread = UI/cv2; worker thread = mutate() only
  outputs/base.py window.py recorder.py wall_preview.py null.py
tests/  examples/session.toml  docs/images/  ROADMAP.md
```

## Key design decisions

- **Mutators (providers pattern):** `Mutator.mutate(canvas_rgb, mask, params) -> canvas_rgb`.
  - `ProceduralMutator` — no model, < 50 ms at 512: hue drift, noise-field displacement, edge glow along
    the mask boundary, micro-zoom/kaleidoscope. Also runs as **idle motion between diffusion keyframes**
    so the window never freezes during 5–15 s generations.
  - `DiffusionMutator` (`[diffusion]` extra) — `AutoPipelineForImage2Image` with `stabilityai/sd-turbo`
    + `AutoencoderTiny("madebyollin/taesd")` for encode/decode, `guidance_scale=0.0`, fp32; validates
    `int(steps*strength) >= 1`; **precomputes `prompt_embeds` for every keyframe, then frees the text
    encoder** (~5.2 GB → ~3.8 GB resident); `accelerate` for `low_cpu_mem_usage`; pipeline injected so
    tests use a stub. Full VAE behind a flag for quality comparison.
  - `MockMutator` for tests.
- **Loop & drift guard:** input `x = lerp(reference, last_output, feedback)` (feedback ≤ 0.8) → Reinhard
  transfer back to the reference's Lab statistics → mutate → composite through the feathered mask →
  crossfade. If clipped % > 5, feedback auto-lowers; optional reset to the reference every K iterations.
  Stats logged to `metrics.jsonl` (becomes a README chart).
- **Making it interesting:** keyframes lerp `prompt_embeds` (smooth semantic morphing at no extra cost),
  strength breathes between an effective-step floor and ~0.65, seed held for N iterations then advanced,
  mask modes keep the rest of the painting as an anchor. `evolve` runs on virtual time → smooth 30 fps
  output independent of CPU speed; `run` uses the same engine on wall-clock time.
- **Masks:** full / polygon (clicked) / GrabCut (cv2, no model) / boundaryBrush `Segmenter` (clicks →
  `Prompt`, `set_image` once). boundaryBrush is *not* a pyproject dependency in v1.0 (a sibling path
  source would break CI locking); the adapter imports lazily with the hint `uv pip install -e
  ../002-boundaryBrush`, switching to `boundarybrush @ git+…@v1.0.0` in a `[segment]` extra once Part A
  is public.
- **On-the-wall preview** (`ViewMode.wall`): how the mutation would look *projected onto the painting* —
  linear-light model `cam = clip(exposure · R ⊙ (ambient + black + gain · P))^(1/2.2)` with R = painting
  reflectance, projector black ≈ 0.03. Two projection modes: `overlay` and `mask-only`. This is the bridge
  to the projection work without hardware.
- **Demo picture:** a public-domain painting (Wikimedia Commons) for README until Juan photographs his own.
- **Licences:** sd-turbo is under the Stability community licence — fine for personal/portfolio use; a
  paid festival show needs a check (documented; weights never redistributed).

## Dependencies & tooling

```toml
requires-python = ">=3.11,<3.13"
dependencies = ["numpy>=1.26,<2", "opencv-python==4.10.0.84", "pillow>=10"]   # 4.10.0.84 = newest macOS-12 x86_64 wheel
[project.optional-dependencies]
diffusion = ["torch==2.2.2", "diffusers>=0.33,<0.39",      # frozen to == after the spike (0.39+ needs torch>=2.6)
             "transformers>=4.49,<5", "huggingface-hub>=0.30,<1", "safetensors>=0.4", "accelerate>=1.0,<2"]
dev = ["pytest>=7.2", "ruff"]
```
Same uv `environments` + pytorch-cpu index as Part A. Torch stays out of core, so procedural mode and the
main CI job need only numpy + OpenCV. CI: (1) `uv sync --extra dev` → pytest + ruff; (2) smoke-import with
`--extra diffusion` importing `AutoPipelineForImage2Image` / `AutoencoderTiny`, `! grep -q nvidia uv.lock`,
`HF_HUB_OFFLINE=1`. Makefile: awk help, install, test, test-ci, lint, demo, clean.

## Reuse

- Part A: `Segmenter`/`Prompt`/`MaskResult` + `Backend.mock`; dataclass-config pattern; CLI build_parser
  + lazy imports (024-dino); Makefile help + CI offline flags (025-ltm); deviations note.
- v1.1 Arduino link mirrors `001-PromptPlot/promptplot/plotter.py`: `ConnectionState` + transition table,
  single reader thread, simulated twin with `collected`, context-manager connect — without its asyncio,
  per-line acks, GRBL heartbeat or fixed sleeps.

## Implementation phases (TDD; commit per phase on `feat/v1`)

0. **Scaffold + spikes.** `git init` (spec on `main`), branch `feat/v1`, pyproject/Makefile/CI/config.
   Spikes: (a) cv2 4.10 window + trackbars + keys on the main thread on macOS 12; (b) diffusers version
   search from 0.38.x down on torch 2.2.2 → sd-turbo img2img 512 + TAESD: seconds/iteration and peak RAM
   (`/usr/bin/time -l`), text encoder dropped; freeze exact pins; (c) sd-turbo licence/gating check.
1. **Pure maths.** `imageops.py`. Tests first: canvas sizing (multiples of 64, aspect kept), feather mask
   exactly 0/1 beyond radius, composite/crossfade endpoints, Reinhard hits target mean/std, stats.
2. **Mutators.** base/registry/mock/procedural. Tests: seeded determinism, shape/dtype kept, registry by
   enum, procedural < 50 ms at 512.
3. **Engine (sans-IO first).** schedule/loop/mailbox/runner. Tests with a fake clock: crossfade reaches
   target after `fade`; a result arriving mid-fade restarts from the blended frame; embedding lerp +
   seed hold; drift guard lowers feedback on synthetic blow-out; runner with stub mutator + NullOutput
   runs N iterations and shuts down cleanly.
4. **Session + recorder + `evolve`.** Tests: session validation errors; `evolve tiny.png --mutator
   procedural --iterations 3` writes frames, mp4, gif, metrics. **M1:** procedural GIF from a picture.
5. **Masks.** full/polygon/grabcut/boundarybrush. Tests: stub Segmenter records calls (`set_image` once
   for 3 predicts, canvas-pixel coords), `outside` inverts, GrabCut on a synthetic disc IoU > 0.9.
6. **DiffusionMutator.** Stub pipeline recording kwargs: effective-step rule raises, embeddings encoded
   once per prompt then text encoder released, lerped embeds passed, seed follows schedule, output
   resized to canvas; real run `@pytest.mark.slow` (skipped offline). **M2:** diffusion `evolve` GIF of
   the demo painting (~60 iterations × ~10 s, run in background).
7. **Live `run` + wall preview.** Window, trackbars, keys, view toggle, snapshots. **M3:** interactive
   session on a picture.
8. **Docs + release (ask first).** README (demo GIFs, timing/RAM table from the spikes, honest
   limitations, "what runs where"), CLAUDE.md (canvas-space invariant, module list), CHANGELOG,
   **ROADMAP.md for v1.1+**: webcam source + setup on a live frame; projector window with manual
   corner-pin (any HDMI screen works as stand-in); Arduino Uno controls (pots→strength/feedback/prompt,
   buttons→mutate/next; serial protocol with `R` stop-and-wait flow control because `FastLED.show()`
   drops UART bytes; wait for a banner, not a sleep); 16×16 WS2812B output (768 B framebuffer, external
   5 V ≥4 A PSU, never the Uno's 5 V pin) + standalone procedural firmware mode; ESP32-CAM MJPEG source;
   dot-differencing calibration; radiometric compensation. New public repo `juan-garassino/illusionFrame`,
   tag v1.0.0.

## Verification

- `make test` green offline; smoke-import job imports the diffusion stack on torch 2.2.2.
- `illusionframe evolve examples/painting.jpg --mutator procedural` → mp4 + gif in seconds;
  `--mutator diffusion` → coherent evolving GIF; metrics show no blow-out (clipped % stays < 5).
- `illusionframe run …` responds to trackbars/keys while a diffusion step is running (UI never blocks).
- With Part A installed: `setup --mask boundarybrush` produces a SlimSAM mask from clicks.

## Docs to update

- New: `010-illusionFrame/{README,CLAUDE,CHANGELOG,ROADMAP}.md`.
- `005-products/DOCS.md` § 004-CreativeTools: add an illusionFrame line.

---

# illusionFrame roadmap

v1.0 is the picture-only prototype: a photo of a painting in, a mutating loop out (live window or
rendered video). Everything below builds on its seams — `sources/` for inputs, `outputs/` for
displays, the canvas-space invariant — and needs hardware Juan does not own yet.

## v1.1 — camera and projector

- **Webcam source** (`sources/camera.py`): OpenCV capture on the main thread, discard the first ~10
  frames (auto-exposure), `devices` command that probes indices 0–3 and explains the macOS camera
  permission (granted to the terminal app). Camera → canvas via a homography from 4 clicked corners.
- **Projector window with manual corner-pin**: drag the four projected corners onto the painting
  (the MadMapper/Resolume approach) → `mapping.json` = H_proj←canvas. Any HDMI TV or monitor works as a
  stand-in. Put the window on the second display with `WINDOW_NORMAL` + `moveWindow` + `resizeWindow`
  (display origin and size in session.toml; OpenCV cannot enumerate displays).
- **Camera-in-the-loop feedback**: the input becomes what the camera sees (painting + projection);
  keep the drift guard and the feedback cap.
- **Dot-differencing calibration** (camera ↔ projector): project a dot grid, subtract a black frame,
  find blobs, `findHomography(RANSAC)`, report RMS. More robust than a chessboard projected onto a
  textured painting. The wall-preview simulator doubles as its test fixture.
- **Radiometric compensation** (P = target / R, clipped): make the painting *look like* the mutation.

## v1.2 — Arduino (Uno / Nano)

- **Controls**: pots → strength / feedback / prompt position, buttons → mutate now / next prompt.
  The host smooths pots (EMA + deadband); the board latches button presses between reports.
- **Serial protocol**: stop-and-wait. The board loops "read sensors → send control line → send `R`
  → wait ≤100 ms for one frame → show()"; the host only sends after `R`. Needed because
  `FastLED.show()` disables interrupts for ~7.7 ms on 256 LEDs and drops UART bytes. Opening the port
  resets the board: wait for a `H illusionframe 1 16x16` banner, not a fixed sleep. Mirror
  `001-PromptPlot/promptplot/plotter.py`'s ConnectionState machine and simulated twin (without its
  asyncio, per-line acks or GRBL heartbeat).
- **16×16 WS2812B output**: 768-byte framebuffer (fits the Uno's 2 KB), receive straight into
  `leds[]`, no second buffer, `F()` strings. ~13 fps at 115200 baud, ~25 fps at 500000.
  **Power**: 256 LEDs × 60 mA ≈ 15 A at full white — external 5 V ≥ 4 A supply,
  `setMaxPowerInVoltsAndMilliamps(5, 2000)`, 330–470 Ω data resistor, 1000 µF capacitor, common
  ground, never the Uno's 5 V pin.
- **Standalone firmware mode**: when the host goes quiet, the board runs its own procedural pattern
  steered by the pots — what "runs on the board" honestly means for an Uno (no AI fits in 2 KB).
- CI compiles the firmware (`arduino/compile-sketches`, pinned FastLED).

## Later

- ESP32-CAM as a Wi-Fi camera (MJPEG `StreamSource`).
- Building-scale mapping, multiple projectors, audio reactivity.
- **Several paintings on one wall, found automatically**: an open-vocabulary detector (Grounding DINO
  or OWLv2, query like `"painting . poster . framed picture"`) gives boxes; box prompts to SAM 2 (or
  boundaryBrush, which takes box prompts) give masks; `approxPolyDP` / `minAreaRect` turn each mask
  into a TL-TR-BR-BL quad → one canvas per painting. Assign IDs once per scan (sorted left to right)
  and match by IoU on re-scan so they do not shuffle. Opt-in alongside manual corner-pin, not instead.
- **Closed-loop latent walk** for `render_offline`: slerp between noise seeds with the last seed equal
  to the first, so a rendered clip loops without a jump; optional RIFE/FILM frame interpolation to
  get more frames per diffusion call.
- **Mask inset**: erode the mask a few projector pixels before feathering so light does not spill
  onto the wall around the frame.
- **Precomputed warps**: compute each painting's projector warp once per mapping (cache the remap
  tables) instead of solving it every frame; GPU warping only if many paintings.
- **Event interaction**: guests submit prompts by QR code → small web form → prompt queue; DJ cue or
  timer switches every painting's prompt together; pose/gesture (MediaPipe) or proximity nudges
  strength. Prompt changes ride the loop's existing prompt lerp + crossfade.

### Prototype pitfalls (from earlier chats)

- COCO has no "painting" class — filtering Mask R-CNN on label 78 gave "microwave". Use
  open-vocabulary detection.
- Blank the projector (full black) while the camera scans or calibrates, or it detects its own output.
- Camera pixels are not projector pixels: never reuse camera boxes as projector coordinates without
  the homography, and keep 4-corner quads (an axis-aligned bounding box loses the perspective).

### Parked ideas (earlier chats)

Recorded, not adopted — the local decision in brackets stands.

- Zero-manual-geometry setup: detection + automatic camera↔projector calibration with no clicks
  [manual corner-pin first; auto-detection above is opt-in].
- ArUco/ChArUco pattern for calibration [dot-differencing, robust on a textured painting].
- FLUX (schnell / Kontext) img2img, local or via the hosted API [SD-Turbo + TAESD, fits CPU].
- Streamlit operator UI plus a separate pygame/moderngl fullscreen renderer [OpenCV window on the
  main thread, session.toml].
- Generate each painting's walk once, cache frames to disk, show phase only plays them back
  [live mutation loop; `render_offline` covers recorded output].

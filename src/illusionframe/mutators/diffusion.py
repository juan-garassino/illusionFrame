"""SD-Turbo img2img as a mutator (optional extra `[diffusion]`).

CPU-minded choices: guidance off (turbo models are trained for it), 1-2 denoising steps, the tiny
TAESD autoencoder instead of the full VAE, fp32 (no fast bf16 on older Intel CPUs), and every
prompt encoded once up front so the ~1.4 GB text encoder can be dropped from memory. Prompt
positions between keyframes interpolate the embeddings, which morphs smoothly for free.
"""

from __future__ import annotations

import gc
import logging
import math

import numpy as np

from illusionframe.domain.enums import MutatorKind
from illusionframe.imageops import to_canvas
from illusionframe.mutators.base import MutationParams, Mutator

logger = logging.getLogger(__name__)


class DiffusionMutator(Mutator):
    kind = MutatorKind.DIFFUSION

    def __init__(self, pipe, steps: int = 2):
        if steps < 1:
            raise ValueError("steps must be >= 1")
        self.pipe = pipe
        self.steps = steps
        self._embeds: list = []

    @classmethod
    def from_pretrained(
        cls,
        model_id: str = "stabilityai/sd-turbo",
        tiny_vae_id: str | None = "madebyollin/taesd",
        steps: int = 2,
        threads: int | None = None,
    ) -> DiffusionMutator:
        try:
            import torch
            from diffusers import AutoencoderTiny, AutoPipelineForImage2Image
        except ImportError as e:
            raise ImportError(
                "the diffusion mutator needs the [diffusion] extra: uv sync --extra diffusion"
            ) from e
        if threads:
            torch.set_num_threads(threads)
        pipe = AutoPipelineForImage2Image.from_pretrained(
            model_id, variant="fp16", torch_dtype=torch.float32, use_safetensors=True, low_cpu_mem_usage=True
        )
        if tiny_vae_id:
            pipe.vae = AutoencoderTiny.from_pretrained(tiny_vae_id, torch_dtype=torch.float32)
        pipe.set_progress_bar_config(disable=True)
        return cls(pipe, steps)

    def min_strength(self) -> float:
        """img2img runs int(steps * strength) steps; below 1/steps it would run none."""
        return 1.0 / self.steps

    def prepare(self, prompts: list[str]) -> None:
        if not prompts:
            raise ValueError("need at least one prompt")
        self._embeds = []
        for prompt in prompts:
            embeds, _ = self.pipe.encode_prompt(
                prompt, device="cpu", num_images_per_prompt=1, do_classifier_free_guidance=False
            )
            self._embeds.append(embeds)
        self.pipe.text_encoder = None  # every prompt is encoded; free ~1.4 GB
        gc.collect()
        logger.info("encoded %d prompt(s); text encoder released", len(prompts))

    def embeds_at(self, position: float):
        if not self._embeds:
            raise RuntimeError("call prepare(prompts) before mutate()")
        n = len(self._embeds)
        i = int(math.floor(position)) % n
        w = position - math.floor(position)
        if w == 0 or n == 1:
            return self._embeds[i]
        return self._embeds[i] * (1 - w) + self._embeds[(i + 1) % n] * w

    def mutate(self, canvas: np.ndarray, params: MutationParams) -> np.ndarray:
        import torch
        from PIL import Image

        strength = float(np.clip(max(params.strength, self.min_strength()), 0.0, 1.0))
        out = self.pipe(
            prompt_embeds=self.embeds_at(params.prompt_index),
            image=Image.fromarray(canvas),
            num_inference_steps=self.steps,
            strength=strength,
            guidance_scale=0.0,
            generator=torch.Generator().manual_seed(params.seed),
            output_type="np",
        ).images[0]
        result = np.clip(np.rint(np.asarray(out) * 255), 0, 255).astype(np.uint8)
        if result.shape[:2] != canvas.shape[:2]:
            result = to_canvas(result, canvas.shape[:2])
        return result

    def describe(self) -> dict:
        return {"kind": self.kind.value, "steps": self.steps}

"""
Image generation plugin — generate_image tool using Prompture's async
image generation drivers.

Supports OpenAI DALL-E, Google Imagen, Stability AI, and Grok/xAI Aurora
via Prompture's built-in driver registry.
"""

import logging

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)


class ImageGenerationPlugin(CachibotPlugin):
    """Provides the generate_image tool for creating images via Prompture's image drivers."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("image_generation", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="image_generation",
            display_name="Image Generation",
            icon="image",
            group="Creative",
            requires=PluginRequirements(network=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="generate_image",
            description="Generate an image from a text prompt. "
            "Supports OpenAI DALL-E 3, Google Imagen 3, Stability AI, and Grok/xAI Aurora. "
            "The model is determined by the bot's image model slot, "
            "or falls back to openai/dall-e-3.",
            category="creative",
            tags=["image", "generation", "dall-e", "imagen", "stability", "grok"],
            side_effects=False,
            requires_network=True,
            display_name="Generate Image",
            icon="image",
            risk_level=RiskLevel.MODERATE,
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text description of the image to generate.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Image dimensions. Defaults to plugin config.",
                        "enum": ["1024x1024", "1792x1024", "1024x1792"],
                        "default": "1024x1024",
                    },
                    "quality": {
                        "type": "string",
                        "description": (
                            "Image quality (OpenAI DALL-E only). 'hd' produces higher detail."
                        ),
                        "enum": ["standard", "hd"],
                        "default": "standard",
                    },
                    "style": {
                        "type": "string",
                        "description": "Image style (OpenAI DALL-E 3 only).",
                        "enum": ["vivid", "natural"],
                        "default": "vivid",
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
            config_params=[
                ConfigParam(
                    name="defaultSize",
                    display_name="Default Size",
                    description="Default image dimensions.",
                    type="select",
                    default="1024x1024",
                    options=["1024x1024", "1792x1024", "1024x1792"],
                ),
                ConfigParam(
                    name="quality",
                    display_name="Quality (OpenAI)",
                    description="Image quality for OpenAI DALL-E. 'hd' produces higher detail.",
                    type="select",
                    default="standard",
                    options=["standard", "hd"],
                ),
                ConfigParam(
                    name="style",
                    display_name="Style (OpenAI)",
                    description="Image style for OpenAI DALL-E 3.",
                    type="select",
                    default="vivid",
                    options=["vivid", "natural"],
                ),
                ConfigParam(
                    name="timeout",
                    display_name="Timeout",
                    description="Maximum time to wait for image generation.",
                    type="number",
                    default=60,
                    min=10,
                    max=300,
                    step=10,
                    unit="seconds",
                ),
            ],
        )
        async def generate_image(
            prompt: str,
            size: str = "",
            quality: str = "",
            style: str = "",
        ) -> str:
            """Generate an image from a text prompt.

            Args:
                prompt: Text description of the image to generate.
                size: Image dimensions (e.g., "1024x1024"). Defaults to plugin config.
                quality: Image quality ("standard" or "hd", OpenAI only). Defaults to config.
                style: Image style ("vivid" or "natural", OpenAI DALL-E 3 only). Defaults to config.

            Returns:
                Markdown image with base64 data URI and generation metadata.
            """
            try:
                from prompture import get_async_img_gen_driver_for_model
            except ImportError:
                logger.error("Prompture image generation drivers not available")
                return "Error: Prompture image generation drivers not available. Update prompture."

            # Resolve config
            tool_cfg = ctx.tool_configs.get("generate_image", {})
            effective_size = size or tool_cfg.get("defaultSize", "1024x1024")
            effective_quality = quality or tool_cfg.get("quality", "standard")
            effective_style = style or tool_cfg.get("style", "vivid")

            # Resolve model from bot's image slot
            model = ""
            if ctx.bot_models:
                model = ctx.bot_models.get("image", "")
            if not model:
                model = "openai/dall-e-3"

            logger.info(
                "Generating image: model=%s, size=%s, quality=%s, style=%s",
                model,
                effective_size,
                effective_quality,
                effective_style,
            )

            try:
                driver = get_async_img_gen_driver_for_model(model)
            except Exception as exc:
                logger.error("Failed to init image driver for '%s': %s", model, exc)
                return f"Error: Failed to initialize image driver for '{model}': {exc}"

            # Build options — each driver takes what it supports and ignores the rest
            options: dict = {
                "size": effective_size,
                "quality": effective_quality,
                "style": effective_style,
                "n": 1,
            }

            # Stability uses aspect_ratio instead of size
            provider = model.split("/", 1)[0].lower() if "/" in model else ""
            if provider == "stability":
                # Convert size to aspect ratio (e.g. "1024x1024" -> "1:1")
                parts = effective_size.split("x")
                if len(parts) == 2:
                    w, h = int(parts[0]), int(parts[1])
                    from math import gcd

                    d = gcd(w, h)
                    options["aspect_ratio"] = f"{w // d}:{h // d}"
                options.pop("size", None)
                options.pop("quality", None)
                options.pop("style", None)

            try:
                result = await driver.generate_image(prompt, options)
            except Exception as exc:
                logger.error("Image generation failed for '%s': %s", model, exc, exc_info=True)
                return f"Error: Image generation failed: {exc}"

            images = result.get("images", [])
            meta = result.get("meta", {})

            if not images:
                return "Error: No images returned from the provider."

            # Build response with summary FIRST so the LLM sees useful info
            # even if the result is truncated (base64 data is very large).
            image = images[0]
            media_type = getattr(image, "media_type", "image/png")
            image_data = getattr(image, "data", "")

            # Summary metadata (placed before the data URI)
            meta_parts = []
            meta_parts.append(f"Model: {meta.get('model_name', model)}")
            if meta.get("size"):
                meta_parts.append(f"Size: {meta['size']}")
            if meta.get("cost"):
                meta_parts.append(f"Cost: ${meta['cost']:.4f}")
            if meta.get("revised_prompt"):
                meta_parts.append(f"Revised prompt: {meta['revised_prompt']}")

            parts = [
                "Image generated successfully.",
                f"*{' | '.join(meta_parts)}*",
                "",
                f"![Generated Image](data:{media_type};base64,{image_data})",
            ]

            return "\n".join(parts)

        return {"generate_image": generate_image.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

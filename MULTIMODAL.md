# Multimodal Models: Image Generation & Audio (TTS/STT)

Prompture extends beyond text LLMs with full support for **image generation**, **text-to-speech (TTS)**, and **speech-to-text (STT)** across multiple providers. All multimodal drivers follow the same patterns as LLM drivers: registry-based instantiation, standardized response contracts, async support, callback hooks, cost tracking, and plugin extensibility.

---

## Table of Contents

- [Image Generation](#image-generation)
  - [Supported Providers](#image-generation-providers)
  - [Quick Start](#image-generation-quick-start)
  - [Response Contract](#image-generation-response-contract)
  - [Provider-Specific Options](#image-generation-options)
  - [Cost & Pricing](#image-generation-pricing)
- [Audio: Text-to-Speech (TTS)](#text-to-speech-tts)
  - [Supported Providers](#tts-providers)
  - [Quick Start](#tts-quick-start)
  - [Streaming](#tts-streaming)
  - [Response Contract](#tts-response-contract)
  - [Provider-Specific Options](#tts-options)
  - [Cost & Pricing](#tts-pricing)
- [Audio: Speech-to-Text (STT)](#speech-to-text-stt)
  - [Supported Providers](#stt-providers)
  - [Quick Start](#stt-quick-start)
  - [Response Contract](#stt-response-contract)
  - [Provider-Specific Options](#stt-options)
  - [Cost & Pricing](#stt-pricing)
- [Model Discovery](#model-discovery)
  - [Discovering Image Models](#discovering-image-models)
  - [Discovering Audio Models](#discovering-audio-models)
  - [LLM Capability Tags](#llm-capability-tags)
- [Media Content Types](#media-content-types)
  - [ImageContent](#imagecontent)
  - [AudioContent](#audiocontent)
- [Async Support](#async-support)
- [Registry & Plugins](#registry--plugins)
  - [Registering Custom Drivers](#registering-custom-drivers)
  - [Entry Point Plugins](#entry-point-plugins)
  - [Listing Registered Drivers](#listing-registered-drivers)
- [Callbacks & Observability](#callbacks--observability)
- [Configuration](#configuration)

---

## Image Generation

### Image Generation Providers

| Provider | Models | Multi-Image | Size Variants | SDK |
|----------|--------|:-----------:|:-------------:|-----|
| **OpenAI** | `dall-e-3`, `dall-e-2` | Yes (up to 10) | Yes (5 sizes) | `openai` |
| **Google** | `imagen-3.0-generate-002`, `imagen-3.0-fast-generate-001` | Yes (up to 4) | No (1024x1024) | `google-genai` |
| **Stability AI** | `stable-image-core`, `sd3.5-large`, `sd3.5-large-turbo`, `sd3.5-medium` | No (1 per call) | Yes (9 aspect ratios) | `httpx` |
| **Grok/xAI** | `grok-2-image` | Yes (up to 10) | No (1024x1024) | `openai` |

### Image Generation Quick Start

```python
from prompture.drivers import get_img_gen_driver_for_model

# Instantiate a driver using "provider/model" format
driver = get_img_gen_driver_for_model("openai/dall-e-3")

# Generate an image
result = driver.generate_image("a cat surfing on a wave at sunset", {
    "size": "1024x1024",
    "quality": "hd",
    "style": "vivid",
})

# Access the result
for image in result["images"]:
    print(image.media_type)    # "image/png"
    print(len(image.data))     # base64-encoded length

print(result["meta"]["cost"])            # 0.08
print(result["meta"]["revised_prompt"])  # DALL-E 3 revised prompt
```

### Image Generation Response Contract

Every image generation driver returns the same structure:

```python
{
    "images": [ImageContent, ...],  # List of generated images
    "meta": {
        "image_count": int,          # Number of images generated
        "size": str,                 # Size/aspect ratio used
        "revised_prompt": str | None,# Provider-revised prompt (DALL-E 3, Grok)
        "cost": float,              # USD cost
        "model_name": str,          # e.g. "openai/dall-e-3"
        "raw_response": dict,       # Provider-specific raw response
    },
}
```

### Image Generation Options

#### OpenAI DALL-E

```python
driver = get_img_gen_driver_for_model("openai/dall-e-3")
result = driver.generate_image("prompt", {
    "size": "1024x1024",       # 256x256, 512x512, 1024x1024, 1792x1024, 1024x1792
    "quality": "standard",     # "standard" or "hd" (DALL-E 3 only)
    "style": "vivid",          # "vivid" or "natural" (DALL-E 3 only)
    "n": 3,                    # Number of images (DALL-E 3 loops n=1 internally)
})
```

#### Google Imagen

```python
driver = get_img_gen_driver_for_model("google/imagen-3.0-generate-002")
result = driver.generate_image("prompt", {
    "n": 4,                    # 1-4 images per call
})
# Fixed output size: 1024x1024. Raises ValueError if prompt is safety-blocked.
```

#### Stability AI

```python
driver = get_img_gen_driver_for_model("stability/stable-image-core")
result = driver.generate_image("prompt", {
    "aspect_ratio": "16:9",    # 1:1, 16:9, 21:9, 2:3, 3:2, 4:5, 5:4, 9:16, 9:21
    "output_format": "png",    # "png", "jpeg", "webp"
    "negative_prompt": "blurry, low quality",
    "seed": 42,                # For reproducibility
})
# Single image per call only.
```

#### Grok/xAI Aurora

```python
driver = get_img_gen_driver_for_model("grok/grok-2-image")
result = driver.generate_image("prompt", {
    "n": 2,                    # Up to 10 images
})
# Fixed output size: 1024x1024. OpenAI-compatible API via xAI base URL.
```

### Image Generation Pricing

| Model | Size/Quality | Price per Image |
|-------|-------------|:-----------:|
| `dall-e-3` | 1024x1024 / standard | $0.04 |
| `dall-e-3` | 1024x1024 / hd | $0.08 |
| `dall-e-3` | 1792x1024 / standard | $0.08 |
| `dall-e-3` | 1792x1024 / hd | $0.12 |
| `dall-e-2` | 256x256 | $0.016 |
| `dall-e-2` | 512x512 | $0.018 |
| `dall-e-2` | 1024x1024 | $0.020 |
| `imagen-3.0-generate-002` | 1024x1024 | $0.04 |
| `imagen-3.0-fast-generate-001` | 1024x1024 | $0.02 |
| `stable-image-core` | any | $0.03 |
| `sd3.5-large` | any | $0.065 |
| `sd3.5-large-turbo` | any | $0.04 |
| `sd3.5-medium` | any | $0.035 |
| `grok-2-image` | 1024x1024 | $0.07 |

---

## Text-to-Speech (TTS)

### TTS Providers

| Provider | Models | Streaming | Voices | SDK |
|----------|--------|:---------:|--------|-----|
| **OpenAI** | `tts-1`, `tts-1-hd` | Yes | alloy, echo, fable, onyx, nova, shimmer | `openai` |
| **ElevenLabs** | `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5` | Yes | Dynamic (voice ID) | `httpx` |

### TTS Quick Start

```python
from prompture.drivers import get_tts_driver_for_model

driver = get_tts_driver_for_model("openai/tts-1")

result = driver.synthesize("Hello, welcome to Prompture!", {
    "voice": "nova",
    "format": "mp3",
    "speed": 1.0,
})

# Save the audio
with open("output.mp3", "wb") as f:
    f.write(result["audio"])

print(result["meta"]["characters"])  # 28
print(result["meta"]["cost"])        # 0.00042
```

### TTS Streaming

Both OpenAI and ElevenLabs support streaming audio generation:

```python
driver = get_tts_driver_for_model("openai/tts-1")

for chunk in driver.synthesize_stream("A long passage of text...", {"voice": "alloy"}):
    if chunk["type"] == "delta":
        # Process incremental audio data
        play_audio_chunk(chunk["audio"])
    elif chunk["type"] == "done":
        # Final chunk with complete audio and metadata
        print(f"Total cost: ${chunk['meta']['cost']}")
```

### TTS Response Contract

**Standard response** (`synthesize`):

```python
{
    "audio": bytes,           # Raw audio bytes
    "media_type": str,        # MIME type, e.g. "audio/mpeg"
    "meta": {
        "characters": int,    # Input text length
        "cost": float,        # USD cost
        "model_name": str,    # e.g. "openai/tts-1"
        "raw_response": dict,
    },
}
```

**Stream chunks** (`synthesize_stream`):

```python
# Incremental chunks:
{"type": "delta", "audio": bytes, "media_type": str}

# Final chunk:
{"type": "done", "audio": bytes, "media_type": str, "meta": dict}
```

### TTS Options

#### OpenAI TTS

```python
driver = get_tts_driver_for_model("openai/tts-1-hd")
result = driver.synthesize("text", {
    "voice": "nova",       # alloy, echo, fable, onyx, nova, shimmer
    "format": "mp3",       # mp3, opus, aac, flac, wav, pcm
    "speed": 1.5,          # 0.25 to 4.0
})
```

#### ElevenLabs TTS

```python
driver = get_tts_driver_for_model("elevenlabs/eleven_multilingual_v2")
result = driver.synthesize("text", {
    "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel (default)
    "output_format": "mp3_44100_128",      # mp3_44100_128, pcm_16000, etc.
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.75,
    },
})
```

### TTS Pricing

| Model | Pricing |
|-------|---------|
| `tts-1` | $15 / 1M characters ($0.000015/char) |
| `tts-1-hd` | $30 / 1M characters ($0.000030/char) |
| `eleven_multilingual_v2` | ~$30 / 1M characters ($0.000030/char) |
| `eleven_turbo_v2_5` | ~$30 / 1M characters ($0.000030/char) |
| `eleven_flash_v2_5` | ~$15 / 1M characters ($0.000015/char) |

---

## Speech-to-Text (STT)

### STT Providers

| Provider | Models | Timestamps | Language Detection | SDK |
|----------|--------|:----------:|:------------------:|-----|
| **OpenAI** | `whisper-1` | Yes | Yes | `openai` |
| **ElevenLabs** | `scribe_v1` | No | Yes | `httpx` |

### STT Quick Start

```python
from prompture.drivers import get_stt_driver_for_model

driver = get_stt_driver_for_model("openai/whisper-1")

with open("recording.mp3", "rb") as f:
    audio_bytes = f.read()

result = driver.transcribe(audio_bytes, {})

print(result["text"])                          # Full transcription
print(result["language"])                      # Detected language, e.g. "en"
print(result["meta"]["duration_seconds"])       # Audio duration
print(result["meta"]["cost"])                  # USD cost

# With timestamps (OpenAI Whisper)
for segment in result["segments"]:
    print(f"[{segment['start']:.1f}s - {segment['end']:.1f}s] {segment['text']}")
```

### STT Response Contract

```python
{
    "text": str,              # Full transcribed text
    "segments": [             # Timed segments (Whisper only)
        {"start": float, "end": float, "text": str},
        ...
    ],
    "language": str | None,   # Detected language code
    "meta": {
        "duration_seconds": float,
        "cost": float,
        "model_name": str,    # e.g. "openai/whisper-1"
        "raw_response": dict,
    },
}
```

### STT Options

#### OpenAI Whisper

```python
driver = get_stt_driver_for_model("openai/whisper-1")
result = driver.transcribe(audio_bytes, {
    "language": "en",                  # Optional: hint the language
    "response_format": "verbose_json", # json, text, verbose_json, srt, vtt
    "temperature": 0.0,                # 0.0-1.0
    "filename": "meeting.mp3",         # Filename hint for format detection
})
```

#### ElevenLabs Scribe

```python
driver = get_stt_driver_for_model("elevenlabs/scribe_v1")
result = driver.transcribe(audio_bytes, {
    "language_code": "en",        # Language hint
    "tag_audio_events": True,     # Tag non-speech audio events
    "filename": "interview.mp3",
})
```

### STT Pricing

| Model | Pricing |
|-------|---------|
| `whisper-1` | $0.006/minute ($0.0001/second) |
| `scribe_v1` | TBD |

---

## Model Discovery

Prompture can auto-detect which image and audio models are available based on your configured API keys.

### Discovering Image Models

```python
from prompture.infra.discovery import get_available_image_gen_models

models = get_available_image_gen_models()
# Returns e.g.:
# [
#     "google/imagen-3.0-fast-generate-001",
#     "google/imagen-3.0-generate-002",
#     "grok/grok-2-image",
#     "openai/dall-e-2",
#     "openai/dall-e-3",
#     "stability/sd3.5-large",
#     "stability/sd3.5-large-turbo",
#     "stability/sd3.5-medium",
#     "stability/stable-image-core",
# ]
```

Discovery checks which providers have API keys configured (via `.env` or environment variables) and returns models from their `IMAGE_PRICING` dictionaries.

### Discovering Audio Models

```python
from prompture.infra.discovery import get_available_audio_models

# All audio models (STT + TTS)
all_audio = get_available_audio_models()

# Filter by modality
stt_models = get_available_audio_models(modality="stt")
# ["elevenlabs/scribe_v1", "openai/whisper-1"]

tts_models = get_available_audio_models(modality="tts")
# ["elevenlabs/eleven_flash_v2_5", "elevenlabs/eleven_multilingual_v2",
#  "elevenlabs/eleven_turbo_v2_5", "openai/tts-1", "openai/tts-1-hd"]
```

### LLM Capability Tags

For LLM models (not image/audio), the discovery system enriches results with capability metadata from the [models.dev](https://models.dev) API:

```python
from prompture.infra.discovery import get_available_models

models = get_available_models(include_capabilities=True)
# Returns enriched dicts:
# {
#     "model": "openai/gpt-4o",
#     "provider": "openai",
#     "model_id": "gpt-4o",
#     "verified": True,
#     "last_used": "2025-03-15T...",
#     "use_count": 42,
#     "capabilities": {
#         "supports_temperature": True,
#         "supports_tool_use": True,
#         "supports_structured_output": True,
#         "supports_vision": True,
#         "is_reasoning": False,
#         "context_window": 128000,
#         "max_output_tokens": 16384,
#         "modalities_input": ("text", "image"),
#         "modalities_output": ("text",),
#     },
# }
```

The `ModelCapabilities` dataclass includes these tags:

| Tag | Type | Description |
|-----|------|-------------|
| `supports_temperature` | `bool` | Whether the model accepts temperature control |
| `supports_tool_use` | `bool` | Native function/tool calling |
| `supports_structured_output` | `bool` | JSON schema-constrained output |
| `supports_vision` | `bool` | Image input support |
| `is_reasoning` | `bool` | Chain-of-thought reasoning model |
| `context_window` | `int` | Maximum input tokens |
| `max_output_tokens` | `int` | Maximum output tokens |
| `modalities_input` | `tuple[str]` | Accepted input types (text, image, audio) |
| `modalities_output` | `tuple[str]` | Produced output types |

For image/audio drivers, capabilities are exposed as class attributes on each driver:

| Driver Type | Capability Flags |
|-------------|-----------------|
| Image Gen | `supports_multiple`, `supports_size_variants`, `supported_sizes`, `max_images` |
| STT | `supports_timestamps`, `supports_language_detection` |
| TTS | `supports_streaming`, `supports_ssml`, `available_voices` |

```python
from prompture.drivers import OpenAIImageGenDriver, OpenAITTSDriver, OpenAISTTDriver

print(OpenAIImageGenDriver.supports_multiple)      # True
print(OpenAIImageGenDriver.supported_sizes)         # ["256x256", "512x512", ...]

print(OpenAISTTDriver.supports_timestamps)          # True
print(OpenAISTTDriver.supports_language_detection)  # True

print(OpenAITTSDriver.supports_streaming)           # True
print(OpenAITTSDriver.available_voices)             # ["alloy", "echo", "fable", ...]
```

---

## Media Content Types

### ImageContent

A frozen dataclass for normalized image data:

```python
from prompture.media.image import (
    ImageContent,
    image_from_bytes,
    image_from_file,
    image_from_url,
    image_from_base64,
    make_image,
)

# From raw bytes (auto-detects MIME from magic bytes: PNG, JPEG, GIF, WebP, BMP)
img = image_from_bytes(raw_bytes)

# From a file path
img = image_from_file("photo.png")

# From a URL (stores reference, does not download)
img = image_from_url("https://example.com/image.png")

# From base64 (supports data URIs)
img = image_from_base64("data:image/png;base64,iVBOR...")

# Smart constructor: auto-detects input type
img = make_image(raw_bytes)            # bytes
img = make_image("photo.png")          # file path
img = make_image("https://...")        # URL
img = make_image(Path("photo.png"))    # pathlib.Path

# Access fields
img.data          # base64-encoded string
img.media_type    # "image/png"
img.source_type   # "base64" or "url"
img.url           # URL if source_type == "url", else None
```

### AudioContent

A frozen dataclass for normalized audio data:

```python
from prompture.media.audio import (
    AudioContent,
    audio_from_bytes,
    audio_from_file,
    audio_from_url,
    audio_from_base64,
    make_audio,
)

# From raw bytes (auto-detects MIME: MP3, OGG, FLAC, WAV, M4A)
audio = audio_from_bytes(raw_bytes)

# From a file path
audio = audio_from_file("recording.mp3")

# From a URL
audio = audio_from_url("https://example.com/audio.mp3")

# Smart constructor: auto-detects input type
audio = make_audio(raw_bytes)
audio = make_audio("recording.mp3")
audio = make_audio(Path("recording.wav"))

# Access fields
audio.data              # base64-encoded string
audio.media_type        # "audio/mpeg"
audio.source_type       # "base64" or "url"
audio.url               # URL if source_type == "url", else None
audio.duration_seconds  # Duration if known, else None
```

---

## Async Support

Every driver has a full async counterpart. The API is identical, just use the async factory and `await` the calls:

```python
import asyncio
from prompture.drivers import (
    get_async_img_gen_driver_for_model,
    get_async_tts_driver_for_model,
    get_async_stt_driver_for_model,
)

async def main():
    # Async image generation
    driver = get_async_img_gen_driver_for_model("openai/dall-e-3")
    result = await driver.generate_image("a sunset over mountains", {"size": "1024x1024"})

    # Async TTS
    tts = get_async_tts_driver_for_model("openai/tts-1")
    result = await tts.synthesize("Hello world", {"voice": "nova"})

    # Async TTS streaming
    async for chunk in tts.synthesize_stream("Long text...", {"voice": "alloy"}):
        if chunk["type"] == "delta":
            process(chunk["audio"])

    # Async STT
    stt = get_async_stt_driver_for_model("openai/whisper-1")
    result = await stt.transcribe(audio_bytes, {})

asyncio.run(main())
```

**Async driver classes:**

| Sync | Async |
|------|-------|
| `OpenAIImageGenDriver` | `AsyncOpenAIImageGenDriver` |
| `GoogleImageGenDriver` | `AsyncGoogleImageGenDriver` |
| `StabilityImageGenDriver` | `AsyncStabilityImageGenDriver` |
| `GrokImageGenDriver` | `AsyncGrokImageGenDriver` |
| `OpenAITTSDriver` | `AsyncOpenAITTSDriver` |
| `ElevenLabsTTSDriver` | `AsyncElevenLabsTTSDriver` |
| `OpenAISTTDriver` | `AsyncOpenAISTTDriver` |
| `ElevenLabsSTTDriver` | `AsyncElevenLabsSTTDriver` |

---

## Registry & Plugins

All multimodal drivers use the same pluggable registry system as LLM drivers.

### Registering Custom Drivers

```python
from prompture.drivers import register_img_gen_driver, register_tts_driver, register_stt_driver

# Register a custom image gen driver
def my_img_factory(model=None):
    return MyImageDriver(model=model or "my-model")

register_img_gen_driver("my_provider", my_img_factory)

# Register a custom TTS driver
register_tts_driver("my_provider", lambda model=None: MyTTSDriver(model=model))

# Register a custom STT driver
register_stt_driver("my_provider", lambda model=None: MySTTDriver(model=model))

# Async variants
from prompture.drivers import register_async_img_gen_driver, register_async_tts_driver
register_async_img_gen_driver("my_provider", lambda model=None: MyAsyncImageDriver(model=model))
```

### Entry Point Plugins

Third-party packages can register drivers via Python entry points in `pyproject.toml`:

```toml
[project.entry-points."prompture.img_gen_drivers"]
my_provider = "my_package.drivers:my_img_gen_factory"

[project.entry-points."prompture.async_img_gen_drivers"]
my_provider = "my_package.drivers:my_async_img_gen_factory"

[project.entry-points."prompture.stt_drivers"]
my_provider = "my_package.drivers:my_stt_factory"

[project.entry-points."prompture.async_stt_drivers"]
my_provider = "my_package.drivers:my_async_stt_factory"

[project.entry-points."prompture.tts_drivers"]
my_provider = "my_package.drivers:my_tts_factory"

[project.entry-points."prompture.async_tts_drivers"]
my_provider = "my_package.drivers:my_async_tts_factory"
```

### Listing Registered Drivers

```python
from prompture.drivers import (
    list_registered_img_gen_drivers,
    list_registered_stt_drivers,
    list_registered_tts_drivers,
    is_img_gen_driver_registered,
    is_stt_driver_registered,
    is_tts_driver_registered,
)

print(list_registered_img_gen_drivers())  # ["google", "grok", "openai", "stability"]
print(list_registered_stt_drivers())      # ["elevenlabs", "openai"]
print(list_registered_tts_drivers())      # ["elevenlabs", "openai"]

print(is_img_gen_driver_registered("openai"))  # True
```

---

## Callbacks & Observability

All multimodal drivers support the same `DriverCallbacks` hook system as LLM drivers. Use `*_with_hooks()` methods for automatic callback firing:

```python
from prompture.infra.callbacks import DriverCallbacks
from prompture.drivers import get_img_gen_driver_for_model

def on_request(payload):
    print(f"Generating image: {payload['options']}")

def on_response(payload):
    print(f"Generated {payload['image_count']} images in {payload['elapsed_ms']:.0f}ms")

def on_error(payload):
    print(f"Error: {payload['error']}")

driver = get_img_gen_driver_for_model("openai/dall-e-3")
driver.callbacks = DriverCallbacks(
    on_request=on_request,
    on_response=on_response,
    on_error=on_error,
)

# Use the *_with_hooks variant to fire callbacks automatically
result = driver.generate_image_with_hooks("a mountain landscape", {"size": "1024x1024"})
```

Similarly for audio:
- `stt_driver.transcribe_with_hooks(audio, options)`
- `tts_driver.synthesize_with_hooks(text, options)`

---

## Configuration

Set API keys via environment variables or a `.env` file:

```env
# Image Generation
OPENAI_API_KEY=sk-...              # OpenAI DALL-E (shared with LLM/audio)
GOOGLE_API_KEY=AI...               # Google Imagen (shared with LLM)
STABILITY_API_KEY=sk-...           # Stability AI
STABILITY_ENDPOINT=                # Optional custom endpoint
GROK_API_KEY=xai-...               # Grok/xAI Aurora (shared with LLM)

# Audio (TTS / STT)
OPENAI_API_KEY=sk-...              # OpenAI Whisper & TTS (shared)
ELEVENLABS_API_KEY=...             # ElevenLabs STT & TTS
ELEVENLABS_ENDPOINT=               # Optional (default: https://api.elevenlabs.io/v1)
```

Settings are managed by the `Settings` class in `prompture/infra/settings.py` and loaded automatically from `.env`.

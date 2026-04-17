from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from models.video_production import VideoFormat, VideoResolution


class BackgroundImage(BaseModel):
    path: Path = Field(..., description="Local path to the saved PNG file")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    style_key: str = Field(..., description="Meditation style key used for this image")
    backend_used: str = Field(..., description="Backend that generated this image: 'google' or 'runpod'")


@runtime_checkable
class ImageBackend(Protocol):
    async def generate(self, prompt: str, video_format: VideoFormat, seed: int) -> Path:
        """Generate image and return local path to saved PNG."""
        ...


class GeminiImageBackend:
    """Google Gemini image generation backend (Nano Banana 2 / Pro)."""

    NANO_MODEL = "gemini-3.1-flash-image-preview"
    PRO_MODEL = "gemini-3-pro-image-preview"

    def __init__(self, quality: str = "nano", cache_dir: Path = None) -> None:
        api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GOOGLE_GENERATIVE_AI_API_KEY is required for the Google image backend"
            )
        from google import genai as google_genai
        self._client = google_genai.Client(api_key=api_key)
        self._model = self.PRO_MODEL if quality == "pro" else self.NANO_MODEL
        self._cache_dir = cache_dir or Path("image_cache")

    async def generate(self, prompt: str, video_format: VideoFormat, seed: int) -> Path:
        resolution = VideoResolution.from_format(video_format)
        size_prompt = f"Create a {resolution.width}x{resolution.height} pixel image. {prompt}"

        response = self._client.models.generate_content(
            model=self._model,
            contents=[size_prompt],
        )

        output_path = self._cache_dir / f"gemini_{abs(seed)}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for part in response.parts:
            if hasattr(part, "inline_data") and part.inline_data is not None:
                image = part.as_image()
                image.save(str(output_path))
                return output_path

        raise RuntimeError("Gemini returned no image data in response parts")


class RunpodImageBackend:
    """Z-Image Turbo backend via RunPod API."""

    ENDPOINT = "https://api.runpod.ai/v2/z-image-turbo/runsync"

    # VideoFormat → RunPod size string
    SIZE_MAP = {
        VideoFormat.LONG_FORM: "1280*720",
        VideoFormat.SHORTS: "720*1280",
    }

    def __init__(self, cache_dir: Path = None) -> None:
        self._api_key = os.environ.get("RUNPOD_API_KEY")
        if not self._api_key:
            raise EnvironmentError("RUNPOD_API_KEY is required for the RunPod image backend")
        self._cache_dir = cache_dir or Path("image_cache")

    async def generate(self, prompt: str, video_format: VideoFormat, seed: int) -> Path:
        import requests as req
        size = self.SIZE_MAP.get(video_format, "1024*1024")
        payload = {
            "input": {
                "prompt": prompt,
                "size": size,
                "seed": seed if seed >= 0 else -1,
                "output_format": "png",
                "enable_safety_checker": True,
            }
        }
        resp = req.post(
            self.ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "COMPLETED":
            raise RuntimeError(f"RunPod generation failed: {data}")

        image_url = data["output"]["image_url"]

        # Download immediately — URL expires in 7 days
        img_resp = req.get(image_url, timeout=60)
        img_resp.raise_for_status()

        output_path = self._cache_dir / f"runpod_{abs(seed)}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_resp.content)
        return output_path


class BackgroundImageGeneratorConfig(BaseModel):
    image_backend: Literal["google", "runpod"] = Field(default="google", description="Image generation backend")
    image_quality: Literal["nano", "pro"] = Field(default="nano", description="Quality tier for Gemini backend")
    storage_path: Path = Field(..., description="Root storage path; image cache goes in storage_path/image_cache/")


class BackgroundImageGenerator:
    def __init__(self, config: BackgroundImageGeneratorConfig) -> None:
        cache_dir = config.storage_path / "image_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = cache_dir

        if config.image_backend == "google":
            self._backend: ImageBackend = GeminiImageBackend(
                quality=config.image_quality, cache_dir=cache_dir
            )
            self._backend_name = "google"
        else:
            self._backend = RunpodImageBackend(cache_dir=cache_dir)
            self._backend_name = "runpod"

    def _cache_key(self, prompt: str, video_format: VideoFormat, seed: int) -> str:
        """SHA-256 hash of (prompt, video_format, seed) → filename stem."""
        raw = f"{prompt}|{video_format.value}|{seed}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _build_prompt(self, style_key: str, video_format: VideoFormat) -> str:
        from models.meditation_script import STYLE_REGISTRY
        style = STYLE_REGISTRY.get(style_key)
        if not style:
            raise ValueError(f"Unknown style_key: {style_key!r}")
        fmt_label = "landscape (16:9)" if video_format == VideoFormat.LONG_FORM else "portrait (9:16)"
        return f"{style.image_prompt_template}, {fmt_label} composition, high quality"

    async def generate(
        self,
        style_key: str,
        video_format: VideoFormat,
        seed: int = -1,
        custom_prompt: Optional[str] = None,
    ) -> BackgroundImage:
        prompt = custom_prompt.strip() if custom_prompt else self._build_prompt(style_key, video_format)
        # Cache key includes the prompt so custom prompts get their own cached entry
        cache_key = self._cache_key(prompt, video_format, seed)
        cached_path = self._cache_dir / f"{cache_key}.png"

        if cached_path.exists():
            from PIL import Image as PILImage
            with PILImage.open(cached_path) as img:
                w, h = img.size
            return BackgroundImage(
                path=cached_path,
                width=w,
                height=h,
                style_key=style_key,
                backend_used=f"{self._backend_name}(cached)",
            )

        # Pass seed to backend; backend saves to its own temp name — we rename to cache key
        raw_path = await self._backend.generate(prompt, video_format, seed)

        # Move/rename to canonical cache path
        if raw_path != cached_path:
            raw_path.rename(cached_path)

        resolution = VideoResolution.from_format(video_format)
        return BackgroundImage(
            path=cached_path,
            width=resolution.width,
            height=resolution.height,
            style_key=style_key,
            backend_used=self._backend_name,
        )

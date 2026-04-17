"""Video production models for the meditation video pipeline."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from datatypes.transcript import Transcript


class VideoFormat(str, Enum):
    LONG_FORM = "long_form"  # 16:9 YouTube long-form
    SHORTS = "shorts"        # 9:16 YouTube Shorts


class VideoResolution(BaseModel):
    width: int
    height: int

    @classmethod
    def from_format(cls, fmt: VideoFormat) -> "VideoResolution":
        if fmt == VideoFormat.LONG_FORM:
            return cls(width=1920, height=1080)
        return cls(width=1080, height=1920)


class VideoCompositionConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio_path: Path = Field(..., description="Path to the stitched audio file")
    image_path: Path = Field(..., description="Path to the background image (PNG)")
    output_path: Path = Field(..., description="Where to write the output MP4")
    video_format: VideoFormat = Field(..., description="Target video format")
    transcript: Optional[Any] = Field(
        None,
        description="ElevenLabs word-level transcript for karaoke (Transcript instance)",
    )
    script_segments: Optional[list[tuple[Path, Optional[int]]]] = Field(
        None,
        description="List of (audio_segment_path, pause_after_seconds) for stitching",
    )
    enable_karaoke: bool = Field(False, description="Burn karaoke subtitles from word-level transcript")
    fade_in_seconds: float = Field(2.0, description="Duration of fade-in effect in seconds")
    fade_out_seconds: float = Field(2.0, description="Duration of fade-out effect in seconds")
    title_card_text: Optional[str] = Field(None, description="Text to display on the opening title card")
    title_card_duration_seconds: float = Field(5.0, description="Duration of the title card in seconds")
    title_card_font_size: int = Field(64, description="Font size for the title card text")
    title_card_color: str = Field("white", description="Font color for the title card text")


class VideoProductionResult(BaseModel):
    output_path: Path = Field(..., description="Path to the produced MP4 file")
    duration_seconds: float = Field(..., description="Total duration of the video in seconds")
    file_size_bytes: int = Field(..., description="File size of the output MP4 in bytes")
    video_format: VideoFormat = Field(..., description="Video format of the produced file")
    resolution: VideoResolution = Field(..., description="Resolution of the produced video")
    processing_time_seconds: float = Field(..., description="Wall-clock time taken to compose the video in seconds")


class VideoProductionItem(BaseModel):
    title: str = Field(..., description="Title of the meditation video")
    custom_instructions: Optional[str] = Field(
        None,
        description="Additional LLM instructions for this specific item",
    )
    notion_record_id: Optional[str] = Field(
        None,
        description="Notion record ID, populated after auto-creation",
    )


class VideoProductionBatchRequest(BaseModel):
    items: list[VideoProductionItem] = Field(
        ...,
        description="List of videos to produce in this batch",
    )
    voice_id: Optional[str] = Field(
        None,
        description="Override voice ID for all items; defaults to AudioProcessorConfig.default_voice_id if None",
    )
    style_key: str = Field(..., description="Meditation style key from STYLE_REGISTRY")
    duration_key: str = Field(..., description="Duration key from DURATION_REGISTRY")
    video_format: VideoFormat = Field(
        default=VideoFormat.LONG_FORM,
        description="Target video format",
    )
    image_backend: Optional[str] = Field(
        None,
        description="Image backend override: 'google' or 'runpod'",
    )
    image_quality: Optional[str] = Field(
        None,
        description="Image quality override: 'nano' or 'pro'",
    )
    produce_shorts: bool = Field(
        default=False,
        description="Also produce a 9:16 Shorts version for each item",
    )
    enable_karaoke: bool = Field(
        default=False,
        description="Burn karaoke subtitles from word-level transcript",
    )


class VideoCompositionError(Exception):
    """Raised when FFmpeg video composition fails."""
    pass

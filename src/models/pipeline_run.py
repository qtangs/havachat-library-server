from __future__ import annotations
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from models.meditation_script import MeditationScript
from models.video_production import VideoProductionBatchRequest


class PipelineStage(str, Enum):
    IDLE = "idle"
    SCRIPT = "script"
    AWAITING_SCRIPT_APPROVAL = "awaiting_script_approval"
    AUDIO = "audio"
    AWAITING_AUDIO_APPROVAL = "awaiting_audio_approval"
    IMAGE_PROMPT = "image_prompt"
    AWAITING_IMAGE_PROMPT_APPROVAL = "awaiting_image_prompt_approval"
    IMAGE = "image"
    AWAITING_IMAGE_APPROVAL = "awaiting_image_approval"
    VIDEO = "video"
    COMPLETE = "complete"
    FAILED = "failed"


class YoutubeMetadata(BaseModel):
    title: str = Field(..., description="YouTube video title")
    description: str = Field(..., description="YouTube video description")
    tags: list[str] = Field(default_factory=list, description="YouTube tags")


class PipelineRun(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this pipeline run")
    config: VideoProductionBatchRequest = Field(..., description="Batch request configuration")
    stage: PipelineStage = Field(default=PipelineStage.IDLE, description="Current pipeline stage")
    script: Optional[MeditationScript] = Field(None, description="Generated meditation script")
    audio_path: Optional[Path] = Field(None, description="Path to the generated/stitched audio file")
    transcript: Optional[dict] = Field(None, description="Word-level transcript from TTS with timestamps (serialised pydantic-v1 dict)")
    image_prompt: Optional[str] = Field(None, description="Image generation prompt (editable by user)")
    image_path: Optional[Path] = Field(None, description="Path to the generated background image")
    video_path: Optional[Path] = Field(None, description="Path to the composed video file")
    shorts_path: Optional[Path] = Field(None, description="Path to the Shorts variant video, if produced")
    youtube_metadata: Optional[YoutubeMetadata] = Field(None, description="Generated YouTube title/description/tags")
    error: Optional[str] = Field(None, description="Error message if stage is FAILED")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this run was created")


class PipelineStore:
    """Thread-safe in-memory store for PipelineRun objects, with optional file-based persistence."""

    def __init__(self) -> None:
        self._runs: dict[UUID, PipelineRun] = {}
        self._lock = threading.Lock()
        self._persist_dir: Optional[Path] = None

    def configure_persistence(self, base_path: Path) -> None:
        """Point the store at a directory and load any previously saved runs."""
        self._persist_dir = base_path / "pipeline_runs"
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        for run_file in sorted(self._persist_dir.glob("*/run.json")):
            try:
                run = PipelineRun.model_validate_json(run_file.read_text())
                with self._lock:
                    self._runs[run.run_id] = run
            except Exception:
                pass  # ignore corrupted / incompatible files

    def get(self, run_id: UUID) -> Optional[PipelineRun]:
        with self._lock:
            return self._runs.get(run_id)

    def set(self, run: PipelineRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run
        if self._persist_dir is not None:
            run_dir = self._persist_dir / str(run.run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(run.model_dump_json())

    def all(self) -> list[PipelineRun]:
        with self._lock:
            return list(self._runs.values())


pipeline_store = PipelineStore()


class PipelineStageEvent(BaseModel):
    run_id: str = Field(..., description="UUID of the pipeline run as a string")
    stage: str = Field(..., description="Current stage name")
    status: Literal["running", "awaiting_approval", "complete", "failed"] = Field(..., description="Stage status")
    message: Optional[str] = Field(None, description="Optional human-readable message")

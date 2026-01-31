"""Audio metadata models for tracking generated audio files."""

from datetime import UTC, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AudioVersion(BaseModel):
    """Single version of generated audio."""
    
    version: int = Field(..., description="Version number (1, 2, 3)")
    audio_local_path: str = Field(..., description="Local file path relative to language/level")
    audio_url: Optional[str] = Field(None, description="Cloudflare R2 URL after sync")
    format: str = Field(..., description="Audio format: opus or mp3")
    sample_rate: int = Field(..., description="Sample rate in Hz")
    bitrate: int = Field(..., description="Bitrate in kbps")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    duration_ms: Optional[int] = Field(None, description="Audio duration in milliseconds")
    voice_id: str = Field(..., description="ElevenLabs voice ID used")
    character_count: int = Field(..., description="Number of characters synthesized")
    selected: bool = Field(default=False, description="True if this is the selected version")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningItemAudio(BaseModel):
    """Audio metadata for a learning item."""
    
    learning_item_id: str = Field(..., description="UUID of the learning item")
    target_item: str = Field(..., description="The word/phrase for reference")
    category: str = Field(..., description="Learning item category")
    versions: List[AudioVersion] = Field(
        default_factory=list,
        description="List of generated audio versions (1-3)"
    )
    
    def get_selected_version(self) -> AudioVersion | None:
        """Get the selected audio version."""
        for version in self.versions:
            if version.selected:
                return version
        return None
    
    def select_version(self, version_number: int) -> bool:
        """Mark a version as selected and unselect others.
        
        Returns:
            True if version was found and selected, False otherwise
        """
        found = False
        for ver in self.versions:
            if ver.version == version_number:
                ver.selected = True
                found = True
            else:
                ver.selected = False
        return found


class SegmentAudio(BaseModel):
    """Audio metadata for a content unit segment."""
    
    segment_index: int = Field(..., description="Index of segment in content unit")
    speaker_id: Optional[str] = Field(None, description="Speaker ID (A, B, C) for dialogues")
    text: str = Field(..., description="Text of the segment for reference")
    versions: List[AudioVersion] = Field(
        default_factory=list,
        description="List of generated audio versions (1-3)"
    )
    
    def get_selected_version(self) -> AudioVersion | None:
        """Get the selected audio version."""
        for version in self.versions:
            if version.selected:
                return version
        return None
    
    def select_version(self, version_number: int) -> bool:
        """Mark a version as selected and unselect others."""
        found = False
        for ver in self.versions:
            if ver.version == version_number:
                ver.selected = True
                found = True
            else:
                ver.selected = False
        return found


class ContentUnitAudio(BaseModel):
    """Audio metadata for a content unit (conversation or story)."""
    
    content_unit_id: str = Field(..., description="UUID of the content unit")
    title: str = Field(..., description="Content title for reference")
    type: str = Field(..., description="conversation or story")
    segments: List[SegmentAudio] = Field(
        default_factory=list,
        description="Audio metadata for each segment"
    )
    
    def get_segment_audio(self, segment_index: int) -> SegmentAudio | None:
        """Get audio metadata for a specific segment."""
        for seg in self.segments:
            if seg.segment_index == segment_index:
                return seg
        return None

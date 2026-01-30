"""Voice configuration models for ElevenLabs TTS."""

from typing import List, Literal
from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    """Voice configuration for ElevenLabs TTS.
    
    Type format:
    - "single": General purpose voice for learning items
    - "conversation": Voice for conversations (gender-specific)
    
    Examples:
    - type="single", gender="male"
    - type="conversation", gender="female"
    """
    
    voice_id: str = Field(..., description="Provider/Voice ID (e.g., 'elevenlabs/abc123')")
    name: str = Field(..., description="Human-readable voice name")
    type: Literal["single", "conversation"] = Field(
        ...,
        description="Voice type: 'single' for learning items or 'conversation' for conversations"
    )
    gender: Literal["male", "female"] = Field(
        ...,
        description="Voice gender: 'male' or 'female'"
    )
    description: str = Field(..., description="Description of voice characteristics")
    supported_languages: List[str] = Field(
        ..., description="List of ISO 639-1 language codes this voice supports"
    )
    comment: str = Field(default="", description="Additional notes about voice usage")
    
    def is_conversation_voice(self) -> bool:
        """Check if this is a conversation voice."""
        return self.type == "conversation"


class VoiceConfigCollection(BaseModel):
    """Collection of voice configurations."""
    
    voices: List[VoiceConfig] = Field(..., description="List of voice configurations")
    
    def get_voice_by_id(self, voice_id: str) -> VoiceConfig | None:
        """Get voice configuration by voice ID."""
        for voice in self.voices:
            if voice.voice_id == voice_id:
                return voice
        return None
    
    def get_voices_for_language(self, language: str) -> List[VoiceConfig]:
        """Get all voices that support a specific language."""
        return [v for v in self.voices if language in v.supported_languages]
    
    def get_single_voices(self, language: str | None = None, gender: str | None = None) -> List[VoiceConfig]:
        """Get all single-type voices, optionally filtered by language and gender."""
        voices = [v for v in self.voices if v.type == "single"]
        if language:
            voices = [v for v in voices if language in v.supported_languages]
        if gender:
            voices = [v for v in voices if v.gender == gender]
        return voices
    
    def get_conversation_voices(
        self,
        language: str | None = None,
        gender: str | None = None
    ) -> List[VoiceConfig]:
        """Get conversation voices, optionally filtered by language and gender.
        
        Args:
            language: ISO 639-1 language code filter
            gender: Gender filter ('male' or 'female')
            
        Returns:
            List of VoiceConfig objects matching the criteria
        """
        voices = [v for v in self.voices if v.is_conversation_voice()]
        if language:
            voices = [v for v in voices if language in v.supported_languages]
        if gender:
            voices = [v for v in voices if v.gender == gender]
        return voices

"""Voice configuration validation logic."""

import json
import random
from pathlib import Path
from typing import Dict, List

from src.pipeline.models.voice_config import VoiceConfig, VoiceConfigCollection


class VoiceConfigValidator:
    """Validator for voice configurations."""
    
    def __init__(self, language_code: str, config_dir: str | Path | None = None):
        """Initialize validator with language-specific voice config.
        
        Args:
            language_code: ISO 639-1 language code (e.g., 'zh', 'ja', 'fr')
            config_dir: Directory containing voice_config_{lang}.json files (defaults to repo root)
        """
        self.language_code = language_code
        self.config_dir = Path(config_dir) if config_dir else Path.cwd()
        self.config_path = self.config_dir / f"voice_config_{language_code}.json"
        self.config: VoiceConfigCollection | None = None
        self._load_config()
    
    def _load_config(self):
        """Load voice configuration from language-specific JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Voice config file not found: {self.config_path}. "
                f"Expected voice_config_{self.language_code}.json in {self.config_dir}"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.config = VoiceConfigCollection(**data)
    
    def validate_voice_config(self, voice_id: str) -> tuple[bool, str]:
        """Validate that a voice ID exists and supports the target language.
        
        Args:
            voice_id: Provider/Voice ID (e.g., 'elevenlabs/abc123')
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.config:
            return False, "Voice configuration not loaded"
        
        voice = self.config.get_voice_by_id(voice_id)
        if not voice:
            return False, f"Voice ID '{voice_id}' not found in configuration"
        
        if self.language_code not in voice.supported_languages:
            return False, (
                f"Voice '{voice.name}' ({voice_id}) does not support language '{self.language_code}'. "
                f"Supported languages: {', '.join(voice.supported_languages)}"
            )
        
        return True, ""
    
    def validate_conversation_config(
        self,
        speaker_genders: List[str]
    ) -> tuple[bool, str]:
        """Validate that conversation voices exist for the required genders.
        
        Args:
            speaker_genders: List of genders for each speaker ('male' or 'female')
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.config:
            return False, "Voice configuration not loaded"
        
        # Check that we have conversation voices for each required gender
        for i, gender in enumerate(speaker_genders):
            voices = self.config.get_conversation_voices(self.language_code, gender)
            if not voices:
                return False, (
                    f"No conversation voices found for gender '{gender}' "
                    f"in language '{self.language_code}'"
                )
        
        return True, ""
    
    def get_single_voice_for_language(self, gender: str | None = None) -> VoiceConfig | None:
        """Get a default single voice for the language.
        
        Args:
            gender: Optional gender filter ('male' or 'female')
            
        Returns:
            First available single voice, or None
        """
        if not self.config:
            return None
        
        voices = self.config.get_single_voices(self.language_code, gender)
        return voices[0] if voices else None
    
    def get_conversation_voices_for_speakers(
        self,
        speaker_genders: List[str]
    ) -> Dict[str, str]:
        """Get conversation voice mapping for speakers with specified genders.
        
        Randomly selects conversation voices matching each speaker's gender.
        
        Args:
            speaker_genders: List of genders for each speaker (e.g., ['female', 'male'])
            
        Returns:
            Dict mapping speaker ID (A, B, C, ...) to voice_id
        """
        if not self.config:
            return {}
        
        voice_mapping = {}
        speaker_ids = [chr(65 + i) for i in range(len(speaker_genders))]  # A, B, C, ...
        
        for speaker_id, gender in zip(speaker_ids, speaker_genders):
            # Get all conversation voices for this gender
            voices = self.config.get_conversation_voices(self.language_code, gender)
            if voices:
                # Randomly select one
                selected_voice = random.choice(voices)
                voice_mapping[speaker_id] = selected_voice.voice_id
        
        return voice_mapping
    
    def get_all_languages(self) -> List[str]:
        """Get all supported languages from voice configurations."""
        if not self.config:
            return []
        
        languages = set()
        for voice in self.config.voices:
            languages.update(voice.supported_languages)
        
        return sorted(list(languages))


def validate_voice_config(voice_id: str, language_code: str, config_dir: str | Path | None = None) -> tuple[bool, str]:
    """Convenience function to validate a single voice configuration.
    
    Args:
        voice_id: Provider/Voice ID (e.g., 'elevenlabs/abc123')
        language_code: ISO 639-1 language code
        config_dir: Directory containing voice config files (defaults to repo root)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = VoiceConfigValidator(language_code, config_dir)
    return validator.validate_voice_config(voice_id)


def validate_conversation_config(
    speaker_genders: List[str],
    language_code: str,
    config_dir: str | Path | None = None
) -> tuple[bool, str]:
    """Convenience function to validate conversation voice configuration.
    
    Args:
        speaker_genders: List of genders for each speaker (e.g., ['female', 'male'])
        language_code: ISO 639-1 language code
        config_dir: Directory containing voice config files (defaults to repo root)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = VoiceConfigValidator(language_code, config_dir)
    return validator.validate_conversation_config(speaker_genders)

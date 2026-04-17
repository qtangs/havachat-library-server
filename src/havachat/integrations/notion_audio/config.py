"""
Configuration Loader for Notion Audio Content Processor

Loads and validates environment variables for the processor.
"""

from src.models.notion_audio import AudioProcessorConfig


def load_config_from_env() -> AudioProcessorConfig:
    """
    Load configuration from environment variables.
    
    Required environment variables:
    - NOTION_API_KEY: Notion integration token
    - NOTION_AUDIO_DATABASE_ID: Audio Content database ID (default: 302dd30aa93a8087be8dda41b3b4de9b)
    - NOTION_VOICE_DATABASE_ID: Voice configuration database ID
    - HAVACHAT_KNOWLEDGE_PATH: Root storage path for audio files
    - ELEVENLABS_API_KEY: ElevenLabs API key
    - DEFAULT_VOICE_ID: Default voice ID for fallback
    - OPENAI_API_KEY or ANTHROPIC_API_KEY: LLM API key
    
    Optional environment variables:
    - TTS_MODEL: ElevenLabs model (default: eleven_multilingual_v2)
    - AUDIO_FORMAT: Audio format (default: mp3_44100_192)
    - LLM_MODEL: LLM model (default: gpt-4o-mini)
    
    Returns:
        AudioProcessorConfig instance with validated settings
    
    Raises:
        ValidationError: If required variables are missing or invalid
    """
    return AudioProcessorConfig.from_env()

"""
Notion Audio Content Processor

Processes Notion Audio Database records marked "Ready for Audio",
generates high-quality audio files with timestamps using ElevenLabs TTS,
and creates AI-powered metadata (descriptions and hashtags).

Main components:
- AudioProcessor: Batch processing engine (✅ Implemented)
- VoiceResolver: Voice selection from Notion Voice Database (✅ Implemented)
- MetadataGenerator: AI-powered metadata creation (🔜 Coming in US2)
"""

from src.havachat.integrations.notion_audio.processor import AudioProcessor
from src.havachat.integrations.notion_audio.voice_resolver import VoiceResolver

# Imports will be enabled as components are implemented:
# from src.havachat.integrations.notion_audio.metadata_generator import MetadataGenerator

__all__ = ["AudioProcessor", "VoiceResolver"]

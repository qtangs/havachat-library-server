"""ElevenLabs TTS client with retry logic and cost tracking."""

import logging
import os
import time
from pathlib import Path
from typing import Literal

from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class ElevenLabsClient:
    """Client for ElevenLabs Text-to-Speech API with retry logic."""
    
    # Audio format configurations
    FORMATS = {
        "opus": {
            "format_string": "opus_48000_32",
            "sample_rate": 48000,
            "bitrate": 32,
            "extension": "opus"
        },
        "mp3": {
            "format_string": "mp3_44100_128",
            "sample_rate": 44100,
            "bitrate": 64,
            "extension": "mp3"
        }
    }
    
    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize ElevenLabs client.
        
        Args:
            api_key: ElevenLabs API key (or uses ELEVENLABS_API_KEY env var)
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds (exponential backoff)
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key required (ELEVENLABS_API_KEY env var or api_key param)")
        
        self.client = ElevenLabs(api_key=self.api_key)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Cost tracking
        self.total_characters = 0
        self.total_requests = 0
        self.failed_requests = 0
    
    def text_to_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str | Path,
        audio_format: Literal["opus", "mp3"] = "opus",
        model_id: str = "eleven_multilingual_v2"
    ) -> tuple[bool, dict]:
        """Generate speech from text using ElevenLabs API.
        
        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            output_path: Path to save the audio file
            audio_format: Audio format (opus or mp3)
            model_id: ElevenLabs model ID
            
        Returns:
            Tuple of (success, metadata_dict)
            metadata includes: character_count, duration_ms, file_size_bytes, latency_ms
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        format_config = self.FORMATS.get(audio_format, self.FORMATS["opus"])
        character_count = len(text)
        
        metadata = {
            "character_count": character_count,
            "voice_id": voice_id,
            "format": audio_format,
            "sample_rate": format_config["sample_rate"],
            "bitrate": format_config["bitrate"],
            "attempts": 0,
            "latency_ms": 0,
            "file_size_bytes": 0,
            "duration_ms": None
        }
        
        for attempt in range(self.max_retries):
            metadata["attempts"] = attempt + 1
            
            try:
                start_time = time.time()
                
                logger.info(
                    f"Generating audio (attempt {attempt + 1}/{self.max_retries}): "
                    f"{character_count} chars, voice={voice_id[:8]}..."
                )
                
                # Extract just the voice ID (remove "elevenlabs/" prefix if present)
                clean_voice_id = voice_id.split('/')[-1] if '/' in voice_id else voice_id
                
                # Generate audio using the current API (returns a generator)
                audio_generator = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=clean_voice_id,
                    model_id=model_id,
                    output_format=format_config["format_string"]
                )
                
                # Convert generator to bytes
                audio_bytes = b"".join(audio_generator)
                
                # Save to file
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)
                
                latency_ms = int((time.time() - start_time) * 1000)
                file_size = output_path.stat().st_size
                
                metadata["latency_ms"] = latency_ms
                metadata["file_size_bytes"] = file_size
                
                # Update statistics
                self.total_characters += character_count
                self.total_requests += 1
                
                logger.info(
                    f"✓ Audio generated successfully: {file_size} bytes, {latency_ms}ms"
                )
                
                return True, metadata
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Audio generation failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}"
                )
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    self.failed_requests += 1
                    logger.error(
                        f"✗ Audio generation failed after {self.max_retries} attempts: {error_msg}"
                    )
                    metadata["error"] = error_msg
                    return False, metadata
        
        return False, metadata
    
    def text_to_dialogue(
        self,
        dialogue_inputs: list[dict[str, str]],
        voice_mapping: dict[str, str],
        output_path: str | Path,
        audio_format: Literal["opus", "mp3"] = "opus",
        model_id: str = "eleven_v3"
    ) -> tuple[bool, dict]:
        """Generate dialogue from text-speaker pairs using ElevenLabs Text-to-Dialogue API.
        
        Args:
            dialogue_inputs: List of dicts with 'text' and 'speaker' keys (speaker is A/B/C/...)
            voice_mapping: Dict mapping speaker IDs to voice IDs (e.g., {'A': 'voice_123', 'B': 'voice_456'})
            output_path: Path to save the audio file
            audio_format: Audio format (opus or mp3)
            model_id: ElevenLabs model ID
            
        Returns:
            Tuple of (success, metadata_dict)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        format_config = self.FORMATS.get(audio_format, self.FORMATS["opus"])
        total_character_count = sum(len(inp["text"]) for inp in dialogue_inputs)
        
        metadata = {
            "character_count": total_character_count,
            "format": audio_format,
            "sample_rate": format_config["sample_rate"],
            "bitrate": format_config["bitrate"],
            "attempts": 0,
            "latency_ms": 0,
            "file_size_bytes": 0,
            "duration_ms": None,
            "num_speakers": len(voice_mapping)
        }
        
        # Map speakers to voice IDs and clean voice IDs (remove provider prefix)
        cleaned_inputs = [
            {
                "text": inp["text"],
                "voice_id": voice_mapping[inp["speaker"]].split('/')[-1] 
                            if '/' in voice_mapping[inp["speaker"]] 
                            else voice_mapping[inp["speaker"]]
            }
            for inp in dialogue_inputs
        ]
        
        for attempt in range(self.max_retries):
            metadata["attempts"] = attempt + 1
            
            try:
                start_time = time.time()
                
                logger.info(
                    f"Generating dialogue (attempt {attempt + 1}/{self.max_retries}): "
                    f"{len(dialogue_inputs)} segments, {total_character_count} chars total"
                )
                
                # Generate dialogue using the current API
                audio_generator = self.client.text_to_dialogue.convert(
                    inputs=cleaned_inputs,
                    model_id=model_id,
                    output_format=format_config["format_string"]
                )
                
                # Convert generator to bytes
                audio_bytes = b"".join(audio_generator)
                
                # Save to file
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)
                
                latency_ms = int((time.time() - start_time) * 1000)
                file_size = output_path.stat().st_size
                
                # Calculate audio duration
                try:
                    audio = AudioSegment.from_file(output_path, format=audio_format)
                    duration_ms = len(audio)  # pydub returns duration in milliseconds
                    metadata["duration_ms"] = duration_ms
                except Exception as e:
                    logger.warning(f"Could not determine audio duration: {e}")
                    metadata["duration_ms"] = None
                
                metadata["latency_ms"] = latency_ms
                metadata["file_size_bytes"] = file_size
                
                # Update statistics
                self.total_characters += total_character_count
                self.total_requests += 1
                
                logger.info(
                    f"✓ Dialogue generated successfully: {file_size} bytes, {latency_ms}ms"
                )
                
                return True, metadata
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Dialogue generation failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}"
                )
                
                # Check if we should retry
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    self.failed_requests += 1
                    logger.error(
                        f"✗ Dialogue generation failed after {self.max_retries} attempts: {error_msg}"
                    )
                    metadata["error"] = error_msg
                    return False, metadata
        
        return False, metadata
    
    def get_cost_estimate(self, character_count: int | None = None) -> dict:
        """Get cost estimate for character usage.
        
        Args:
            character_count: Optional character count to estimate, or uses total tracked
            
        Returns:
            Dict with cost information (assumes $0.30 per 1000 characters)
        """
        chars = character_count or self.total_characters
        cost_per_1k = 0.30  # ElevenLabs pricing (approximate)
        estimated_cost = (chars / 1000) * cost_per_1k
        
        return {
            "character_count": chars,
            "cost_per_1000_chars": cost_per_1k,
            "estimated_cost_usd": round(estimated_cost, 2),
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            )
        }
    
    def reset_statistics(self):
        """Reset cost tracking statistics."""
        self.total_characters = 0
        self.total_requests = 0
        self.failed_requests = 0

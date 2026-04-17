"""
Audio processing API routes

Endpoints for TTS, transcription, and other audio operations.
"""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.utils import verify_api_key
from libs.logging_helper import logger
from tools.audio.tts_with_elevenlabs import text_to_speech_with_timestamps

router = APIRouter()


class TTSRequest(BaseModel):
    """Request model for TTS with timestamps."""
    
    text: str = Field(..., description="Text to convert to speech", min_length=1)
    voice_id: str = Field(..., description="ElevenLabs voice ID")
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'fr', 'ja')")
    model_id: str = Field("eleven_multilingual_v2", description="ElevenLabs model ID")
    output_format: str = Field("mp3_44100_128", description="Audio output format")
    optimize_streaming_latency: int = Field(0, ge=0, le=4, description="Latency optimization (0-4)")
    return_audio: bool = Field(True, description="Whether to return base64 audio in response")


class TranscriptWord(BaseModel):
    """Word-level timing information."""
    
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    word: str = Field(description="The word text")
    score: Optional[float] = Field(None, description="Confidence score (if available)")


class TranscriptSegment(BaseModel):
    """Sentence-level segment with timing."""
    
    start: float = Field(description="Start time of segment")
    end: float = Field(description="End time of segment")
    text: str = Field(description="Segment text")
    words: list[TranscriptWord] = Field(description="Words in this segment")


class TranscriptResponse(BaseModel):
    """Response model for transcript data."""
    
    segments: list[TranscriptSegment] = Field(description="List of transcript segments")


class TTSResponse(BaseModel):
    """Response model for TTS with timestamps."""
    
    success: bool = Field(description="Whether the operation succeeded")
    transcript: TranscriptResponse = Field(description="Transcript with timing information")
    audio_base_64: Optional[str] = Field(None, description="Base64 encoded audio data")
    metadata: dict = Field(description="Additional metadata about the generation")


@router.post("/tts-with-timestamps", response_model=TTSResponse)
async def tts_with_timestamps(
    request: TTSRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Generate speech from text with detailed timestamp information.
    
    This endpoint converts text to speech using ElevenLabs API and returns:
    - Base64 encoded audio data
    - Word-level timing information
    - Sentence-level segments with timing
    
    The timing information is derived from character-level data provided by
    ElevenLabs and automatically converted to word and sentence levels.
    
    **Authentication:** Requires X-API-Key header
    
    **Example:**
    ```json
    {
        "text": "Hello world, this is a test.",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "language": "en"
    }
    ```
    """
    try:
        logger.info({
            "msg": "TTS request received",
            "text_length": len(request.text),
            "voice_id": request.voice_id,
            "language": request.language,
        })
        
        # Call TTS function
        transcript, audio_base_64 = text_to_speech_with_timestamps(
            text=request.text,
            voice_id=request.voice_id,
            output_path=None,  # Don't save to file when called via API
            save_transcript=False,
            optimize_streaming_latency=request.optimize_streaming_latency,
            output_format=request.output_format,
            model_id=request.model_id,
            language=request.language,
            return_audio_base_64=request.return_audio,
        )
        
        # Convert transcript to response format
        segments_data = []
        for segment in transcript.segments:
            words_data = []
            if segment.words:
                for word in segment.words:
                    words_data.append(TranscriptWord(
                        start=word.start,
                        end=word.end,
                        word=word.word,
                        score=word.score,
                    ))
            
            segments_data.append(TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                words=words_data,
            ))
        
        transcript_response = TranscriptResponse(segments=segments_data)
        
        # Calculate metadata
        total_words = sum(len(seg.words) if seg.words else 0 for seg in transcript.segments)
        duration = transcript.segments[-1].end if transcript.segments else 0.0
        
        return TTSResponse(
            success=True,
            transcript=transcript_response,
            audio_base_64=audio_base_64 if request.return_audio else None,
            metadata={
                "character_count": len(request.text),
                "word_count": total_words,
                "segment_count": len(transcript.segments),
                "duration_seconds": duration,
                "voice_id": request.voice_id,
                "model_id": request.model_id,
                "language": transcript.detected_language,
            }
        )
        
    except Exception as e:
        logger.error({
            "msg": "TTS request failed",
            "error": str(e),
            "text_length": len(request.text),
        })
        raise HTTPException(
            status_code=500,
            detail=f"TTS generation failed: {str(e)}"
        )


@router.get("/voices")
async def list_voices(api_key: str = Depends(verify_api_key)):
    """
    List commonly used ElevenLabs voices.
    
    Returns a list of popular voice IDs with descriptions.
    For the complete voice library, visit: https://elevenlabs.io/voice-library
    
    **Authentication:** Requires X-API-Key header
    """
    return {
        "voices": [
            {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "gender": "female", "description": "Default voice, calm and clear"},
            {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi", "gender": "female", "description": "Warm and friendly"},
            {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "gender": "female", "description": "Soft and gentle"},
            {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "gender": "male", "description": "Well-rounded and versatile"},
            {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli", "gender": "female", "description": "Young and energetic"},
            {"id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh", "gender": "male", "description": "Deep and authoritative"},
            {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold", "gender": "male", "description": "Mature and commanding"},
            {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "gender": "male", "description": "Deep and resonant"},
            {"id": "yoZ06aMxZJJ28mfd3POQ", "name": "Sam", "gender": "male", "description": "Dynamic and expressive"},
        ],
        "note": "For the complete voice library, visit https://elevenlabs.io/voice-library"
    }

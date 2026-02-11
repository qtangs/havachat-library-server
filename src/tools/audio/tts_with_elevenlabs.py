"""
ElevenLabs Text-to-Speech with Timestamps

This module provides text-to-speech generation using ElevenLabs API with detailed
timestamp information at character, word, and sentence levels. The timing data
is converted to match the Transcript schema defined in datatypes/transcript.py.

## Local CLI Usage:
    uv run python -m src.tools.audio.tts_with_elevenlabs "Hello world" "voice_id" "output.mp3" "en"

## API Usage:
    This module is exposed via FastAPI endpoint at POST /audio/tts-with-timestamps
    
    See api/routes/audio.py for the API endpoint implementation.

## Features:
- Character-level timing from ElevenLabs API
- Automatic conversion to word-level timing
- Automatic conversion to sentence-level segments
- Fallback from normalized_alignment to alignment
- Compatible with Transcript schema
- Logging with timing and cost estimates
"""

import base64
import json
import os
import re
import time
from typing import List, Optional

from elevenlabs import ElevenLabs

from datatypes.transcript import Transcript, TranscriptSegment, TranscriptWord
from libs.logging_helper import logger


def _group_characters_into_words(
    characters: List[str],
    character_start_times: List[float],
    character_end_times: List[float],
) -> List[TranscriptWord]:
    """
    Convert character-level timing information into word-level timing.
    
    Args:
        characters: List of individual characters
        character_start_times: Start time for each character
        character_end_times: End time for each character
        
    Returns:
        List of TranscriptWord objects with word-level timing
    """
    words = []
    current_word = ""
    word_start = None
    word_end = None
    
    for i, (char, start, end) in enumerate(zip(characters, character_start_times, character_end_times)):
        # Check if this is a word boundary (space, punctuation, etc.)
        if char.isspace() or char in ',.:;!?()[]{}"\'-':
            # Save the current word if it exists
            if current_word:
                words.append(TranscriptWord(
                    start=word_start,
                    end=word_end,
                    word=current_word,
                    score=None,
                ))
                current_word = ""
                word_start = None
                word_end = None
            
            # Handle punctuation as separate "words" if they're not spaces
            if not char.isspace():
                words.append(TranscriptWord(
                    start=start,
                    end=end,
                    word=char,
                    score=None,
                ))
        else:
            # Add character to current word
            if word_start is None:
                word_start = start
            word_end = end
            current_word += char
    
    # Don't forget the last word
    if current_word:
        words.append(TranscriptWord(
            start=word_start,
            end=word_end,
            word=current_word,
            score=None,
        ))
    
    return words


def _group_words_into_segments(
    words: List[TranscriptWord],
    text: str,
) -> List[TranscriptSegment]:
    """
    Convert word-level timing into sentence-level segments.
    
    Args:
        words: List of TranscriptWord objects
        text: The full text to split into sentences
        
    Returns:
        List of TranscriptSegment objects with sentence-level timing
    """
    # Split text into sentences using regex
    sentence_pattern = r'[.!?]+\s*'
    sentence_boundaries = [(m.start(), m.end()) for m in re.finditer(sentence_pattern, text)]
    
    if not sentence_boundaries:
        # No sentence boundaries found, return entire text as one segment
        return [TranscriptSegment(
            start=words[0].start if words else 0.0,
            end=words[-1].end if words else 0.0,
            text=text,
            words=words,
            speaker=None,
        )]
    
    segments = []
    current_word_idx = 0
    sentence_start_pos = 0
    
    for boundary_start, boundary_end in sentence_boundaries:
        # Extract sentence text
        sentence_text = text[sentence_start_pos:boundary_end].strip()
        
        if not sentence_text:
            sentence_start_pos = boundary_end
            continue
        
        # Find words that belong to this sentence
        sentence_words = []
        sentence_word_count = len(sentence_text.split())
        
        # Estimate how many words belong to this sentence
        while current_word_idx < len(words) and len(sentence_words) < sentence_word_count + 5:  # +5 for punctuation
            sentence_words.append(words[current_word_idx])
            current_word_idx += 1
        
        if sentence_words:
            segments.append(TranscriptSegment(
                start=sentence_words[0].start,
                end=sentence_words[-1].end,
                text=sentence_text,
                words=sentence_words,
                speaker=None,
            ))
        
        sentence_start_pos = boundary_end
    
    # Handle remaining text after last sentence boundary
    if sentence_start_pos < len(text) and current_word_idx < len(words):
        remaining_text = text[sentence_start_pos:].strip()
        remaining_words = words[current_word_idx:]
        
        if remaining_text and remaining_words:
            segments.append(TranscriptSegment(
                start=remaining_words[0].start,
                end=remaining_words[-1].end,
                text=remaining_text,
                words=remaining_words,
                speaker=None,
            ))
    
    # If no segments were created, create one with all content
    if not segments and words:
        segments.append(TranscriptSegment(
            start=words[0].start,
            end=words[-1].end,
            text=text,
            words=words,
            speaker=None,
        ))
    
    return segments


def text_to_speech_with_timestamps(
    text: str,
    voice_id: str,
    output_path: Optional[str] = None,
    save_transcript: bool = False,
    optimize_streaming_latency: int = 0,
    output_format: str = "mp3_44100_128",
    model_id: str = "eleven_multilingual_v2",
    language: Optional[str] = None,
    return_audio_base_64: bool = False,
) -> tuple[Transcript, Optional[str]]:
    """
    Generate speech from text using ElevenLabs TTS with timestamp information.
    
    Args:
        text: The text to convert to speech
        voice_id: ElevenLabs voice ID to use
        output_path: Optional path to save the audio file
        save_transcript: Whether to save the transcript JSON file
        optimize_streaming_latency: Optimization level (0-4)
        output_format: Audio format (e.g., mp3_44100_128, pcm_16000, etc.)
        model_id: Model ID to use (default: eleven_multilingual_v2)
        language: Optional language code for the text
        return_audio_base_64: Whether to return the base64 audio data
        
    Returns:
        Tuple of (Transcript object, optional base64 audio string)
    """
    try:
        import elevenlabs
    except ImportError:
        raise Exception("Install the `elevenlabs` package to use this.")
    
    logger.info({"msg": "Start ElevenLabs TTS API call with timestamps"})
    start_time = time.time()
    
    client = ElevenLabs(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
    )
    
    # Call the API with timestamps enabled
    params = {
        "voice_id": voice_id,
        "text": text,
        "model_id": model_id,
        "output_format": output_format,
    }

    if model_id == "eleven_multilingual_v2":
        params["optimize_streaming_latency"] = optimize_streaming_latency
    
    if language:
        params["language_code"] = language
    
    response = client.text_to_speech.convert_with_timestamps(**params)
    
    # Extract alignment data - prefer normalized_alignment over alignment
    alignment = None
    if hasattr(response, 'normalized_alignment') and response.normalized_alignment:
        alignment = response.normalized_alignment
        logger.info({"msg": "Using normalized_alignment for timing"})
    elif hasattr(response, 'alignment') and response.alignment:
        alignment = response.alignment
        logger.info({"msg": "Using alignment for timing (fallback)"})
    else:
        raise Exception("No alignment data available in response")
    
    # Extract timing information
    characters = alignment.characters
    character_start_times = alignment.character_start_times_seconds
    character_end_times = alignment.character_end_times_seconds
    
    # Convert character-level timing to word-level
    words = _group_characters_into_words(
        characters,
        character_start_times,
        character_end_times,
    )
    
    # Convert word-level timing to sentence-level segments
    segments = _group_words_into_segments(words, text)
    
    # Create Transcript object
    transcript = Transcript(
        segments=segments,
        doc_id=None,
        index=0,
        is_last_transcript=True,
        url=None,
        title=f"TTS: {text[:50]}..." if len(text) > 50 else f"TTS: {text}",
        transcriber="elevenlabs_tts",
        detected_language=language,
    )
    
    # Get audio data
    audio_base_64_str = None
    if hasattr(response, 'audio_base_64'):
        audio_base_64_str = response.audio_base_64
        
        # Save audio file if output_path is provided
        if output_path:
            audio_data = base64.b64decode(audio_base_64_str)
            # Create parent directory if it doesn't exist
            parent_dir = os.path.dirname(output_path)
            if parent_dir:  # Only create if there's a parent directory
                os.makedirs(parent_dir, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_data)
            logger.info({"msg": f"Audio saved to {output_path}"})
    else:
        logger.warning({"msg": "No audio_base_64 found in response"})
        print(response.__dict__)
    
    # Save transcript if requested
    if save_transcript and output_path:
        transcript_path = f"{output_path}_transcript.json"
        with open(transcript_path, "w") as f:
            json.dump(transcript.to_dict(), f, indent=2)
        logger.info({"msg": f"Transcript saved to {transcript_path}"})
    
    end_time = time.time()
    
    # Calculate character count for cost estimation
    char_count = len(text)
    
    logger.info({
        "msg": "Completed ElevenLabs TTS API call",
        "time_taken": end_time - start_time,
        "character_count": char_count,
        "word_count": len(words),
        "segment_count": len(segments),
        "audio_byte_size": len(base64.b64decode(audio_base_64_str)) if audio_base_64_str else 0,
    })
    
    return transcript, audio_base_64_str if return_audio_base_64 else None


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Example usage: python tts_with_elevenlabs.py "Your text here" "voice_id" "output.mp3"
    if len(sys.argv) < 3:
        print("Usage: python tts_with_elevenlabs.py <text> <voice_id> [output_path] [language]")
        sys.exit(1)
    
    text = sys.argv[1]
    voice_id = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    language = sys.argv[4] if len(sys.argv) > 4 else None
    
    transcript, _ = text_to_speech_with_timestamps(
        text=text,
        voice_id=voice_id,
        output_path=output_path,
        save_transcript=True,
        language=language,
    )
    
    print("\n=== Transcript Summary ===")
    print(f"Total segments: {len(transcript.segments)}")
    print(f"Language: {transcript.detected_language}")
    print("\n=== Segments ===")
    for i, segment in enumerate(transcript.segments):
        print(f"\nSegment {i+1}:")
        print(f"  Time: {segment.start:.2f}s - {segment.end:.2f}s")
        print(f"  Text: {segment.text}")
        print(f"  Words: {len(segment.words) if segment.words else 0}")

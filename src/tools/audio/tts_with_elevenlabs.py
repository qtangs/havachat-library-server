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
- Pause handling: splits text by [pause X seconds] or [pause Xs] and generates audio in segments
"""

import base64
import json
import os
import re
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

from elevenlabs import ElevenLabs

from datatypes.transcript import Transcript, TranscriptSegment, TranscriptWord
from libs.logging_helper import logger


@dataclass
class TextSegment:
    """Represents a segment of text or pause"""
    type: str  # "text" or "pause"
    content: str
    pause_duration: Optional[float] = None  # in seconds, only for pause type


def _parse_text_with_pauses(text: str) -> List[TextSegment]:
    """
    Parse text containing [pause X seconds] or [pause Xs] markers into segments.
    
    Supported formats:
    - [pause 2 seconds]
    - [pause 2s]
    - [pause 0.5 seconds]
    
    Args:
        text: Text potentially containing pause markers
        
    Returns:
        List of TextSegment objects
    """
    # Pattern matches: [pause 2 seconds], [pause 2s], [pause 0.5 seconds], etc.
    pause_pattern = r'\[pause\s+([\d.]+)\s*(?:seconds?|s)\]'
    
    segments = []
    last_end = 0
    
    for match in re.finditer(pause_pattern, text, re.IGNORECASE):
        # Add text before this pause (if any)
        if match.start() > last_end:
            text_content = text[last_end:match.start()].strip()
            if text_content:
                segments.append(TextSegment(type="text", content=text_content))
        
        # Add pause
        pause_duration = float(match.group(1))
        segments.append(TextSegment(
            type="pause",
            content=match.group(0),
            pause_duration=pause_duration
        ))
        
        last_end = match.end()
    
    # Add remaining text after last pause
    if last_end < len(text):
        text_content = text[last_end:].strip()
        if text_content:
            segments.append(TextSegment(type="text", content=text_content))
    
    return segments


def _generate_silence(duration_seconds: float, sample_rate: int = 44100) -> bytes:
    """
    Generate silence (zeros) for a given duration.
    
    Args:
        duration_seconds: Duration of silence in seconds
        sample_rate: Sample rate in Hz (default: 44100)
        
    Returns:
        Raw PCM audio data (16-bit, mono) as bytes
    """
    num_samples = int(duration_seconds * sample_rate)
    # 16-bit PCM: 2 bytes per sample
    silence = b'\x00\x00' * num_samples
    return silence


def _adjust_transcript_timestamps(
    transcript: Transcript,
    time_offset: float
) -> Transcript:
    """
    Adjust all timestamps in a transcript by a given offset.
    
    Args:
        transcript: Transcript to adjust
        time_offset: Seconds to add to all timestamps
        
    Returns:
        New Transcript with adjusted timestamps
    """
    adjusted_segments = []
    for segment in transcript.segments:
        adjusted_words = []
        if segment.words:
            for word in segment.words:
                adjusted_words.append(TranscriptWord(
                    start=word.start + time_offset,
                    end=word.end + time_offset,
                    word=word.word,
                    score=word.score,
                ))
        
        adjusted_segments.append(TranscriptSegment(
            start=segment.start + time_offset,
            end=segment.end + time_offset,
            text=segment.text,
            words=adjusted_words,
            speaker=segment.speaker,
        ))
    
    return Transcript(
        segments=adjusted_segments,
        doc_id=transcript.doc_id,
        index=transcript.index,
        is_last_transcript=transcript.is_last_transcript,
        url=transcript.url,
        title=transcript.title,
        transcriber=transcript.transcriber,
        detected_language=transcript.detected_language,
    )


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
    Convert word-level timing into sentence-level segments by precisely matching
    words to their positions in the text.
    
    Args:
        words: List of TranscriptWord objects
        text: The full text to split into sentences
        
    Returns:
        List of TranscriptSegment objects with sentence-level timing
    """
    if not words:
        return []
    
    # Split text into sentences using regex
    sentence_pattern = r'[.!?]+(?:\s+|$)'
    
    # Find all sentence boundaries
    sentences = []
    last_end = 0
    for match in re.finditer(sentence_pattern, text):
        sentence_text = text[last_end:match.end()].strip()
        if sentence_text:
            sentences.append(sentence_text)
        last_end = match.end()
    
    # Handle remaining text
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            sentences.append(remaining)
    
    # If no sentences found, treat entire text as one sentence
    if not sentences:
        return [TranscriptSegment(
            start=words[0].start,
            end=words[-1].end,
            text=text.strip(),
            words=words,
            speaker=None,
        )]
    
    # Now match words to sentences
    segments = []
    word_idx = 0
    
    for sentence_text in sentences:
        if word_idx >= len(words):
            break
        
        # Collect words for this sentence
        sentence_words = []
        accumulated_text = ""
        
        # Remove spaces and newlines for comparison
        target_text = sentence_text.replace(" ", "").replace("\n", "")
        
        while word_idx < len(words):
            word = words[word_idx]
            accumulated_text += word.word
            sentence_words.append(word)
            word_idx += 1
            
            # Check if we've accumulated enough
            accumulated_clean = accumulated_text.replace(" ", "").replace("\n", "")
            
            # If accumulated text matches or exceeds target, we're done with this sentence
            if target_text in accumulated_clean or accumulated_clean in target_text:
                # Check if we have a complete match
                if len(accumulated_clean) >= len(target_text) * 0.9:  # 90% match threshold
                    break
        
        if sentence_words:
            segments.append(TranscriptSegment(
                start=sentence_words[0].start,
                end=sentence_words[-1].end,
                text=sentence_text,
                words=sentence_words,
                speaker=None,
            ))
    
    # If there are leftover words, add them to the last segment or create a new one
    if word_idx < len(words):
        remaining_words = words[word_idx:]
        if segments:
            # Extend last segment
            segments[-1].words.extend(remaining_words)
            segments[-1].end = remaining_words[-1].end
        else:
            # Create new segment with remaining words
            remaining_text = "".join(w.word for w in remaining_words)
            segments.append(TranscriptSegment(
                start=remaining_words[0].start,
                end=remaining_words[-1].end,
                text=remaining_text,
                words=remaining_words,
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
    
    Supports pause markers: [pause 2 seconds] or [pause 2s]
    Text is split into segments, with actual text sent to ElevenLabs and pauses added as silence.
    The result is a single MP3 file and transcript with continuous timestamps.
    
    Args:
        text: The text to convert to speech (may include [pause X seconds] markers)
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
        from pydub import AudioSegment
        import io
    except ImportError as e:
        raise Exception(f"Install required packages: {e}")
    
    logger.info({
        "msg": "Start ElevenLabs TTS API call with timestamps",
        "voice_id": voice_id,
        "model_id": model_id,
        "output_format": output_format,
        "optimize_streaming_latency": optimize_streaming_latency,
        "language": language,
        "input_text_length": len(text),
        "return_audio_base_64": return_audio_base_64,
        "save_transcript": save_transcript,
        "output_path": output_path,
    })
    start_time = time.time()
    
    # Parse text into segments (text and pauses)
    segments = _parse_text_with_pauses(text)
    
    logger.info({
        "msg": "Parsed text into segments",
        "total_segments": len(segments),
        "text_segments": sum(1 for s in segments if s.type == "text"),
        "pause_segments": sum(1 for s in segments if s.type == "pause"),
    })
    
    client = ElevenLabs(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
    )
    
    # Process each segment and combine
    combined_audio_segments = []
    combined_transcripts = []
    combined_alignments_debug = []  # Store alignment data for each text segment
    previous_request_ids = []
    current_time_offset = 0.0
    total_input_chars = 0
    total_spoken_chars = 0
    
    for i, segment in enumerate(segments):
        if segment.type == "pause":
            # Add silence for pause
            pause_duration = segment.pause_duration
            logger.info({
                "msg": f"Adding pause segment {i+1}",
                "duration": pause_duration,
                "time_offset": current_time_offset,
            })
            
            # Store pause debug data
            combined_alignments_debug.append({
                "segment_index": i,
                "segment_type": "pause",
                "pause_duration": pause_duration,
                "pause_marker": segment.content,
                "time_offset": current_time_offset,
            })
            
            # Create silent audio segment
            silence = AudioSegment.silent(duration=int(pause_duration * 1000))  # pydub uses ms
            combined_audio_segments.append(silence)
            current_time_offset += pause_duration
            
        else:  # text segment
            segment_text = segment.content
            total_input_chars += len(segment_text)
            
            logger.info({
                "msg": f"Generating audio for text segment {i+1}",
                "text_preview": segment_text[:50] + "..." if len(segment_text) > 50 else segment_text,
                "text_length": len(segment_text),
                "time_offset": current_time_offset,
                "previous_request_ids": previous_request_ids[-3:] if previous_request_ids else [],
            })
            
            # Call ElevenLabs API with timestamps
            params = {
                "voice_id": voice_id,
                "text": segment_text,
                "model_id": model_id,
                "output_format": output_format,
            }
            
            if model_id == "eleven_multilingual_v2":
                params["optimize_streaming_latency"] = optimize_streaming_latency
            
            if language:
                params["language_code"] = language
            
            # Add previous_request_ids for request stitching (maintains voice prosody across chunks)
            # https://elevenlabs.io/docs/eleven-api/guides/cookbooks/text-to-speech/request-stitching
            # Only include previous_request_ids for non-eleven_v3 models, as v3 may not support it
            if previous_request_ids and model_id != "eleven_v3":
                params["previous_request_ids"] = previous_request_ids[-3:]  # Include last 3 request IDs for better stitching
            
            # Use with_raw_response to access headers for request stitching
            raw_response = client.text_to_speech.with_raw_response.convert_with_timestamps(**params)

            # Extract request ID from headers for next segment
            request_id = raw_response._response.headers.get("request-id")
            if request_id:
                previous_request_ids.append(request_id)
                logger.debug({
                    "msg": f"Got request_id from headers for segment {i+1}",
                    "request_id": request_id,
                    "total_request_ids": len(previous_request_ids),
                })
            
            # Get the actual response data
            response = raw_response.data
            
            # Extract alignment data
            alignment = None
            if hasattr(response, 'normalized_alignment') and response.normalized_alignment:
                alignment = response.normalized_alignment
            elif hasattr(response, 'alignment') and response.alignment:
                alignment = response.alignment
            else:
                raise Exception(f"No alignment data available for segment {i+1}")
            
            # Extract timing information
            characters = alignment.characters
            character_start_times = alignment.character_start_times_seconds
            character_end_times = alignment.character_end_times_seconds
            
            total_spoken_chars += len(characters)
            
            # Convert character-level timing to word-level
            words = _group_characters_into_words(
                characters,
                character_start_times,
                character_end_times,
            )
            
            # Reconstruct spoken text and create segments
            spoken_text = "".join(characters)
            transcript_segments = _group_words_into_segments(words, spoken_text)
            
            # Store alignment debug data for this segment
            combined_alignments_debug.append({
                "segment_index": i,
                "segment_type": "text",
                "input_text": segment_text,
                "spoken_text": spoken_text,
                "time_offset": current_time_offset,
                "characters": characters,
                "character_start_times_seconds": character_start_times,
                "character_end_times_seconds": character_end_times,
                "character_count": len(characters),
                "word_count": len(words),
                "request_id": previous_request_ids[-1] if previous_request_ids else None,
            })
            
            # Create transcript for this segment (with original timestamps)
            segment_transcript = Transcript(
                segments=transcript_segments,
                doc_id=None,
                index=i,
                is_last_transcript=False,
                url=None,
                title=f"Segment {i+1}",
                transcriber="elevenlabs_tts",
                detected_language=language,
            )
            
            # Adjust timestamps and add to combined list
            adjusted_transcript = _adjust_transcript_timestamps(segment_transcript, current_time_offset)
            combined_transcripts.append(adjusted_transcript)
            
            # Get audio duration from last timestamp
            if transcript_segments and transcript_segments[-1].end > 0:
                segment_duration = transcript_segments[-1].end
                current_time_offset += segment_duration
            
            # Get audio data and add to combined segments
            if hasattr(response, 'audio_base_64'):
                audio_data = base64.b64decode(response.audio_base_64)
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
                combined_audio_segments.append(audio_segment)
            else:
                raise Exception(f"No audio data for segment {i+1}")
    
    # Combine all audio segments
    if not combined_audio_segments:
        raise Exception("No audio segments generated")
    
    final_audio = combined_audio_segments[0]
    for audio_seg in combined_audio_segments[1:]:
        final_audio += audio_seg
    
    # Combine all transcripts
    all_segments = []
    for trans in combined_transcripts:
        all_segments.extend(trans.segments)
    
    final_transcript = Transcript(
        segments=all_segments,
        doc_id=None,
        index=0,
        is_last_transcript=True,
        url=None,
        title=f"TTS: {text[:50]}..." if len(text) > 50 else f"TTS: {text}",
        transcriber="elevenlabs_tts",
        detected_language=language,
    )
    
    # Save combined audio
    audio_base_64_str = None
    if output_path:
        # Create parent directory if needed
        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # Export as MP3
        final_audio.export(output_path, format="mp3")
        logger.info({"msg": f"Combined audio saved to {output_path}"})
        
        # Convert to base64 if requested
        if return_audio_base_64:
            with open(output_path, "rb") as f:
                audio_base_64_str = base64.b64encode(f.read()).decode('utf-8')
    elif return_audio_base_64:
        # Export to buffer for base64
        buffer = io.BytesIO()
        final_audio.export(buffer, format="mp3")
        audio_base_64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # Save transcript if requested
    if save_transcript and output_path:
        transcript_path = f"{output_path}_transcript.json"
        with open(transcript_path, "w") as f:
            json.dump(final_transcript.to_dict(), f, indent=2)
        logger.info({"msg": f"Transcript saved to {transcript_path}"})
        
        # Save detailed alignment data for each segment
        alignment_path = f"{output_path}_alignment.json"
        with open(alignment_path, "w") as f:
            json.dump({
                "input_text": text,
                "total_duration": current_time_offset,
                "segments": combined_alignments_debug,
            }, f, indent=2)
        logger.info({"msg": f"Alignment data saved to {alignment_path}"})
        
        if len(segments) > 0:
            # Save simplified segment debug info
            debug_path = f"{output_path}_segments_debug.json"
            debug_info = {
                "input_text": text,
                "total_segments": len(segments),
                "text_segments": [s.content for s in segments if s.type == "text"],
                "pause_segments": [{"duration": s.pause_duration, "marker": s.content} for s in segments if s.type == "pause"],
                "total_duration": current_time_offset,
                "request_ids": previous_request_ids,
            }
            with open(debug_path, "w") as f:
                json.dump(debug_info, f, indent=2)
            logger.info({"msg": f"Segment debug data saved to {debug_path}"})
    
    end_time = time.time()
    
    logger.info({
        "msg": "Completed ElevenLabs TTS with segments",
        "time_taken": end_time - start_time,
        "total_segments": len(segments),
        "text_segments": sum(1 for s in segments if s.type == "text"),
        "pause_segments": sum(1 for s in segments if s.type == "pause"),
        "input_character_count": total_input_chars,
        "spoken_character_count": total_spoken_chars,
        "total_duration": current_time_offset,
        "transcript_segments": len(all_segments),
    })
    
    return final_transcript, audio_base_64_str if return_audio_base_64 else None


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

import json
import os
import time

from elevenlabs.client import ElevenLabs

from datatypes.transcript import Transcript
from libs.logging_helper import logger


def transcribe_audio_with_elevenlabs(
    file_path: str,
    prompt: str = None,
    language: str = None,
    save_to_file: bool = False,
) -> Transcript:
    """
    Transcribe an audio file using ElevenLabs' Scribe.
    https://elevenlabs.io/docs/developers/guides/cookbooks/speech-to-text/quickstart
    """
    try:
        pass  # elevenlabs already imported at module level
    except ImportError:
        raise Exception("Install the `elevenlabs` package to use this.")

    logger.info({"msg": "Start ElevenLabs API call"})
    start = time.time()
    el_client = ElevenLabs(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
    )

    # Pass the open file handle directly; the SDK expects a binary file-like object
    with open(file_path, "rb") as audio_file:
        params = {
            "file": audio_file,
            "model_id": "scribe_v2",
        }

        if prompt:
            params["prompt"] = prompt

        if language:
            params["language_code"] = language

        transcription = el_client.speech_to_text.convert(**params)

    print("Transcription result:", transcription)

    # Convert to Transcript object
    from datatypes.transcript import Transcript, TranscriptSegment, TranscriptWord
    
    # ElevenLabs returns a flat structure with text and words at the top level
    full_text = transcription.text if hasattr(transcription, 'text') else str(transcription)
    
    words = []
    if hasattr(transcription, 'words') and transcription.words:
        for w in transcription.words:
            words.append(TranscriptWord(
                start=w.start if hasattr(w, 'start') else None,
                end=w.end if hasattr(w, 'end') else None,
                word=w.text if hasattr(w, 'text') else str(w),
                score=None,  # ElevenLabs uses logprob, not confidence score
            ))
    
    # Calculate start and end times from words if available
    start_time = words[0].start if words and words[0].start is not None else 0.0
    end_time = words[-1].end if words and words[-1].end is not None else 0.0
    
    segments = [TranscriptSegment(
        start=start_time,
        end=end_time,
        text=full_text,
        words=words if words else None,
        speaker=None,
    )]
    
    result = Transcript(
        segments=segments,
        doc_id=None,
        index=0,
        is_last_transcript=True,
        url=None,
        title=os.path.basename(file_path),
        transcriber="elevenlabs",
        detected_language=transcription.language_code if hasattr(transcription, 'language_code') else language,
    )
    end = time.time()
    logger.info(
        {
            "msg": "Completed ElevenLabs API call",
            "time_taken": end - start,
            "cost_estimate": (end - start) * 0.3 / 60,  # $0.30 per minute estimate
        }
    )

    if save_to_file:
        # Write to file
        with open(f"{file_path}_elevenlabs.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)
    
    return result


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    transcribe_audio_with_elevenlabs(
        file_path=sys.argv[1],
        prompt=sys.argv[2] if len(sys.argv) > 2 else None,
        save_to_file=True,
    )

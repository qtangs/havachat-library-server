import json
import os
from typing import Optional

from datatypes.transcript import Transcript


def transcribe_audio(
    video_id: str,
    file_path: str,
    prompt: str = None,
    language: str = None,
    output_dir: Optional[str] = None,
) -> Transcript:
    """Transcribe audio file with one of the providers
    and save to the folder transcripts in output_dir"""
    TRANSCRIPTION_SERVICE = os.environ.get(
        "TRANSCRIPTION_SERVICE", "Replicate"  # use Replicate for best quality
    )

    if TRANSCRIPTION_SERVICE == "Groq":
        from tools.audio.transcribe_audio_with_groq import (
            transcribe_audio_with_groq,
        )

        transcript = transcribe_audio_with_groq(
            file_path=file_path,
            prompt=prompt,
            language=language,
        )

    elif TRANSCRIPTION_SERVICE == "Fal":
        from tools.audio.transcribe_audio_with_fal import (
            transcribe_audio_with_fal,
        )

        transcript = transcribe_audio_with_fal(
            file_path=file_path,
            prompt=prompt,
            language=language,
        )

    elif TRANSCRIPTION_SERVICE == "Replicate":
        from tools.audio.transcribe_audio_with_replicate import (
            transcribe_audio_with_replicate,
        )

        transcript = transcribe_audio_with_replicate(
            file_path=file_path,
            prompt=prompt,
            language=language,
        )

    else:
        raise ValueError(
            f"Invalid TRANSCRIPTION_SERVICE: {TRANSCRIPTION_SERVICE}",
        )

    if output_dir:
        with open(
            os.path.join(output_dir, f"{video_id}_transcript.json"), "w"
        ) as f:
            json.dump(transcript.dict(), f, indent=2)

    return transcript

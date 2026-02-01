import json
import time

from datatypes.transcript import Transcript
from datatypes.transcript import TranscriptSegment
from libs.logging_helper import logger
from tools.text.merge_transcript_into_sentences import (
    merge_transcript_into_sentences,
)
from tools.text.post_process_groq_segments import post_process_groq_segments


def transcribe_audio_with_groq(
    file_path: str,
    prompt: str = None,
    language: str = None,
) -> Transcript:
    """
    Transcribe an audio file using Groq's Whisper.
    https://console.groq.com/docs/speech-to-text

    Note:
        + File uploads are limited to 25 MB
        + Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, and webm
        + If multiple audio tracks, e.g. video with dubs, only use 1st track
        + Whisper will downsample audio to 16,000 Hz mono before transcribing
        https://github.com/openai/whisper/discussions/870#discussioncomment-4743438

    Also check this for prompting guide:
    https://cookbook.openai.com/examples/whisper_prompting_guide
    """
    try:
        from groq import Groq, NOT_GIVEN
    except ImportError:
        raise Exception("Install the `groq` package to use this.")

    client = Groq()

    with open(file_path, "rb") as file:
        logger.info({"msg": "Start Groq Whisper API call"})
        start = time.time()

        transcription = client.audio.transcriptions.create(
            file=(file_path, file.read()),
            model="whisper-large-v3",
            prompt=prompt or NOT_GIVEN,
            response_format="verbose_json",
            language=language or NOT_GIVEN,
            temperature=0.0,
            timeout=120.0,
        )
        end = time.time()
        logger.info(
            {
                "msg": "Completed Groq Whisper API call",
                "time_taken": end - start,
                "cost_estimate": (end - start) * 0.000008333333333,
            }
        )

        segments = post_process_groq_segments(transcription.segments)
        transcript = Transcript(segments=segments)
        transcript = merge_transcript_into_sentences(transcript.to_dict())

        with open(f"{file_path}_groq.json", "w") as f:
            json.dump(transcript, f, indent=2)

        return Transcript(
            segments=[TranscriptSegment(**s) for s in transcription.segments]
        )


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    transcribe_audio_with_groq(
        file_path=sys.argv[1],
        prompt=sys.argv[2] if len(sys.argv) > 2 else None,
    )

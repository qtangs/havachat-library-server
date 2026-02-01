import json
import time

from datatypes.transcript import Transcript
from libs.logging_helper import logger
from tools.file_upload import default_file_upload_func


def transcribe_audio_with_fal(
    file_path: str,
    prompt: str = None,
    language: str = None,
    save_to_file: bool = False,
) -> Transcript:
    """
    Transcribe an audio file using Fal.ai's Whisper.
    https://fal.ai/models/fal-ai/whisper

    Alternative is wizper, but it doesn't support word/sentence timestamps.

    Also check this for prompting guide:
    https://cookbook.openai.com/examples/whisper_prompting_guide
    """
    try:
        import fal_client
    except ImportError:
        raise Exception("Install the `fal-client` package to use this.")

    # Upload file
    uploaded_file_url = default_file_upload_func(file_path)

    logger.info({"msg": "Start Replicate API call"})
    start = time.time()
    handler = fal_client.submit(
        "fal-ai/whisper",
        arguments={
            "audio_url": uploaded_file_url,
            "task": "transcribe",
            "language": language,
            "chunk_level": "word",
            "prompt": prompt or "",
        },
    )

    result = handler.get()
    end = time.time()
    logger.info(
        {
            "msg": "Completed Fal.ai Whisper API call",
            "time_taken": end - start,
            "cost_estimate": (end - start) * 0.001108333333,
        }
    )

    if save_to_file:
        # Write to file
        with open(f"{file_path}_fal.json", "w") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    transcribe_audio_with_fal(
        file_path=sys.argv[1],
        prompt=sys.argv[2] if len(sys.argv) > 2 else None,
        save_to_file=True,
    )

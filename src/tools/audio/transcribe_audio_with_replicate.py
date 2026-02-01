import json
import os
import time

from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from datatypes.transcript import Transcript
from libs.logging_helper import logger
from tools.file_upload import default_file_upload_func


def transcribe_audio_with_replicate(
    file_path: str,
    prompt: str = None,
    language: str = None,
    save_to_file: bool = False,
) -> Transcript:
    """
    Transcribe an audio file using Replicate's WhisperX.
    https://replicate.com/victor-upmeet/whisperx

    Also check this for prompting guide:
    https://cookbook.openai.com/examples/whisper_prompting_guide
    """
    try:
        import replicate

        if "REPLICATE_API_TOKEN" not in os.environ:
            raise Exception(
                "Please set REPLICATE_API_TOKEN in your environment variables"
            )
    except ImportError:
        raise Exception("Install the `replicate` package to use this.")

    import httpx

    replicate_client = replicate.Client(
        api_token=os.environ.get("REPLICATE_API_TOKEN"),
        timeout=httpx.Timeout(600.0),
    )

    # Upload file
    uploaded_file_url = default_file_upload_func(file_path)

    try:
        output = _call_replicate_api_with_retry(
            replicate_client, uploaded_file_url, prompt, language
        )
    except Exception as e:
        logger.error(
            {
                "msg": "Fail to get Replicate output",
                "error": str(e)[:1000],
            }
        )
        raise e

    if save_to_file:
        try:
            # Save output to json file in the same directory as the video file
            with open(f"{file_path}_replicate.json", "w") as json_file:
                json.dump(output, json_file, ensure_ascii=False, indent=2)
        except Exception as e:
            print(str(e)[:1000])

    return Transcript(**output)


@retry(wait=wait_exponential(multiplier=1, min=1), stop=stop_after_attempt(3))
def _call_replicate_api_with_retry(
    replicate_client, uploaded_file_url, prompt, language
):
    # Call Replicate API
    logger.info({"msg": "Start Replicate API call"})
    # Time the call
    start = time.time()
    output = replicate_client.run(
        "victor-upmeet/whisperx"
        ":"
        "84d2ad2d6194fe98a17d2b60bef1c7f910c46b2f6fd38996ca457afd9c8abfcb",
        # "thomasmol/whisper-diarization"
        # ":"
        # "cbd15da9f839c5f932742f86ce7def3a03c22e2b4171d42823e83e314547003f",
        # "vaibhavs10/incredibly-fast-whisper"
        # ":"
        # "3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
        input={
            "audio": uploaded_file_url,
            "audio_file": uploaded_file_url,
            "file_url": uploaded_file_url,
            "language": language or "en",  # or "english"
            "prompt": prompt or "",
            "initial_prompt": prompt or "",
            "align_output": True,
            "diarization": True,
            "diarise_audio": True,
            "huggingface_access_token": os.getenv("HUGGING_FACE_TOKEN"),
            "hf_token": os.getenv("HUGGING_FACE_TOKEN"),
            "min_speakers": 2,
            "max_speakers": 2,
        },
    )
    end = time.time()
    logger.info(
        {
            "msg": "Completed Replicate API call",
            "time_taken": end - start,
            "cost_estimate": (end - start) * 0.000575,
        }
    )
    return output


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    prompt = sys.argv[2] if len(sys.argv) > 2 else None

    transcribe_audio_with_replicate(
        sys.argv[1], prompt=prompt, save_to_file=True
    )

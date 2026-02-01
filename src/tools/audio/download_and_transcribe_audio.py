from libs.logging_helper import logger
from tools.audio import transcribe_audio
from tools.audio.preprocess_audio_for_whisper import downsample_audio
from tools.video.download_youtube_video import download_youtube_audio


async def download_and_transcribe_audio(video_id, output_dir):
    # Transcribe only if the transcription file is not already there
    # Download audio file
    logger.info({"msg": "Downloading audio"})
    audio_file_path = download_youtube_audio(
        video_id=video_id, output_dir=output_dir
    )
    logger.info(
        {
            "msg": "Completed downloading audio",
            "video_id": video_id,
            "audio_file_path": audio_file_path,
        }
    )
    # Preprocess
    logger.info({"msg": "Preprocess audio file"})
    audio_file_path = downsample_audio(input_file=audio_file_path)
    logger.info(
        {
            "msg": "Completed preprocess audio file",
            "video_id": video_id,
            "audio_file_path": audio_file_path,
        }
    )
    # Transcribe
    logger.info({"msg": "Transcribing audio"})
    transcript = transcribe_audio(
        video_id=video_id, file_path=audio_file_path, output_dir=output_dir
    )
    logger.info(
        {
            "msg": "Completed transcribing audio",
            "video_id": video_id,
            "transcript_snippets": transcript.segments[3],
        }
    )
    # Post process transcription file
    logger.info({"msg": "Post processing transcript"})
    return transcript

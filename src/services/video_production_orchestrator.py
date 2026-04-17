from __future__ import annotations

from pathlib import Path
from typing import Optional

from models.notion_audio import AudioContentStatus, AudioProcessorConfig
from models.video_production import (
    VideoCompositionConfig,
    VideoFormat,
    VideoProductionBatchRequest,
    VideoProductionItem,
    VideoProductionResult,
    VideoResolution,
)
from services.background_image_generator import (
    BackgroundImageGenerator,
    BackgroundImageGeneratorConfig,
)
from services.meditation_script_generator import (
    MeditationScriptGenerator,
    MeditationScriptGeneratorConfig,
)
from services.video_composer import VideoComposer


class VideoProductionOrchestrator:
    """Orchestrates the full meditation video production pipeline.

    Coordinates script generation, audio synthesis, background image generation,
    and video composition for a batch of video production items.
    """

    def __init__(self, config: AudioProcessorConfig) -> None:
        self.config = config
        self._script_gen = MeditationScriptGenerator(
            MeditationScriptGeneratorConfig(
                llm_backend="claude",
                claude_api_key=config.llm_api_key,
                openai_api_key=config.llm_api_key,
            )
        )
        self._composer = VideoComposer(ffmpeg_path=config.ffmpeg_path)

    async def _create_notion_records(
        self,
        items: list[VideoProductionItem],
        style_key: str,
        duration_key: str,
    ) -> list[VideoProductionItem]:
        """Create a Notion Audio Content record for each item, return items with notion_record_id populated."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.config.notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        updated: list[VideoProductionItem] = []
        for item in items:
            payload = {
                "parent": {"database_id": self.config.notion_audio_db_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": item.title}}]},
                    "Status": {"select": {"name": AudioContentStatus.PROCESSING.value}},
                },
            }
            resp = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            record_id = resp.json()["id"]
            updated.append(item.model_copy(update={"notion_record_id": record_id}))
        return updated

    def _update_notion_status(
        self,
        record_id: str,
        status: AudioContentStatus,
        error: str = None,
    ) -> None:
        """Update the Status (and optionally Notes) of a Notion Audio Content record."""
        import requests

        headers = {
            "Authorization": f"Bearer {self.config.notion_api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        props = {"Status": {"select": {"name": status.value}}}
        if error:
            props["Notes"] = {"rich_text": [{"text": {"content": error[:2000]}}]}
        requests.patch(
            f"https://api.notion.com/v1/pages/{record_id}",
            headers=headers,
            json={"properties": props},
        )

    async def _process_item(
        self,
        item: VideoProductionItem,
        request: VideoProductionBatchRequest,
        effective_voice_id: str,
    ) -> VideoProductionResult:
        """Run the full single-item pipeline: script → audio → image → video (+ Shorts variant)."""
        style_key = request.style_key
        duration_key = request.duration_key

        # 1. Generate meditation script
        script = await self._script_gen.generate(style_key, duration_key)

        # 2. Parse script into segments
        from models.meditation_script import MeditationScriptParser

        segments = MeditationScriptParser.parse(script.body)

        # 3. Generate audio per segment using ElevenLabs
        from elevenlabs import ElevenLabs

        el_client = ElevenLabs(api_key=self.config.elevenlabs_api_key)

        output_dir = self.config.video_output_path / item.title.replace(" ", "_")
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_segment_paths: list[tuple[Path, Optional[int]]] = []
        for seg_idx, seg in enumerate(segments):
            if not seg.text:
                continue
            seg_audio_path = output_dir / f"seg_{seg_idx:03d}.mp3"
            audio_bytes = el_client.text_to_speech.convert(
                voice_id=effective_voice_id,
                text=seg.text,
                model_id=self.config.tts_model,
            )
            # elevenlabs SDK returns bytes or a generator; handle both
            if hasattr(audio_bytes, "__iter__") and not isinstance(audio_bytes, bytes):
                audio_bytes = b"".join(audio_bytes)
            seg_audio_path.write_bytes(audio_bytes)
            audio_segment_paths.append((seg_audio_path, seg.pause_after_seconds))

        # 4. Generate background image
        img_backend = request.image_backend or self.config.image_backend
        img_quality = request.image_quality or self.config.image_quality
        img_gen = BackgroundImageGenerator(
            BackgroundImageGeneratorConfig(
                image_backend=img_backend,
                image_quality=img_quality,
                storage_path=self.config.storage_path,
            )
        )
        bg_image = await img_gen.generate(style_key, request.video_format)

        # 5. Compose video (long-form)
        video_output = output_dir / f"{item.title.replace(' ', '_')}.mp4"
        comp_config = VideoCompositionConfig(
            audio_path=output_dir / "stitched.mp3",  # composer will stitch
            image_path=bg_image.path,
            output_path=video_output,
            video_format=request.video_format,
            script_segments=audio_segment_paths,
            enable_karaoke=request.enable_karaoke,
            title_card_text=item.title,
        )
        result = await self._composer.compose(comp_config)

        # 6. Produce Shorts variant if requested
        if request.produce_shorts:
            shorts_bg = await img_gen.generate(style_key, VideoFormat.SHORTS)
            shorts_output = output_dir / f"{item.title.replace(' ', '_')}_shorts.mp4"
            shorts_config = VideoCompositionConfig(
                audio_path=comp_config.audio_path,
                image_path=shorts_bg.path,
                output_path=shorts_output,
                video_format=VideoFormat.SHORTS,
                enable_karaoke=True,  # always for Shorts
                title_card_text=item.title,
            )
            await self._composer.compose(shorts_config)

        return result

    async def run_batch(
        self, request: VideoProductionBatchRequest
    ) -> list[VideoProductionResult]:
        """Create Notion records, then process each item sequentially.

        On success each item's Notion record is updated to VIDEO_COMPLETED.
        On failure the record is updated to FAILED with the error message and
        a zero-result placeholder is appended so the caller receives one result
        per input item regardless of errors.
        """
        # Resolve effective voice ID (task 8.5)
        effective_voice_id = request.voice_id or self.config.default_voice_id

        # Create Notion records first (task 8.2)
        items_with_records = await self._create_notion_records(
            request.items, request.style_key, request.duration_key
        )

        results: list[VideoProductionResult] = []
        for item in items_with_records:
            try:
                result = await self._process_item(item, request, effective_voice_id)
                results.append(result)
                if item.notion_record_id:
                    self._update_notion_status(
                        item.notion_record_id, AudioContentStatus.VIDEO_COMPLETED
                    )
            except Exception as exc:
                error_msg = str(exc)
                results.append(
                    VideoProductionResult(
                        output_path=Path("/dev/null"),
                        duration_seconds=0.0,
                        file_size_bytes=0,
                        video_format=request.video_format,
                        resolution=VideoResolution.from_format(request.video_format),
                        processing_time_seconds=0.0,
                    )
                )
                if item.notion_record_id:
                    self._update_notion_status(
                        item.notion_record_id, AudioContentStatus.FAILED, error_msg
                    )
        return results

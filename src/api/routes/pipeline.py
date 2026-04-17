"""Pipeline API routes — meditation video production pipeline with pause gates."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from api.utils import verify_api_key
from models.meditation_script import DURATION_REGISTRY, STYLE_REGISTRY
from models.pipeline_run import (
    PipelineRun,
    PipelineStage,
    PipelineStageEvent,
    YoutubeMetadata,
    pipeline_store,
)
from models.video_production import VideoProductionBatchRequest

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Per-run SSE event queues: run_id → asyncio.Queue of PipelineStageEvent | None (None = end)
_event_queues: dict[UUID, asyncio.Queue] = {}


def _deserialize_transcript(data: dict | None):
    """Reconstruct a pydantic-v1 Transcript from a stored plain dict, or return None."""
    if not data:
        return None
    from datatypes.transcript import Transcript
    return Transcript(**data)


async def _emit_event(run_id: UUID, event: PipelineStageEvent) -> None:
    """Push event to the SSE queue for this run and update run state."""
    run = pipeline_store.get(run_id)
    if run:
        run.stage = PipelineStage(event.stage)
        pipeline_store.set(run)
    q = _event_queues.get(run_id)
    if q:
        await q.put(event)
    if event.status in ("complete", "failed"):
        if q:
            await q.put(None)  # signal end of stream


async def _run_script_stage(run_id: UUID) -> None:
    run = pipeline_store.get(run_id)
    if not run:
        return
    await _emit_event(run_id, PipelineStageEvent(
        run_id=str(run_id), stage="script", status="running", message="Generating meditation script..."
    ))
    try:
        from models.notion_audio import AudioProcessorConfig
        from services.meditation_script_generator import MeditationScriptGenerator, MeditationScriptGeneratorConfig
        import os
        cfg = MeditationScriptGeneratorConfig(
            llm_backend="claude",
            claude_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        gen = MeditationScriptGenerator(cfg)
        script = await gen.generate(run.config.style_key, run.config.duration_key)
        run.script = script
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="awaiting_script_approval",
            status="awaiting_approval", message="Script ready for review."
        ))
    except Exception as exc:
        run.error = str(exc)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="failed", status="failed", message=str(exc)
        ))


async def _run_audio_stage(run_id: UUID) -> None:
    run = pipeline_store.get(run_id)
    if not run or not run.script:
        return
    await _emit_event(run_id, PipelineStageEvent(
        run_id=str(run_id), stage="audio", status="running", message="Generating audio..."
    ))
    try:
        from pathlib import Path
        import os
        import asyncio
        from tools.audio.tts_with_elevenlabs import text_to_speech_with_timestamps

        storage_path = Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH", "/tmp"))
        output_dir = storage_path / "pipeline_runs" / str(run_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        voice_id = run.config.voice_id or os.getenv("DEFAULT_VOICE_ID", "7AvtJrjTNyBhBxEvNPIZ")
        tts_model = os.getenv("TTS_MODEL", "eleven_multilingual_v2")
        stitched_path = output_dir / "audio.mp3"

        # Use convert_with_timestamps so we get word-level timing for karaoke.
        # The function handles pause markers internally (inserts real silence via pydub)
        # and returns both the combined MP3 and a time-aligned Transcript.
        transcript, _ = await asyncio.to_thread(
            text_to_speech_with_timestamps,
            run.script.body,
            voice_id,
            str(stitched_path),
            False,   # save_transcript
            0,       # optimize_streaming_latency
            "mp3_44100_128",  # output_format
            tts_model,
            None,    # language
            False,   # return_audio_base_64
        )

        run.audio_path = stitched_path
        run.transcript = transcript.dict()  # store as plain dict (pydantic v1 → v2 boundary)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="awaiting_audio_approval",
            status="awaiting_approval", message="Audio ready for review."
        ))
    except Exception as exc:
        run.error = str(exc)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="failed", status="failed", message=str(exc)
        ))


async def _run_image_prompt_stage(run_id: UUID) -> None:
    """Generate YouTube metadata + default image prompt, then ask user to review."""
    run = pipeline_store.get(run_id)
    if not run or not run.script:
        return
    await _emit_event(run_id, PipelineStageEvent(
        run_id=str(run_id), stage="image_prompt", status="running",
        message="Generating image prompt and YouTube metadata..."
    ))
    try:
        import os, json
        import anthropic
        from models.meditation_script import STYLE_REGISTRY

        style = STYLE_REGISTRY.get(run.config.style_key)
        style_label = style.label if style else run.config.style_key
        script_snippet = run.script.body[:1200]  # enough context without burning tokens

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        tools = [{
            "name": "submit_metadata",
            "description": "Submit the image prompt and YouTube metadata",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_prompt": {"type": "string", "description": "Detailed Stable Diffusion / Gemini image prompt"},
                    "youtube_title": {"type": "string"},
                    "youtube_description": {"type": "string"},
                    "youtube_tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["image_prompt", "youtube_title", "youtube_description", "youtube_tags"],
            },
        }]
        prompt = f"""You are helping produce a meditation video.

Style: {style_label}
Script title: {run.script.title}
Script excerpt (first 1200 chars):
{script_snippet}

Please generate:
1. **image_prompt** — a vivid, detailed prompt (≈60 words) for an AI image generator to create a serene background image that suits this meditation. Describe atmosphere, colours, lighting and mood. 16:9 landscape composition.
2. **youtube_title** — an engaging, SEO-friendly title (≤60 chars).
3. **youtube_description** — 150-250 word description including a brief intro, what listeners will experience, and relevant keywords.
4. **youtube_tags** — 10-15 relevant tags as a list of strings.

Call submit_metadata now."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=tools,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": prompt}],
        )
        data = {}
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_metadata":
                data = block.input
                break

        run.image_prompt = data.get("image_prompt", f"{style_label} meditation, serene nature background, soft light")
        run.youtube_metadata = YoutubeMetadata(
            title=data.get("youtube_title", run.script.title),
            description=data.get("youtube_description", ""),
            tags=data.get("youtube_tags", []),
        )
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="awaiting_image_prompt_approval",
            status="awaiting_approval", message="Review image prompt and YouTube metadata."
        ))
    except Exception as exc:
        run.error = str(exc)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="failed", status="failed", message=str(exc)
        ))


async def _run_image_stage(run_id: UUID) -> None:
    run = pipeline_store.get(run_id)
    if not run:
        return
    await _emit_event(run_id, PipelineStageEvent(
        run_id=str(run_id), stage="image", status="running", message="Generating background image..."
    ))
    try:
        import os
        from pathlib import Path
        from services.background_image_generator import BackgroundImageGenerator, BackgroundImageGeneratorConfig
        storage_path = Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH", "/tmp"))
        img_backend = run.config.image_backend or os.getenv("IMAGE_BACKEND", "google")
        img_quality = run.config.image_quality or os.getenv("IMAGE_QUALITY", "nano")
        gen = BackgroundImageGenerator(BackgroundImageGeneratorConfig(
            image_backend=img_backend,
            image_quality=img_quality,
            storage_path=storage_path,
        ))
        bg = await gen.generate(run.config.style_key, run.config.video_format, custom_prompt=run.image_prompt)
        run.image_path = bg.path
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="awaiting_image_approval",
            status="awaiting_approval", message="Image ready for review."
        ))
    except Exception as exc:
        run.error = str(exc)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="failed", status="failed", message=str(exc)
        ))


async def _run_video_stage(run_id: UUID) -> None:
    run = pipeline_store.get(run_id)
    if not run or not run.audio_path or not run.image_path:
        return
    await _emit_event(run_id, PipelineStageEvent(
        run_id=str(run_id), stage="video", status="running", message="Composing video..."
    ))
    try:
        import os
        from services.video_composer import VideoComposer
        from models.video_production import VideoCompositionConfig
        storage_path = Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH", "/tmp"))
        output_dir = storage_path / "pipeline_runs" / str(run_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        video_output = output_dir / "video.mp4"
        composer = VideoComposer(ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"))
        comp_config = VideoCompositionConfig(
            audio_path=run.audio_path,
            image_path=run.image_path,
            output_path=video_output,
            video_format=run.config.video_format,
            transcript=_deserialize_transcript(run.transcript),
            enable_karaoke=bool(run.config.enable_karaoke and run.transcript is not None),
        )
        await composer.compose(comp_config)
        run.video_path = video_output
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="complete", status="complete", message="Video production complete!"
        ))
    except Exception as exc:
        run.error = str(exc)
        pipeline_store.set(run)
        await _emit_event(run_id, PipelineStageEvent(
            run_id=str(run_id), stage="failed", status="failed", message=str(exc)
        ))


# Map stage → next stage background task
_APPROVE_MAP: dict[PipelineStage, Any] = {
    PipelineStage.AWAITING_SCRIPT_APPROVAL: _run_audio_stage,
    PipelineStage.AWAITING_AUDIO_APPROVAL: _run_image_prompt_stage,
    PipelineStage.AWAITING_IMAGE_PROMPT_APPROVAL: _run_image_stage,
    PipelineStage.AWAITING_IMAGE_APPROVAL: _run_video_stage,
}

# Stages that can be rerun and what they clear
_RERUN_CLEARS: dict[str, list[str]] = {
    "script": ["script", "audio_path", "image_prompt", "image_path", "video_path", "shorts_path"],
    "audio": ["audio_path", "image_prompt", "image_path", "video_path", "shorts_path"],
    "image_prompt": ["image_prompt", "image_path", "video_path", "shorts_path"],
    "image": ["image_path", "video_path", "shorts_path"],
    "video": ["video_path", "shorts_path"],
}

_RERUN_TASK: dict[str, Any] = {
    "script": _run_script_stage,
    "audio": _run_audio_stage,
    "image_prompt": _run_image_prompt_stage,
    "image": _run_image_stage,
    "video": _run_video_stage,
}

_RERUN_REQUIRES: dict[str, list[str]] = {
    "audio": ["script"],
    "image_prompt": ["audio_path"],
    "image": ["audio_path"],
    "video": ["image_path"],
}


@router.post("/runs", dependencies=[Depends(verify_api_key)])
async def create_run(
    request: VideoProductionBatchRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Create a new pipeline run and immediately start script generation."""
    run = PipelineRun(config=request, stage=PipelineStage.IDLE)
    pipeline_store.set(run)
    _event_queues[run.run_id] = asyncio.Queue()
    background_tasks.add_task(_run_script_stage, run.run_id)
    return {"run_id": str(run.run_id)}


@router.get("/runs/{run_id}", dependencies=[Depends(verify_api_key)])
async def get_run(run_id: UUID) -> dict:
    run = pipeline_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": str(run.run_id),
        "stage": run.stage.value,
        "script": run.script.model_dump() if run.script else None,
        "audio_ready": run.audio_path is not None,
        "image_prompt": run.image_prompt,
        "image_ready": run.image_path is not None,
        "video_ready": run.video_path is not None,
        "youtube_metadata": run.youtube_metadata.model_dump() if run.youtube_metadata else None,
        "error": run.error,
    }


@router.patch("/runs/{run_id}/image-prompt", dependencies=[Depends(verify_api_key)])
async def update_image_prompt(run_id: UUID, body: dict) -> dict:
    """Update the image generation prompt before generating the image."""
    run = pipeline_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    prompt = (body.get("image_prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="image_prompt must not be empty")
    run.image_prompt = prompt
    pipeline_store.set(run)
    return {"ok": True}


# Stages that need to be replayed when a client reconnects
_REPLAY_STAGE_MAP: dict[PipelineStage, tuple[str, str, str]] = {
    PipelineStage.AWAITING_SCRIPT_APPROVAL: (
        "awaiting_script_approval", "awaiting_approval", "Script ready for review."
    ),
    PipelineStage.AWAITING_AUDIO_APPROVAL: (
        "awaiting_audio_approval", "awaiting_approval", "Audio ready for review."
    ),
    PipelineStage.AWAITING_IMAGE_PROMPT_APPROVAL: (
        "awaiting_image_prompt_approval", "awaiting_approval", "Review image prompt and YouTube metadata."
    ),
    PipelineStage.AWAITING_IMAGE_APPROVAL: (
        "awaiting_image_approval", "awaiting_approval", "Image ready for review."
    ),
    PipelineStage.COMPLETE: ("complete", "complete", "Video production complete!"),
}


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: UUID, api_key: str = Depends(verify_api_key)):
    """SSE stream of pipeline stage events."""
    run = pipeline_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()

    # Capture stage at connect time so the closure is stable
    current_stage = run.stage
    current_error = run.error

    async def generator():
        # Replay current state so reconnecting clients see the right panel immediately.
        if current_stage in _REPLAY_STAGE_MAP:
            stage_val, status_val, msg_val = _REPLAY_STAGE_MAP[current_stage]
            synthetic = PipelineStageEvent(
                run_id=str(run_id), stage=stage_val, status=status_val, message=msg_val
            )
            yield {"data": synthetic.model_dump_json(), "event": "pipeline_event"}
            if current_stage == PipelineStage.COMPLETE:
                return  # terminal — nothing more to stream
        elif current_stage == PipelineStage.FAILED:
            synthetic = PipelineStageEvent(
                run_id=str(run_id), stage="failed", status="failed",
                message=current_error or "Pipeline failed"
            )
            yield {"data": synthetic.model_dump_json(), "event": "pipeline_event"}
            return  # terminal

        q = _event_queues[run_id]
        while True:
            event = await q.get()
            if event is None:
                break
            yield {"data": event.model_dump_json(), "event": "pipeline_event"}

    return EventSourceResponse(generator())


@router.post("/runs/{run_id}/approve", dependencies=[Depends(verify_api_key)])
async def approve_stage(run_id: UUID, background_tasks: BackgroundTasks) -> dict:
    run = pipeline_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    next_task = _APPROVE_MAP.get(run.stage)
    if not next_task:
        raise HTTPException(status_code=409, detail=f"Run is not awaiting approval (current stage: {run.stage.value})")
    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()
    background_tasks.add_task(next_task, run_id)
    return {"status": "approved", "run_id": str(run_id)}


@router.post("/runs/{run_id}/rerun/{stage}", dependencies=[Depends(verify_api_key)])
async def rerun_stage(run_id: UUID, stage: str, background_tasks: BackgroundTasks) -> dict:
    run = pipeline_store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if stage not in _RERUN_TASK:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage!r}")

    # Check preconditions
    for required_attr in _RERUN_REQUIRES.get(stage, []):
        val = getattr(run, required_attr, None)
        if val is None:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot rerun '{stage}': '{required_attr}' is not yet available",
            )

    # Clear downstream artefacts
    for attr in _RERUN_CLEARS.get(stage, []):
        if hasattr(run, attr):
            object.__setattr__(run, attr, None)
    pipeline_store.set(run)

    # Reset SSE queue
    _event_queues[run_id] = asyncio.Queue()
    background_tasks.add_task(_RERUN_TASK[stage], run_id)
    return {"status": "rerunning", "stage": stage, "run_id": str(run_id)}


@router.get("/runs/{run_id}/audio", dependencies=[Depends(verify_api_key)])
async def get_audio(run_id: UUID):
    run = pipeline_store.get(run_id)
    if not run or not run.audio_path or not run.audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not yet generated")
    return FileResponse(str(run.audio_path), media_type="audio/mpeg")


@router.get("/runs/{run_id}/image", dependencies=[Depends(verify_api_key)])
async def get_image(run_id: UUID):
    run = pipeline_store.get(run_id)
    if not run or not run.image_path or not run.image_path.exists():
        raise HTTPException(status_code=404, detail="Image not yet generated")
    return FileResponse(str(run.image_path), media_type="image/png")


@router.get("/runs/{run_id}/video", dependencies=[Depends(verify_api_key)])
async def get_video(run_id: UUID):
    run = pipeline_store.get(run_id)
    if not run or not run.video_path or not run.video_path.exists():
        raise HTTPException(status_code=404, detail="Video not yet generated")
    return FileResponse(
        str(run.video_path),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="video.mp4"'},
    )


# Registry endpoints for form dropdowns
@router.get("/styles", dependencies=[Depends(verify_api_key)])
async def list_styles() -> list[dict]:
    return [{"key": s.key, "label": s.label, "description": s.description} for s in STYLE_REGISTRY.values()]


@router.get("/durations", dependencies=[Depends(verify_api_key)])
async def list_durations() -> list[dict]:
    return [{"key": d.key, "label": d.label, "target_minutes": d.target_minutes} for d in DURATION_REGISTRY.values()]

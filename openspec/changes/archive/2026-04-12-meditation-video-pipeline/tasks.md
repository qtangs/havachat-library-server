## 1. Document existing models (notion_audio.py)

- [x] 1.1 Add module-level docstring to `src/models/notion_audio.py`
- [x] 1.2 Add class docstrings to `AudioContentStatus`, `ContentMetadata`, `ProcessingResult`, `BatchProcessingSummary`, `AudioProcessorConfig`
- [x] 1.3 Add method docstrings to all public methods: `validate_tag_format`, `tags_as_string`, `__str__`, `success_rate`, `meets_success_criteria`, `validate_storage_path`, `from_env`
- [x] 1.4 Add `description=` to all `Field()` calls that lack one
- [x] 1.5 Add `READY_FOR_VIDEO = "Ready for Video"` and `VIDEO_COMPLETED = "Video Completed"` to `AudioContentStatus`

## 2. Extend AudioProcessorConfig for video pipeline

- [x] 2.1 Add `default_voice_id: str = "7AvtJrjTNyBhBxEvNPIZ"` field with description (ElevenLabs Rhythm)
- [x] 2.2 Add `image_backend: Literal["google", "runpod"] = "google"` field
- [x] 2.3 Add `image_quality: Literal["nano", "pro"] = "nano"` field
- [x] 2.4 Add `ffmpeg_path: str = "ffmpeg"` field
- [x] 2.5 Add `video_output_path: Optional[Path]` with validator defaulting to `storage_path / "videos"`
- [x] 2.6 Add `produce_shorts: bool = False` and `enable_karaoke: bool = False` fields
- [x] 2.7 Update `from_env()` to read `DEFAULT_VOICE_ID`, `IMAGE_BACKEND`, `IMAGE_QUALITY`, `FFMPEG_PATH`, `PRODUCE_SHORTS`, `ENABLE_KARAOKE`

## 3. Meditation script models

- [x] 3.1 Create `src/models/meditation_script.py`
- [x] 3.2 Define `MeditationDuration` dataclass/model with `key: str`, `label: str`, `target_minutes: float`, `word_count: int` and a `DURATION_REGISTRY: dict[str, MeditationDuration]` pre-populated with all 8 defaults
- [x] 3.3 Define `MeditationStyle` dataclass/model with `key: str`, `label: str`, `description: str`, `image_prompt_template: str` and a `STYLE_REGISTRY: dict[str, MeditationStyle]` pre-populated with all 8 defaults (each with a suitable `image_prompt_template`)
- [x] 3.4 Define `MeditationScript` Pydantic model with `title: str`, `style_key: str`, `duration_key: str`, `word_count: int`, `body: str`
- [x] 3.5 Define `ScriptSegment` model: `text: str`, `pause_after_seconds: Optional[int]`
- [x] 3.6 Define `ScriptGenerationError` and `ScriptParseError` exception classes
- [x] 3.7 Implement `MeditationScriptParser.parse(body: str) -> list[ScriptSegment]` using regex `\[pause (\d+) seconds?\]`; validate pause values are positive integers

## 4. Video production models

- [x] 4.1 Create `src/models/video_production.py`
- [x] 4.2 Define `VideoFormat` enum: `LONG_FORM`, `SHORTS`
- [x] 4.3 Define `VideoResolution` model with `width: int`, `height: int` and `classmethod from_format(fmt: VideoFormat) -> VideoResolution` (LONG_FORM→1920×1080, SHORTS→1080×1920)
- [x] 4.4 Define `VideoCompositionConfig` Pydantic model: `audio_path: Path`, `image_path: Path`, `output_path: Path`, `video_format: VideoFormat`, `transcript: Optional[Transcript]`, `script_segments: Optional[list[tuple[Path, Optional[int]]]]`, `enable_karaoke: bool = False`, `fade_in_seconds: float = 2.0`, `fade_out_seconds: float = 2.0`, `title_card_text: Optional[str]`, `title_card_duration_seconds: float = 5.0`, `title_card_font_size: int = 64`, `title_card_color: str = "white"`
- [x] 4.5 Define `VideoProductionResult` Pydantic model: `output_path: Path`, `duration_seconds: float`, `file_size_bytes: int`, `video_format: VideoFormat`, `resolution: VideoResolution`, `processing_time_seconds: float`
- [x] 4.6 Define `VideoProductionBatchRequest` Pydantic model: `items: list[VideoProductionItem]`, `voice_id: Optional[str]`, `style_key: str`, `duration_key: str`, `video_format: VideoFormat`, `image_backend: Optional[str]`, `image_quality: Optional[str]`, `produce_shorts: bool = False`, `enable_karaoke: bool = False`
- [x] 4.7 Define `VideoProductionItem` model: `title: str`, `custom_instructions: Optional[str]`, with `notion_record_id: Optional[str]` populated after Notion creation
- [x] 4.8 Define `VideoCompositionError` exception class

## 5. Meditation script generator service

- [x] 5.1 Create `src/services/meditation_script_generator.py`
- [x] 5.2 Define `MeditationScriptGeneratorConfig` with `llm_backend: Literal["claude", "gpt4o"]`, `claude_api_key: Optional[str]`, `openai_api_key: Optional[str]`, `max_retries: int = 3`
- [x] 5.3 Implement `_build_prompt(style: MeditationStyle, duration: MeditationDuration) -> str` using style description, word count target, `[pause X seconds]` format instructions, and JSON schema
- [x] 5.4 Implement `_call_claude(prompt: str) -> dict` via Anthropic SDK with tool-use JSON enforcement
- [x] 5.5 Implement `_call_gpt4o(prompt: str) -> dict` via OpenAI SDK with `response_format={"type": "json_object"}`
- [x] 5.6 Implement `_parse_and_validate(raw: dict) -> MeditationScript` constructing and validating the Pydantic model
- [x] 5.7 Implement `async generate(style_key: str, duration_key: str) -> MeditationScript` with retry loop raising `ScriptGenerationError` after `max_retries`

## 6. Background image generator service

- [x] 6.1 Create `src/services/background_image_generator.py`
- [x] 6.2 Define `BackgroundImage` Pydantic model: `path: Path`, `width: int`, `height: int`, `style_key: str`, `backend_used: str`
- [x] 6.3 Define `ImageBackend` protocol: `async def generate(prompt: str, video_format: VideoFormat, seed: int) -> Path`
- [x] 6.4 Implement `GeminiImageBackend(ImageBackend)`: init validates `GOOGLE_GENERATIVE_AI_API_KEY`; `generate()` calls `google.genai.Client().models.generate_content()` with model `gemini-3.1-flash-image-preview` (nano) or `gemini-3-pro-image-preview` (pro); saves first `inline_data` part via `part.as_image().save()`
- [x] 6.5 Implement `RunpodImageBackend(ImageBackend)`: init validates `RUNPOD_API_KEY`; `generate()` POSTs to `https://api.runpod.ai/v2/z-image-turbo/runsync` with `input.size` mapped from `VideoFormat` (LONG_FORM→`"1280*720"`, SHORTS→`"720*1280"`); downloads image from `output.image_url` immediately
- [x] 6.6 Implement `BackgroundImageGenerator.__init__` selecting backend from `image_backend` config; raise `EnvironmentError` if required credentials missing
- [x] 6.7 Implement cache key as `sha256(style_key + video_format + str(seed))` + `.png`; cache directory `<storage_path>/image_cache/`
- [x] 6.8 Implement `async generate(style_key: str, video_format: VideoFormat, seed: int = -1) -> BackgroundImage` with cache check → backend call → cache write

## 7. Video composer service

- [x] 7.1 Create `src/services/video_composer.py`
- [x] 7.2 Implement `KaraokeRenderer.render(transcript: Transcript, output_path: Path)` converting `TranscriptWord` start/end times to an ASS file with `\k` tags per word
- [x] 7.3 Implement `VideoComposer.__init__` checking `shutil.which(config.ffmpeg_path)`, raising `RuntimeError("ffmpeg not found on PATH")` if absent
- [x] 7.4 Implement `_measure_audio_duration(path: Path) -> float` via `ffmpeg.probe()`
- [x] 7.5 Implement `_stitch_audio_segments(segments: list[tuple[Path, Optional[int]]], output_path: Path)` using FFmpeg concat demuxer with generated silence `.wav` files for pauses
- [x] 7.6 Implement `_build_ffmpeg_pipeline(config: VideoCompositionConfig) -> ffmpeg.Stream`: loop image, scale to target resolution, merge stitched audio, apply fade in/out, optionally burn ASS subtitles, optionally add drawtext title card
- [x] 7.7 Implement Shorts guard: raise `VideoCompositionError` if `video_format == SHORTS` and final audio > 60 s
- [x] 7.8 Implement `async compose(config: VideoCompositionConfig) -> VideoProductionResult` running the pipeline and populating result model

## 8. Video production orchestrator

- [x] 8.1 Create `src/services/video_production_orchestrator.py`
- [x] 8.2 Implement `_create_notion_records(items: list[VideoProductionItem]) -> list[VideoProductionItem]` — creates one Notion Audio Content record per item, sets status `PROCESSING`, stores `notion_record_id` on each item
- [x] 8.3 Implement `_process_item(item, config) -> VideoProductionResult` — generates script → parses segments → generates audio per segment + silence stitching → generates background image → composes video (+ Shorts variant if `produce_shorts`)
- [x] 8.4 Implement `async run_batch(request: VideoProductionBatchRequest) -> list[VideoProductionResult]` — creates Notion records first, then fans out `_process_item` for each, updates Notion to `VIDEO_COMPLETED` on success or `FAILED` on error
- [x] 8.5 Resolve effective `voice_id` per batch: use `request.voice_id` if set, else `config.default_voice_id`

## 9. Pipeline stage state model

- [x] 9.1 Create `src/models/pipeline_run.py`
- [x] 9.2 Define `PipelineStage` enum: `IDLE`, `SCRIPT`, `AWAITING_SCRIPT_APPROVAL`, `AUDIO`, `AWAITING_AUDIO_APPROVAL`, `IMAGE`, `AWAITING_IMAGE_APPROVAL`, `VIDEO`, `COMPLETE`, `FAILED`
- [x] 9.3 Define `PipelineRun` Pydantic model: `run_id: UUID`, `config: VideoProductionBatchRequest`, `stage: PipelineStage`, `script: Optional[MeditationScript]`, `audio_path: Optional[Path]`, `image_path: Optional[Path]`, `video_path: Optional[Path]`, `error: Optional[str]`
- [x] 9.4 Define `PipelineStore` as a simple in-memory dict `dict[UUID, PipelineRun]` with thread-safe get/set helpers
- [x] 9.5 Define `PipelineStageEvent` model: `run_id: str`, `stage: str`, `status: Literal["running", "awaiting_approval", "complete", "failed"]`, `message: Optional[str]` — used as SSE payload

## 10. Pipeline API routes

- [x] 10.1 Create `src/api/routes/pipeline.py` FastAPI router with prefix `/pipeline`
- [x] 10.2 Implement `POST /pipeline/runs` — validates request, creates `PipelineRun` in `IDLE`, launches background task to run script stage, returns `{run_id}`
- [x] 10.3 Implement `GET /pipeline/runs/{run_id}` — returns current `PipelineRun` state (HTTP 404 if unknown)
- [x] 10.4 Implement `GET /pipeline/runs/{run_id}/events` — SSE endpoint using `sse-starlette`; yields `PipelineStageEvent` objects as pipeline advances; keeps connection open until `COMPLETE` or `FAILED`
- [x] 10.5 Implement `POST /pipeline/runs/{run_id}/approve` — advances run past current `AWAITING_*` stage, launching the next stage as a background task; HTTP 409 if not in an awaiting stage
- [x] 10.6 Implement `POST /pipeline/runs/{run_id}/rerun/{stage}` — validates stage is rerunnable (has prior output), clears downstream artefacts, re-launches that stage; HTTP 409 if precondition not met
- [x] 10.7 Implement `GET /pipeline/runs/{run_id}/audio` — streams audio file with `Content-Type: audio/mpeg`; HTTP 404 if not yet generated
- [x] 10.8 Implement `GET /pipeline/runs/{run_id}/image` — serves PNG with `Content-Type: image/png`; HTTP 404 if not yet generated
- [x] 10.9 Implement `GET /pipeline/runs/{run_id}/video` — serves MP4 with `Content-Type: video/mp4` as attachment; HTTP 404 if not yet generated
- [x] 10.10 Register `pipeline` router in `src/api/main.py`

## 11. Pipeline UI HTML page

- [x] 11.1 Create `src/api/routes/pipeline_ui.py` — FastAPI router serving `GET /pipeline/` without API key auth; returns `FileResponse` to `src/static/pipeline/index.html`
- [x] 11.2 Create `src/static/pipeline/` directory
- [x] 11.3 Create `src/static/pipeline/index.html` — single HTML file with embedded CSS and `<script src="app.js">`; mount `StaticFiles` in main app for `/pipeline/static/`
- [x] 11.4 Create `src/static/pipeline/app.js` — vanilla JS, no framework
- [x] 11.5 Implement **Settings panel**: text input for API key stored in `localStorage`; shown on first load if no key found
- [x] 11.6 Implement **Run creation form**: style dropdown (fetched from `GET /pipeline/styles`), duration dropdown (fetched from `GET /pipeline/durations`), N videos input, voice ID input (default pre-filled), image backend/quality selects, Shorts toggle, karaoke toggle; Submit → `POST /pipeline/runs`
- [x] 11.7 Add `GET /pipeline/styles` and `GET /pipeline/durations` endpoints returning registry keys+labels; used to populate form dropdowns
- [x] 11.8 Implement **Stage progress timeline**: horizontal or vertical stepper showing Script → Audio → Image → Video stages with running / awaiting / complete / failed states driven by SSE
- [x] 11.9 Implement **Script approval panel**: rendered at `AWAITING_SCRIPT_APPROVAL`; displays script text in a `<pre>` block with `[pause X seconds]` markers highlighted in a distinct colour; Approve and Rerun Script buttons
- [x] 11.10 Implement **Audio approval panel**: rendered at `AWAITING_AUDIO_APPROVAL`; shows `<audio controls src="/pipeline/runs/{id}/audio">`; Approve and Rerun Audio buttons
- [x] 11.11 Implement **Image approval panel**: rendered at `AWAITING_IMAGE_APPROVAL`; shows `<img src="/pipeline/runs/{id}/image" style="max-width:100%">`; Approve and Rerun Image buttons
- [x] 11.12 Implement **Video complete panel**: rendered at `COMPLETE`; shows download link to `/pipeline/runs/{id}/video`; Rerun Video button
- [x] 11.13 Implement **Error panel**: shown on `FAILED` stage event; displays error message with a "Retry from here" button that calls the appropriate rerun endpoint
- [x] 11.14 Implement SSE listener in `app.js`: `new EventSource(url, {headers: ...})` — note browser `EventSource` does not support custom headers natively; implement a `fetchEventSource` polyfill using `fetch` + `ReadableStream` to pass `X-API-Key`

## 12. Dependencies

- [x] 12.1 Add `google-genai` to `requirements.txt` (or `pyproject.toml`)
- [x] 12.2 Add `ffmpeg-python` to requirements
- [x] 12.3 Add `sse-starlette` for SSE support
- [x] 12.4 Verify `requests` or `httpx` is available for RunPod HTTP calls (add if missing)
- [x] 12.5 Verify `anthropic` and `openai` SDK versions; pin minimums if needed
- [x] 12.6 Document new required env vars in `.env.example`: `GOOGLE_GENERATIVE_AI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `RUNPOD_API_KEY`

## 13. Tests

- [x] 13.1 Unit test `DURATION_REGISTRY` has all 8 default entries; `word_count` values in expected range
- [x] 13.2 Unit test `STYLE_REGISTRY` has all 8 defaults; each has non-empty `image_prompt_template`
- [x] 13.3 Unit test `MeditationScriptParser.parse()` for multi-pause, zero-pause, and invalid pause value
- [x] 13.4 Unit test `MeditationScriptGenerator` retry logic (mock LLM to fail twice then succeed)
- [x] 13.5 Unit test `VideoResolution.from_format` for both formats
- [x] 13.6 Unit test `GeminiImageBackend` and `RunpodImageBackend` cache hit/miss (mock HTTP/SDK)
- [x] 13.7 Unit test `RunpodImageBackend` size mapping for both video formats
- [x] 13.8 Unit test `KaraokeRenderer.render()` ASS output has `\k` tags at correct timestamps
- [x] 13.9 Unit test `VideoComposer` FFmpeg-absent init and Shorts 60-second guard
- [x] 13.10 Unit test `VideoProductionOrchestrator` creates Notion records before processing (mock Notion)
- [x] 13.11 Unit test new `AudioContentStatus` values
- [x] 13.12 Unit test `AudioProcessorConfig` default voice, video field defaults, and `from_env()` loading
- [x] 13.13 API test `POST /pipeline/runs` returns `run_id` and creates run in `SCRIPT` stage
- [x] 13.14 API test `POST /pipeline/runs/{id}/approve` on non-awaiting stage returns HTTP 409
- [x] 13.15 API test `POST /pipeline/runs/{id}/rerun/audio` before audio exists returns HTTP 409
- [x] 13.16 API test `GET /pipeline/runs/{id}` for unknown run returns HTTP 404

## Why

The existing Notion audio processor produces high-quality audio with ElevenLabs TTS, but the content pipeline stops there — there is no path from audio to publishable video. Adding a meditation-video pipeline closes the gap: a single batch request creates Notion records automatically, an LLM generates the meditation script, ElevenLabs produces audio with timestamps, an AI image model generates a matching background, and FFmpeg assembles the final video — making the full creation cycle automatable from one API call.

## What Changes

- Add `MeditationScript` Pydantic models with dynamic, config-driven duration presets and meditation styles (not hardcoded enums — easy to extend)
- Extend `notion_audio.py` models with full docstrings and inline type commentary
- Introduce a `VideoProductionRequest` model that describes a batch of 1..N videos to produce, with shared config (style, length, voice, image backend) and auto-creates the corresponding Notion records
- Introduce a `MeditationScriptGenerator` service that uses an LLM to produce scripts using `[pause X seconds]` markers for deliberate silence
- Introduce a `BackgroundImageGenerator` service that calls Google Gemini image models (Nano Banana 2: `gemini-3.1-flash-image-preview` / Nano Banana Pro: `gemini-3-pro-image-preview`) via the `google-genai` SDK, or Z-Image Turbo (RunPod) as the open-source fallback
- Introduce a `VideoComposer` service that drives FFmpeg to combine audio + background into YouTube-ready MP4s (16:9 long-form, 9:16 Shorts), with karaoke-style subtitle overlays derived from ElevenLabs word-level transcripts
- Extend `AudioProcessorConfig` with video pipeline fields (image model, FFmpeg path, output resolutions, Shorts flag, default voice)
- Add `VideoProcessingResult` and `VideoProductionSummary` models mirroring existing batch-processing patterns
- Update `AudioContentStatus` enum with video-pipeline states (`READY_FOR_VIDEO`, `VIDEO_COMPLETED`)

## Capabilities

### New Capabilities

- `meditation-script`: LLM-driven script generation with dynamic duration presets (Shorts <1 m, 5 m, 10 m, 20 m, 30 m, 40 m, 50 m, 60 m) and dynamic meditation styles (Plum Village, Plum Village Total Relaxation, Body Scan, Vipassana, Loving-Kindness, Yoga Nidra, Guided Imagery, Mantra-Based), using `[pause X seconds]` silence markers
- `background-image-generation`: AI image generation via Google Gemini image models (`gemini-3.1-flash-image-preview` / `gemini-3-pro-image-preview`) or Z-Image Turbo (RunPod), producing style-keyed backgrounds at correct YouTube dimensions
- `video-composition`: FFmpeg-based assembly of audio + background into long-form (16:9) and Shorts (9:16) MP4 files, with karaoke subtitle track from word-level ElevenLabs transcripts and optional title card overlay
- `video-production-batch`: Batch request model that auto-creates Notion records, then fans out to script → audio → image → video for each item
- `pipeline-ui`: Browser-based UI (served by the existing FastAPI app) for running video production pipelines with manual approval gates between stages, inline playback/preview of audio and images, and per-stage rerun capability

### Modified Capabilities

- `notion-audio-processor`: `AudioContentStatus`, `AudioProcessorConfig`, and `ProcessingResult` gain video-pipeline states, video config fields, default voice (`7AvtJrjTNyBhBxEvNPIZ` Rhythm), and per-run voice override; existing audio fields unchanged (**non-breaking extension**)

## Impact

- **src/models/notion_audio.py** — extended with new enums, models, and docstrings
- **src/models/meditation_script.py** — new file: script models, dynamic duration/style registries
- **src/models/video_production.py** — new file: video result and batch request models
- **src/services/meditation_script_generator.py** — new LLM service
- **src/services/background_image_generator.py** — new image service (Gemini genai SDK + RunPod HTTP)
- **src/services/video_composer.py** — new FFmpeg wrapper with subtitle burn-in
- **src/api/routes/pipeline_ui.py** — new FastAPI router serving the UI HTML + SSE/WebSocket progress stream
- **src/api/routes/pipeline.py** — new FastAPI router with REST endpoints for each pipeline stage and rerun actions
- **src/static/pipeline/** — single-page HTML + vanilla JS + CSS (no build step required)
- **src/datatypes/transcript.py** — read-only dependency (word timestamps feed karaoke renderer)
- **Dependencies**: `google-genai` (Gemini image), `httpx` or `requests` (RunPod), `ffmpeg-python`, Pillow; `anthropic`/`openai` already present; `sse-starlette` for server-sent events
- **Env vars**: `GOOGLE_GENERATIVE_AI_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `RUNPOD_API_KEY` (open-source backend), `ELEVENLABS_API_KEY` (existing)
- **Notion DB**: audio content records gain "Video Status" and "Voice ID" properties; non-breaking addition

## Context

The havachat-library-server runs a Notion-driven audio production pipeline: it reads Audio Content records from Notion, generates TTS audio via ElevenLabs, and writes results (including word-level transcripts in `TranscriptSegment`/`TranscriptWord` format) back. The Pydantic models in `src/models/notion_audio.py` define the shape of that workflow but are sparsely documented.

This change documents those models, then designs four new services — script generation, image generation, video composition, and batch orchestration — that form a complete chain: **batch request → auto-create Notion records → meditation script → ElevenLabs audio + transcript → AI background image → FFmpeg video (long-form + Shorts with karaoke) → Notion update**.

Key environment facts:
- Google AI: `GOOGLE_GENERATIVE_AI_API_KEY` + `GOOGLE_CLOUD_PROJECT`; client via `google.genai`
- Open-source image: Z-Image Turbo at `https://api.runpod.ai/v2/z-image-turbo/runsync`; auth via `RUNPOD_API_KEY`
- Default ElevenLabs voice: Rhythm `7AvtJrjTNyBhBxEvNPIZ` (overrideable per run)
- Silence markers in scripts: `[pause X seconds]` (integer X)

## Goals / Non-Goals

**Goals:**
- Fully document `notion_audio.py` models with docstrings and field descriptions
- Define Pydantic models for meditation scripts with **dynamic** (not hardcoded) duration and style registries
- Design `MeditationScriptGenerator`, `BackgroundImageGenerator`, `VideoComposer`, and `VideoProductionOrchestrator` services with clear contracts
- Auto-create Notion records from a batch `VideoProductionRequest` before processing begins
- Burn karaoke subtitles into Shorts (and optionally long-form) from ElevenLabs word-level transcripts
- Support per-run voice ID override (default Rhythm `7AvtJrjTNyBhBxEvNPIZ`)
- Keep all services independently testable with no circular dependencies
- Preserve 100% backwards-compatibility with the existing audio-only workflow
- Provide a browser UI (no build step, no npm) for running pipelines with pause gates after script, audio, and image stages
- Support per-stage rerun without restarting the whole pipeline; invalidate downstream artefacts on rerun

**Non-Goals:**
- YouTube Data API upload automation
- Real-time streaming or live composition
- Multi-language script generation in this phase (English-first)
- Mobile or web front-ends

## Decisions

### D1: Dynamic Duration and Style Registries
**Decision:** `MeditationDuration` and `MeditationStyle` are NOT Python `Enum`s. Instead, they are Pydantic models stored in module-level registries (dicts) that can be extended at runtime or by config. Each `MeditationDuration` carries `label`, `target_minutes`, and `word_count` (computed at 120 wpm). Each `MeditationStyle` carries `label`, `description`, and `image_prompt_template`.

**Rationale:** The user explicitly asked for these to be easy to extend in future without code changes. Enums require code edits and redeploys; registry dicts can be populated from config files or a Notion database.

**Alternatives considered:**
- Python Enum — simpler but rigid; adding a new style requires a code change and redeploy.
- Database-driven — more complex; overkill for v1.

---

### D2: Batch Request Auto-Creates Notion Records
**Decision:** `VideoProductionOrchestrator.run_batch(request: VideoProductionBatchRequest)` creates a Notion Audio Content record for each video item before any processing begins. Items reference their Notion record ID throughout the pipeline for status updates.

**Rationale:** Centralises observability in Notion. Operators can see queued/in-progress/failed items without querying the local filesystem.

**Alternatives considered:**
- Write Notion records only on completion — loses visibility for long-running batches.

---

### D3: Silence Marker Format
**Decision:** Scripts use `[pause X seconds]` (e.g., `[pause 3 seconds]`). The script generator is instructed to use this exact format. The audio assembler converts these markers to ElevenLabs `pause` entries or post-processes by inserting silence via FFmpeg at the corresponding timestamps.

**Rationale:** User-specified format. Consistent with natural language and legible to human reviewers.

**Implementation detail:** The `MeditationScriptParser` utility extracts `(text_segment, pause_duration_s)` tuples. Each text segment is sent to ElevenLabs individually; silence is stitched in post with FFmpeg concat demuxer.

---

### D4: Google Gemini Image Models ("Nano Banana")
**Decision:** `BackgroundImageGenerator` uses `google.genai` SDK with:
- **Nano Banana 2** (default): `model="gemini-3.1-flash-image-preview"` — fast, cost-efficient
- **Nano Banana Pro** (opt-in): `model="gemini-3-pro-image-preview"` — high-fidelity, complex instructions

Auth: `GOOGLE_GENERATIVE_AI_API_KEY` env var (SDK picks this up automatically).

**Alternatives considered:**
- `google-cloud-aiplatform` (Imagen 3) — different API surface, Imagen models, not Gemini; user explicitly specified Gemini models.
- DALL-E 3 — higher cost, less controllable for meditative aesthetics.

---

### D5: Z-Image Turbo (RunPod) as Open-Source Backend
**Decision:** When `image_backend = "runpod"`, the service POSTs to `https://api.runpod.ai/v2/z-image-turbo/runsync` with `RUNPOD_API_KEY`. Size parameter maps from `VideoFormat`: long-form → `"1280*720"`, Shorts → `"720*1280"`. Images are downloaded from the returned `output.image_url` (expiry: 7 days) and saved locally immediately.

**Rationale:** No local GPU required; $0.005/image; matches user specification.

---

### D6: Karaoke Subtitles from ElevenLabs Transcripts
**Decision:** Word-level timestamps from the existing `TranscriptWord` model (in `src/datatypes/transcript.py`) are converted to an ASS (Advanced SubStation Alpha) subtitle file by a `KaraokeRenderer` utility. FFmpeg burns the ASS track into the video using the `ass` filter. Active word highlighting is achieved via ASS karaoke tags (`\k`).

**Rationale:** ASS format gives fine-grained per-word timing control; FFmpeg supports it natively without additional libraries.

**Shorts vs long-form:** Karaoke is always enabled for Shorts; optional for long-form (config flag `enable_karaoke`).

---

### D7: Service Layer, Not Processor Integration
**Decision:** Each new capability is a standalone service class with an async method. A new `VideoProductionOrchestrator` composes them. The existing `NotionAudioProcessor` is untouched.

**Rationale:** Single responsibility, independent testability, no forking of the existing audio path.

---

### D8: FFmpeg via `ffmpeg-python` Binding
**Decision:** `VideoComposer` uses `ffmpeg-python` fluent API for the composition pipeline; `ffprobe` for duration measurement. ASS subtitle burn-in uses `ffmpeg.input().video.filter('ass', filename=ass_path)`.

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Gemini image API in preview, may have breaking changes | Pin SDK version; wrap calls behind `BackgroundImageBackend` interface so swapping backend is a one-line config change |
| RunPod image URL expires in 7 days | Download and persist to `<storage_path>/image_cache/` immediately after generation |
| `[pause X seconds]` parsing fails if LLM deviates | Validate with regex `\[pause \d+ seconds?\]` post-generation; retry up to 3× |
| ASS subtitle rendering misaligns if audio stitching shifts timestamps | Re-measure final stitched audio duration with `ffprobe`; offset subtitle timecodes accordingly |
| Batch creates Notion records before knowing if generation will succeed | Mark new records as `PROCESSING`; update to `FAILED` on error with error message in Notion |
| Per-run voice override missing from config | `VideoProductionBatchRequest.voice_id` defaults to `"7AvtJrjTNyBhBxEvNPIZ"` (Rhythm); override applies to entire batch |

### D9: Web UI — FastAPI + Server-Sent Events + Vanilla JS (no build step)
**Decision:** The UI is a single HTML page served at `/pipeline/` by the existing FastAPI app (new router `src/api/routes/pipeline_ui.py`). Static assets (JS, CSS) live in `src/static/pipeline/`. Progress updates stream over **Server-Sent Events** (SSE) via `sse-starlette`. No React/Vue/bundler — vanilla JS only.

**Rationale:** The server is already FastAPI. Avoiding a JS build pipeline keeps setup friction near-zero for a personal tool. SSE is simpler than WebSockets for one-way progress streaming and works natively in all browsers.

**Alternatives considered:**
- React SPA — adds build tooling, npm dependencies, CORS complexity; overkill for a personal tool.
- WebSockets — bidirectional, more complex; SSE is sufficient since UI only needs server → browser updates.
- Separate frontend repo — unnecessary separation for an internal tool.

---

### D10: Pipeline Stage Machine with Pause Gates
**Decision:** Each pipeline run is tracked server-side as a `PipelineRun` object stored in an in-memory dict (keyed by `run_id: UUID`). Runs progress through a `PipelineStage` enum: `IDLE → SCRIPT → AWAITING_SCRIPT_APPROVAL → AUDIO → AWAITING_AUDIO_APPROVAL → IMAGE → AWAITING_IMAGE_APPROVAL → VIDEO → COMPLETE`. The UI sends `POST /pipeline/{run_id}/approve` to advance through an `AWAITING_*` gate, or `POST /pipeline/{run_id}/rerun/{stage}` to re-execute a specific stage.

**Stage outputs persisted per run:**
- `SCRIPT`: `MeditationScript` JSON + rendered text
- `AUDIO`: audio file path (served at `/pipeline/{run_id}/audio`)
- `IMAGE`: image file path (served at `/pipeline/{run_id}/image`)
- `VIDEO`: video file path (served at `/pipeline/{run_id}/video`)

**Rationale:** In-memory state is sufficient for a personal single-user tool. Runs survive the HTTP request lifecycle via async background tasks. Pause gates give the operator full control over quality at each stage without having to restart.

---

### D11: Per-Stage Rerun Actions
**Decision:** `POST /pipeline/{run_id}/rerun/script` discards the current script and regenerates from scratch using the same config. Similarly for `rerun/audio`, `rerun/image`, `rerun/video`. Downstream outputs are invalidated on rerun (e.g., rerunning script also clears audio, image, and video artefacts for that item).

**Rationale:** Operators need granular control — a poor image shouldn't force regenerating script and audio. Downstream invalidation prevents stale artefacts silently flowing into later stages.

---

## Migration Plan

1. **Phase 1 (this change):** Document `notion_audio.py`; add new model files; implement services; no Notion schema change yet.
2. **Phase 2:** Add "Video Status" and "Voice ID" select/text properties to the Notion Audio Content database; update orchestrator to write video results back.
3. **Rollback:** All new services are additive. Removing the new service files reverts to audio-only.

## Open Questions

- **Q1:** Should Shorts be a separate Notion record or a derived output from the long-form record? *(Recommendation: derived output — same record, two output files.)*
- **Q2:** Should karaoke be enabled for long-form by default or opt-in? *(Recommendation: opt-in via `enable_karaoke: bool = False` on `VideoCompositionConfig`.)*
- **Q3:** For Plum Village style, should the bell sound effect be auto-inserted at `[pause X seconds]` markers, or is silence sufficient for v1? *(Recommendation: silence for v1; bell as a future enhancement.)*

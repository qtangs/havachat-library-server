## ADDED Requirements

### Requirement: Pipeline run creation
The UI SHALL expose a form that collects the required configuration to start a production run: style (dropdown from `STYLE_REGISTRY`), duration (dropdown from `DURATION_REGISTRY`), number of videos (1..N), voice ID (pre-filled with default Rhythm, editable), image backend (`google` / `runpod`), image quality (`nano` / `pro`), produce Shorts toggle, enable karaoke toggle. Submitting the form SHALL POST to `POST /pipeline/runs` and return a `run_id`.

#### Scenario: Form submission creates a run
- **WHEN** the user fills the form and clicks "Start"
- **THEN** a `POST /pipeline/runs` request SHALL be sent and the page SHALL transition to the run detail view for the returned `run_id`

#### Scenario: Style and duration dropdowns are populated from registries
- **WHEN** the creation form loads
- **THEN** the style dropdown SHALL contain all keys from `STYLE_REGISTRY` and the duration dropdown all keys from `DURATION_REGISTRY`

---

### Requirement: Real-time progress via Server-Sent Events
`GET /pipeline/runs/{run_id}/events` SHALL be an SSE endpoint that emits events as the pipeline advances. Each event SHALL carry `stage`, `status` (`running` | `awaiting_approval` | `complete` | `failed`), and optional `message`. The UI SHALL listen to this stream and update the stage progress indicator in real time.

#### Scenario: SSE events update UI stage indicators
- **WHEN** the pipeline advances to `AWAITING_SCRIPT_APPROVAL`
- **THEN** the script stage indicator SHALL show "awaiting approval" without a page reload

#### Scenario: SSE stream stays open across stages
- **WHEN** the pipeline moves from script to audio
- **THEN** the same SSE connection SHALL continue delivering events without reconnection

#### Scenario: Failed stage turns indicator red
- **WHEN** a stage emits `status: "failed"` with a message
- **THEN** the UI SHALL display the stage as failed with the error message visible

---

### Requirement: Script approval gate
After script generation the pipeline SHALL pause. The UI SHALL display the full script text in a readable, scrollable panel. The operator SHALL be able to:
- Click **Approve** → `POST /pipeline/runs/{run_id}/approve` to advance to audio generation
- Click **Rerun Script** → `POST /pipeline/runs/{run_id}/rerun/script` to regenerate the script (discards audio, image, video artefacts)

#### Scenario: Script is displayed at approval gate
- **WHEN** the pipeline reaches `AWAITING_SCRIPT_APPROVAL`
- **THEN** the full script body SHALL be rendered in the UI with `[pause X seconds]` markers visually highlighted

#### Scenario: Approve advances to audio stage
- **WHEN** the operator clicks Approve at the script gate
- **THEN** `POST /pipeline/runs/{run_id}/approve` SHALL be called and the pipeline SHALL begin audio generation

#### Scenario: Rerun script regenerates and stays at gate
- **WHEN** the operator clicks Rerun Script
- **THEN** the pipeline SHALL regenerate the script and return to `AWAITING_SCRIPT_APPROVAL` with the new script displayed

#### Scenario: Script rerun invalidates downstream artefacts
- **WHEN** a script rerun is triggered
- **THEN** any previously generated audio, image, and video artefacts for the run SHALL be cleared server-side

---

### Requirement: Audio approval gate
After audio generation the pipeline SHALL pause. The UI SHALL render an HTML `<audio>` player pointing to `GET /pipeline/runs/{run_id}/audio` so the operator can listen before proceeding. Controls:
- **Approve** → advance to image generation
- **Rerun Audio** → regenerate audio only (keeps script, discards image and video)

#### Scenario: Audio player is shown at approval gate
- **WHEN** the pipeline reaches `AWAITING_AUDIO_APPROVAL`
- **THEN** an `<audio controls>` element SHALL appear with `src` pointing to the run's audio endpoint

#### Scenario: Audio streams from server
- **WHEN** the operator presses play in the audio player
- **THEN** `GET /pipeline/runs/{run_id}/audio` SHALL stream the audio file with correct `Content-Type: audio/mpeg`

#### Scenario: Rerun audio keeps script
- **WHEN** the operator clicks Rerun Audio
- **THEN** the existing `MeditationScript` SHALL be preserved; only audio generation SHALL be repeated

#### Scenario: Audio rerun invalidates downstream artefacts
- **WHEN** an audio rerun is triggered
- **THEN** any previously generated image and video artefacts SHALL be cleared

---

### Requirement: Image approval gate
After image generation the pipeline SHALL pause. The UI SHALL display the generated background image inline. Controls:
- **Approve** → advance to video composition
- **Rerun Image** → regenerate image only (keeps script and audio, discards video)

#### Scenario: Image is displayed at approval gate
- **WHEN** the pipeline reaches `AWAITING_IMAGE_APPROVAL`
- **THEN** an `<img>` element SHALL appear with `src` pointing to `GET /pipeline/runs/{run_id}/image`

#### Scenario: Image served from server
- **WHEN** the browser requests the image URL
- **THEN** `GET /pipeline/runs/{run_id}/image` SHALL return the PNG with `Content-Type: image/png`

#### Scenario: Rerun image keeps script and audio
- **WHEN** the operator clicks Rerun Image
- **THEN** script and audio artefacts SHALL be preserved; only image generation SHALL be repeated

#### Scenario: Image rerun invalidates video artefacts
- **WHEN** an image rerun is triggered
- **THEN** any previously generated video artefact SHALL be cleared

---

### Requirement: Video composition and rerun
After video composition the pipeline reaches `COMPLETE`. The UI SHALL show a download link for the video file. The operator SHALL be able to click **Rerun Video** at any point after the image stage to re-compose without regenerating script, audio, or image.

#### Scenario: Download link appears on completion
- **WHEN** the pipeline reaches `COMPLETE`
- **THEN** a download link to `GET /pipeline/runs/{run_id}/video` SHALL appear in the UI

#### Scenario: Rerun video keeps all prior artefacts
- **WHEN** the operator clicks Rerun Video
- **THEN** script, audio, and image artefacts SHALL be preserved; only FFmpeg composition SHALL be repeated

---

### Requirement: Pipeline stage REST API
The FastAPI app SHALL expose the following endpoints (all require the existing `X-API-Key` header):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/pipeline/runs` | Create a new run, returns `{run_id}` |
| `GET` | `/pipeline/runs/{run_id}` | Return current run state and stage |
| `GET` | `/pipeline/runs/{run_id}/events` | SSE stream of stage events |
| `POST` | `/pipeline/runs/{run_id}/approve` | Advance past current `AWAITING_*` gate |
| `POST` | `/pipeline/runs/{run_id}/rerun/{stage}` | Rerun `script` | `audio` | `image` | `video` |
| `GET` | `/pipeline/runs/{run_id}/audio` | Stream the generated audio file |
| `GET` | `/pipeline/runs/{run_id}/image` | Serve the generated background image |
| `GET` | `/pipeline/runs/{run_id}/video` | Serve the composed video file |
| `GET` | `/pipeline/` | Serve the single-page HTML UI |

#### Scenario: Unknown run_id returns 404
- **WHEN** any endpoint is called with a `run_id` not in the in-memory store
- **THEN** the response SHALL be HTTP 404

#### Scenario: Approve on non-awaiting stage returns 409
- **WHEN** `POST /pipeline/runs/{run_id}/approve` is called and the run is not in an `AWAITING_*` stage
- **THEN** the response SHALL be HTTP 409 Conflict

#### Scenario: Rerun on unavailable stage returns 409
- **WHEN** `POST /pipeline/runs/{run_id}/rerun/audio` is called before audio has been generated
- **THEN** the response SHALL be HTTP 409 Conflict

---

### Requirement: UI served without authentication for local use
The UI HTML page (`GET /pipeline/`) SHALL be served without requiring the `X-API-Key` header so it can be opened directly in a browser during local development. The API endpoints it calls SHALL still enforce the key.

#### Scenario: UI page loads without API key
- **WHEN** a browser navigates to `http://localhost:8000/pipeline/`
- **THEN** the HTML page SHALL be returned with HTTP 200 regardless of whether `X-API-Key` is present

#### Scenario: API calls from UI use API key stored in localStorage
- **WHEN** the UI makes an API call
- **THEN** it SHALL read the key from `localStorage.getItem("api_key")` and include it as `X-API-Key`; a settings panel SHALL allow the user to set this value

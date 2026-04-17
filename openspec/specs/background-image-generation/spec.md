## ADDED Requirements

### Requirement: Style-keyed image prompts from registry
`BackgroundImageGenerator` SHALL derive the image generation prompt from `STYLE_REGISTRY[style_key].image_prompt_template`, substituting `{video_format}` and any other template variables. This means new styles added to the registry automatically get image generation support.

#### Scenario: Plum Village style maps to nature imagery prompt
- **WHEN** an image is requested with style key `plum_village`
- **THEN** the prompt SHALL contain language consistent with serene natural landscapes (forest, water, soft light)

#### Scenario: Yoga Nidra style maps to night/cosmos imagery
- **WHEN** an image is requested with style key `yoga_nidra`
- **THEN** the prompt SHALL reference tranquil dark or night-sky themes

---

### Requirement: Google Gemini image backend ("Nano Banana")
The system SHALL support two Gemini image generation tiers via the `google.genai` SDK, authenticated with `GOOGLE_GENERATIVE_AI_API_KEY`:
- **Nano Banana 2** (default, `image_quality: "nano"`): model `gemini-3.1-flash-image-preview`
- **Nano Banana Pro** (`image_quality: "pro"`): model `gemini-3-pro-image-preview`

The response SHALL be parsed by iterating `response.parts`; the first part with `inline_data` SHALL be saved as PNG via `part.as_image()`.

#### Scenario: Nano Banana 2 is default model
- **WHEN** `image_quality` is `"nano"` or not set
- **THEN** the SDK call SHALL use model `"gemini-3.1-flash-image-preview"`

#### Scenario: Nano Banana Pro activates on config
- **WHEN** `image_quality` is `"pro"`
- **THEN** the SDK call SHALL use model `"gemini-3-pro-image-preview"`

#### Scenario: Missing API key raises at init
- **WHEN** `GOOGLE_GENERATIVE_AI_API_KEY` is not set and `image_backend` is `"google"`
- **THEN** `BackgroundImageGenerator.__init__` SHALL raise `EnvironmentError`

---

### Requirement: Z-Image Turbo backend (RunPod)
When `image_backend` is `"runpod"`, the system SHALL POST to `https://api.runpod.ai/v2/z-image-turbo/runsync` with `Authorization: Bearer $RUNPOD_API_KEY`. The `input.size` parameter SHALL map from `VideoFormat`: `LONG_FORM` → `"1280*720"`, `SHORTS` → `"720*1280"`. The response `output.image_url` SHALL be downloaded and persisted to the local image cache immediately (URL expires in 7 days).

#### Scenario: RunPod backend fires correct endpoint
- **WHEN** `image_backend` is `"runpod"` and `generate()` is called
- **THEN** the HTTP POST SHALL target `https://api.runpod.ai/v2/z-image-turbo/runsync` with the correct `Authorization` header

#### Scenario: Long-form maps to landscape size
- **WHEN** `video_format` is `LONG_FORM` and backend is `"runpod"`
- **THEN** the request `input.size` SHALL be `"1280*720"`

#### Scenario: Shorts maps to portrait size
- **WHEN** `video_format` is `SHORTS` and backend is `"runpod"`
- **THEN** the request `input.size` SHALL be `"720*1280"`

#### Scenario: Image URL is downloaded immediately
- **WHEN** RunPod returns `output.image_url`
- **THEN** the generator SHALL download the image bytes and write them to the cache path before returning `BackgroundImage`

---

### Requirement: Backend abstraction interface
Both Gemini and RunPod backends SHALL implement the same `ImageBackend` protocol with a single async method `generate(prompt: str, video_format: VideoFormat, seed: int) -> Path`. `BackgroundImageGenerator` SHALL delegate to the active backend via this protocol, making the backend swappable with no changes to call sites.

#### Scenario: Backend interface is uniform
- **WHEN** `BackgroundImageGenerator.generate()` is called
- **THEN** it SHALL return a `BackgroundImage` model regardless of which backend is active

---

### Requirement: Image caching by content hash
Generated images SHALL be cached under `<storage_path>/image_cache/` using a filename derived from `sha256(style_key + video_format + str(seed))`. On cache hit the backend SHALL NOT be called.

#### Scenario: Cache hit skips backend
- **WHEN** a matching cached PNG exists
- **THEN** `generate()` SHALL return it immediately without calling Gemini or RunPod

#### Scenario: Cache miss triggers generation and save
- **WHEN** no cached file matches the hash
- **THEN** the backend SHALL be called and the result saved as PNG before returning

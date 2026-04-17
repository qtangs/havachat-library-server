## ADDED Requirements

### Requirement: Video pipeline status values
`AudioContentStatus` SHALL include `READY_FOR_VIDEO = "Ready for Video"` and `VIDEO_COMPLETED = "Video Completed"`.

#### Scenario: READY_FOR_VIDEO parses correctly
- **WHEN** `AudioContentStatus("Ready for Video")` is called
- **THEN** it SHALL equal `AudioContentStatus.READY_FOR_VIDEO` without raising

#### Scenario: VIDEO_COMPLETED parses correctly
- **WHEN** `AudioContentStatus("Video Completed")` is called
- **THEN** it SHALL equal `AudioContentStatus.VIDEO_COMPLETED` without raising

---

### Requirement: Default and per-run voice configuration
`AudioProcessorConfig` SHALL add a `default_voice_id: str` field with default value `"7AvtJrjTNyBhBxEvNPIZ"` (ElevenLabs Rhythm voice). `VideoProductionBatchRequest` SHALL include an optional `voice_id: Optional[str]` that, when set, overrides `default_voice_id` for the entire batch.

#### Scenario: Default voice is Rhythm
- **WHEN** `AudioProcessorConfig` is instantiated without `default_voice_id`
- **THEN** `config.default_voice_id` SHALL equal `"7AvtJrjTNyBhBxEvNPIZ"`

#### Scenario: Per-run voice override is applied
- **WHEN** `VideoProductionBatchRequest.voice_id` is set to a non-default value
- **THEN** all audio generation in the batch SHALL use that voice ID

#### Scenario: voice_id loads from env
- **WHEN** `AudioProcessorConfig.from_env()` is called and `DEFAULT_VOICE_ID` is set
- **THEN** `config.default_voice_id` SHALL equal the env value

---

### Requirement: Video pipeline configuration fields
`AudioProcessorConfig` SHALL add optional fields: `image_backend: Literal["google", "runpod"] = "google"`, `image_quality: Literal["nano", "pro"] = "nano"`, `ffmpeg_path: str = "ffmpeg"`, `video_output_path: Optional[Path]` (defaults to `<storage_path>/videos/`), `produce_shorts: bool = False`, `enable_karaoke: bool = False`.

#### Scenario: Video fields default correctly
- **WHEN** `AudioProcessorConfig` is instantiated with only required audio fields
- **THEN** `image_backend` SHALL be `"google"`, `image_quality` SHALL be `"nano"`, `produce_shorts` SHALL be `False`, `enable_karaoke` SHALL be `False`

#### Scenario: Video output path defaults to storage subdirectory
- **WHEN** `video_output_path` is not set
- **THEN** `config.video_output_path` SHALL resolve to `config.storage_path / "videos"`

#### Scenario: Video fields load from environment
- **WHEN** `from_env()` is called with `IMAGE_BACKEND=runpod` and `PRODUCE_SHORTS=true`
- **THEN** `config.image_backend` SHALL be `"runpod"` and `config.produce_shorts` SHALL be `True`

---

### Requirement: Batch request auto-creates Notion records
`VideoProductionOrchestrator.run_batch(request: VideoProductionBatchRequest)` SHALL create a Notion Audio Content record for each item in the batch before processing begins, setting status to `PROCESSING`. Each item SHALL carry its `notion_record_id` through the pipeline for status updates.

#### Scenario: Notion records created before processing
- **WHEN** `run_batch()` is called with N items
- **THEN** N new Notion records SHALL be created with status `PROCESSING` before any LLM or audio calls are made

#### Scenario: Failed item updates Notion record to FAILED
- **WHEN** any stage of processing raises an exception for an item
- **THEN** the item's Notion record status SHALL be updated to `FAILED` with the error message

#### Scenario: Completed item updates Notion record to VIDEO_COMPLETED
- **WHEN** video composition succeeds for an item
- **THEN** the item's Notion record status SHALL be updated to `VIDEO_COMPLETED`

---

### Requirement: notion_audio.py module documentation
All public classes and methods in `src/models/notion_audio.py` SHALL have docstrings. All `pydantic.Field()` calls SHALL include `description=`.

#### Scenario: All classes have docstrings
- **WHEN** `pydoc` is run against `notion_audio`
- **THEN** every class SHALL have a non-empty docstring

#### Scenario: All public methods have docstrings
- **WHEN** `pydoc` is run against `notion_audio`
- **THEN** every public method SHALL have a non-empty docstring

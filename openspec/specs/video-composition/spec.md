## ADDED Requirements

### Requirement: FFmpeg health check at init
`VideoComposer.__init__` SHALL verify that an `ffmpeg` binary is accessible on PATH via `shutil.which`. If not found it SHALL raise `RuntimeError("ffmpeg not found on PATH")`.

#### Scenario: FFmpeg present — init succeeds
- **WHEN** `ffmpeg` is on the system PATH
- **THEN** `VideoComposer.__init__` SHALL complete without error

#### Scenario: FFmpeg absent — init raises
- **WHEN** `ffmpeg` is not on PATH
- **THEN** `VideoComposer.__init__` SHALL raise `RuntimeError` with the string `"ffmpeg not found"`

---

### Requirement: Long-form video composition
`VideoComposer` SHALL produce a 16:9 MP4 (H.264 + AAC) by looping a static background image to match audio duration, with configurable fade-in/fade-out (default 2 s each).

#### Scenario: Output file is created at target path
- **WHEN** `compose()` is called with valid audio and image for `LONG_FORM`
- **THEN** a `.mp4` file SHALL exist at `config.output_path` after completion

#### Scenario: Output duration matches audio
- **WHEN** a long-form video is composed
- **THEN** video duration (per `ffprobe`) SHALL be within ±1 s of the source audio duration

#### Scenario: Output resolution is 1920×1080
- **WHEN** a long-form video is composed
- **THEN** `ffprobe` SHALL report width=1920 and height=1080

---

### Requirement: YouTube Shorts composition
`VideoComposer` SHALL produce a 9:16 MP4 targeting YouTube Shorts. If source audio exceeds 60 s the system SHALL raise `VideoCompositionError` rather than silently truncating.

#### Scenario: Shorts output resolution is 1080×1920
- **WHEN** `compose()` is called with `video_format=SHORTS`
- **THEN** `ffprobe` SHALL report width=1080, height=1920

#### Scenario: Audio over 60 s raises for Shorts
- **WHEN** source audio is >60 s and `video_format` is `SHORTS`
- **THEN** `compose()` SHALL raise `VideoCompositionError` before invoking FFmpeg

---

### Requirement: Karaoke subtitle burn-in from ElevenLabs transcripts
`VideoComposer` SHALL accept an optional `transcript: Transcript` (from `src/datatypes/transcript.py`). When provided, a `KaraokeRenderer` utility SHALL convert `TranscriptWord` start/end timestamps into an ASS subtitle file with per-word `\k` karaoke tags, which is then burned in via FFmpeg's `ass` filter. Karaoke is always applied for Shorts; for long-form it is controlled by `enable_karaoke: bool = False` in `VideoCompositionConfig`.

#### Scenario: Karaoke enabled for Shorts when transcript provided
- **WHEN** `video_format` is `SHORTS` and a `Transcript` is passed
- **THEN** the FFmpeg pipeline SHALL include the `ass` filter pointing to the generated subtitle file

#### Scenario: Karaoke disabled for long-form by default
- **WHEN** `video_format` is `LONG_FORM` and `enable_karaoke` is `False`
- **THEN** the FFmpeg pipeline SHALL NOT include an `ass` filter

#### Scenario: Karaoke enabled for long-form when opted in
- **WHEN** `video_format` is `LONG_FORM`, `enable_karaoke` is `True`, and a `Transcript` is passed
- **THEN** the FFmpeg pipeline SHALL include the `ass` filter

#### Scenario: Missing transcript with karaoke enabled raises
- **WHEN** `enable_karaoke` is `True` or `video_format` is `SHORTS` but `transcript` is `None`
- **THEN** `compose()` SHALL raise `VideoCompositionError("transcript required for karaoke")`

---

### Requirement: Audio stitching for pause markers
When `VideoCompositionConfig.script_segments` is provided (a list of `(audio_path, pause_seconds)` tuples produced by the audio assembler), `VideoComposer` SHALL stitch them into a single audio track using FFmpeg concat demuxer, inserting silent `.wav` segments of the specified duration between spoken parts.

#### Scenario: Pause segments are stitched correctly
- **WHEN** three spoken segments with two 3-second pauses are composed
- **THEN** the final audio duration SHALL equal the sum of all spoken audio durations plus 6 seconds

---

### Requirement: Optional title card overlay
`VideoCompositionConfig` SHALL support an optional `title_card_text` that is rendered via FFmpeg `drawtext` filter with configurable font, size, color (default white), position (default center, 20% from top), and display duration (default 5 s).

#### Scenario: Title card renders when configured
- **WHEN** `title_card_text` is set
- **THEN** the FFmpeg pipeline SHALL include a `drawtext` filter for that duration

#### Scenario: No title card when not configured
- **WHEN** `title_card_text` is `None`
- **THEN** the FFmpeg pipeline SHALL NOT include any `drawtext` filter

---

### Requirement: Video production result model
`compose()` SHALL return `VideoProductionResult` with: `output_path`, `duration_seconds`, `file_size_bytes`, `video_format`, `resolution`, `processing_time_seconds`. On FFmpeg failure it SHALL raise `VideoCompositionError` with stderr captured in the message.

#### Scenario: Result populated on success
- **WHEN** composition completes
- **THEN** all `VideoProductionResult` fields SHALL be non-null

#### Scenario: FFmpeg failure raises with stderr
- **WHEN** FFmpeg exits non-zero
- **THEN** `VideoCompositionError` SHALL be raised with FFmpeg stderr in the message

## ADDED Requirements

### Requirement: Dynamic duration registry
The system SHALL maintain a module-level `DURATION_REGISTRY: dict[str, MeditationDuration]` where each entry holds a `label`, `target_minutes` (float), and `word_count` (int, derived at 120 wpm). The registry SHALL be pre-populated with keys `shorts`, `5min`, `10min`, `20min`, `30min`, `40min`, `50min`, `60min`, and SHALL support adding new entries at runtime without code changes.

#### Scenario: Default durations are registered
- **WHEN** the `meditation_script` module is imported
- **THEN** `DURATION_REGISTRY` SHALL contain entries for all 8 default keys

#### Scenario: New duration can be added at runtime
- **WHEN** a new `MeditationDuration` is inserted into `DURATION_REGISTRY` at runtime
- **THEN** `MeditationScriptGenerator.generate()` SHALL accept it as a valid duration without raising

#### Scenario: Unknown duration key raises
- **WHEN** `generate()` is called with a key not present in `DURATION_REGISTRY`
- **THEN** the system SHALL raise `ValueError` before calling the LLM

---

### Requirement: Dynamic style registry
The system SHALL maintain a module-level `STYLE_REGISTRY: dict[str, MeditationStyle]` where each entry holds a `label`, `description`, and `image_prompt_template` (used by `BackgroundImageGenerator`). The registry SHALL be pre-populated with keys `plum_village`, `plum_village_total_relaxation`, `body_scan`, `vipassana`, `loving_kindness`, `yoga_nidra`, `guided_imagery`, `mantra_based`.

#### Scenario: Default styles are registered
- **WHEN** the `meditation_script` module is imported
- **THEN** `STYLE_REGISTRY` SHALL contain entries for all 8 default keys

#### Scenario: New style can be added at runtime
- **WHEN** a new `MeditationStyle` is inserted into `STYLE_REGISTRY`
- **THEN** `generate()` SHALL accept it as a valid style key without raising

---

### Requirement: Pause marker format
Generated scripts SHALL embed `[pause X seconds]` markers (where X is a positive integer) to indicate deliberate silence. The `MeditationScriptParser` utility SHALL extract a list of `(spoken_text: str, pause_after_seconds: int | None)` tuples, where the final segment may have `pause_after_seconds = None`.

#### Scenario: Parser extracts segments and pauses
- **WHEN** `MeditationScriptParser.parse()` is called on a script body containing `[pause 3 seconds]` and `[pause 5 seconds]`
- **THEN** the result SHALL be a list of tuples where pauses are 3 and 5 respectively

#### Scenario: Pause value must be a positive integer
- **WHEN** a generated script contains `[pause 0 seconds]` or `[pause -1 seconds]`
- **THEN** `MeditationScriptParser.parse()` SHALL raise `ScriptParseError`

#### Scenario: Script with no pauses parses cleanly
- **WHEN** a script body contains no `[pause X seconds]` markers
- **THEN** `parse()` SHALL return a single-element list with `pause_after_seconds = None`

---

### Requirement: LLM backend selection with retry
The `MeditationScriptGenerator` SHALL support Claude (primary) and GPT-4o (fallback) backends, selected by `llm_backend` config. Both SHALL enforce structured JSON output with fields `title`, `style_key`, `duration_key`, `word_count`, `body`. On validation failure the generator SHALL retry up to `max_retries` (default 3) times before raising `ScriptGenerationError`.

#### Scenario: Claude backend uses tool-use JSON enforcement
- **WHEN** `llm_backend` is `"claude"`
- **THEN** the generator SHALL call the Anthropic SDK with a tool schema requiring `title`, `style_key`, `duration_key`, `word_count`, `body`

#### Scenario: GPT-4o backend uses response_format
- **WHEN** `llm_backend` is `"gpt4o"`
- **THEN** the generator SHALL call the OpenAI SDK with `response_format={"type": "json_object"}`

#### Scenario: Retry on validation failure
- **WHEN** the LLM returns JSON that fails `MeditationScript` validation
- **THEN** the generator SHALL retry; after `max_retries` exhausted it SHALL raise `ScriptGenerationError`

---

### Requirement: Word count alignment with target
Generated scripts SHALL produce a `body` whose word count is within ±10% of the target word count for the requested duration.

#### Scenario: 10-minute script word count is in range
- **WHEN** a script is requested with duration key `10min` (target ~1 200 words)
- **THEN** `MeditationScript.word_count` SHALL be between 1 080 and 1 320

#### Scenario: Shorts script does not exceed limit
- **WHEN** a script is requested with duration key `shorts`
- **THEN** the spoken content (excluding pause markers) SHALL be ≤60 words

# Feature Specification: Notion Audio Content Processor

**Feature Branch**: `001-notion-audio-processor`  
**Created**: 2026-02-12  
**Status**: Draft  
**Input**: User description: "Create a new script that reads from a new Notion Database for Audio content (environment variable NOTION_AUDIO_DATABASE_ID, default value is 302dd30aa93a8087be8dda41b3b4de9b), distinct from the Chinese Content database we are currently using (NOTION_DATABASE_ID). This script reads Content column (text type) from the database for those record with Status (select type) = Ready for Audio together with Voices column which refers to a new NOTION_VOICE_DATABASE_ID (where Name is mapped to Voice Id) and then call elevenlabs tts with timestamp (use mp3_44100_192 format with eleven_v3 model as default). It also reads the ID, Name (text), Topic (select), Sub-Type (select), stores the audio at HAVACHAT_KNOWLEDGE_PATH/<Topic>/<Sub-Type>/<ID>-<Name>.mp3. It also calls LLM to get a value to fill in Description column (text type) and Tags column (text type but with hash tags and no space in a tag)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audio Generation from Content (Priority: P1)

A content manager marks text content as "Ready for Audio" in the Notion Audio Database. The system processes this content and generates high-quality audio files with timestamp information, storing them in an organized folder structure based on the content's topic and sub-type.

**Why this priority**: This is the core value proposition - converting text content to audio. Without this, the feature has no value.

**Independent Test**: Can be fully tested by marking a single content record as "Ready for Audio", running the processor, and verifying that an audio file is created at the expected location with correct timing information.

**Acceptance Scenarios**:

1. **Given** a content record with Status="Ready for Audio", Content="Hello world", Topic="Education", Sub-Type="Grammar", ID="123", Name="test-content", **When** the processor runs, **Then** an audio file is created at `<storage-path>/Education/Grammar/123-test-content.mp3` with valid audio content
2. **Given** a content record with multi-sentence Content text, **When** the processor generates audio, **Then** the output includes word-level and sentence-level timestamp data
3. **Given** multiple records with Status="Ready for Audio", **When** the processor runs, **Then** all records are processed and audio files are created for each
4. **Given** a content record that has already been processed, **When** the processor runs again, **Then** the existing audio file is not regenerated unless content has changed

---

### User Story 2 - Automatic Metadata Generation (Priority: P2)

After generating audio, the system automatically analyzes the content and generates a descriptive summary (Description field) and relevant hashtags (Tags field), updating these back to the Notion record. This enriches the content database and makes content more discoverable.

**Why this priority**: Enhances content discoverability and organization, but not essential for basic audio generation functionality.

**Independent Test**: Can be tested by processing a content record and verifying that the Description and Tags fields are populated in Notion with appropriate, well-formed content.

**Acceptance Scenarios**:

1. **Given** a content record has been successfully converted to audio, **When** metadata generation completes, **Then** the Notion record's Description field contains a concise summary of the content (50-200 characters)
2. **Given** a content record has been successfully converted to audio, **When** metadata generation completes, **Then** the Notion record's Tags field contains 3-7 relevant hashtags with no spaces (e.g., "#grammar #english #beginner")
3. **Given** content about vocabulary learning, **When** metadata is generated, **Then** tags reflect the content domain and difficulty level
4. **Given** metadata generation fails for any reason, **When** the error occurs, **Then** the audio file is still saved and the error is logged without blocking the process

---

### User Story 3 - Voice Selection and Configuration (Priority: P3)

Content managers can assign specific voices from the Voice Database to content records. The processor uses the assigned voice when generating audio, enabling consistent voice selection for different content types, topics, or characters.

**Why this priority**: Provides flexibility and personalization, but system can operate with a single default voice initially.

**Independent Test**: Can be tested by assigning different voices to content records and verifying that generated audio uses the correct voice for each record.

**Acceptance Scenarios**:

1. **Given** a content record with a voice assigned via the Voices relation field, **When** the processor generates audio, **Then** the audio uses the specified voice from the Voice Database (mapped via Name → Voice Id)
2. **Given** a content record with no voice assigned, **When** the processor generates audio, **Then** the audio uses a default voice and processing continues successfully
3. **Given** a voice relation that references a non-existent or invalid Voice Id, **When** the processor attempts to use it, **Then** the system logs a warning and falls back to the default voice
4. **Given** multiple content records assigned to different voices, **When** the processor runs, **Then** each record's audio uses its assigned voice correctly

---

### Edge Cases

- What happens when the Content field is empty or contains only whitespace?
- What happens when Topic or Sub-Type fields are empty (affects file path construction)?
- What happens when the Name or ID fields contain characters invalid for filenames (spaces, special characters, path separators)?
- What happens when the storage directory path doesn't exist or lacks write permissions?
- What happens when the Notion API rate limit is reached during batch processing?
- What happens when the ElevenLabs API call fails (network error, API error, rate limit)?
- What happens when the LLM metadata generation times out or returns invalid format?
- What happens when two content records have the same ID-Name combination (file collision)?
- What happens when the Voice Database relation is broken or the Voice Id doesn't exist in ElevenLabs?
- What happens when processing is interrupted mid-batch (partial completion state)?


## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST query the Notion Audio Database (via NOTION_AUDIO_DATABASE_ID environment variable, default: 302dd30aa93a8087be8dda41b3b4de9b) filtering for records where Status field equals "Ready for Audio"
- **FR-002**: System MUST read the following fields from each Audio Content record: ID, Name (text), Content (text), Topic (select), Sub-Type (select), Voices (relation)
- **FR-003**: System MUST resolve the Voice ID by querying the Voice Database (NOTION_VOICE_DATABASE_ID) and mapping the Name field to Voice Id for voice selection
- **FR-004**: System MUST convert the Content text to audio using text-to-speech service with the following parameters: audio format mp3_44100_192, model eleven_v3, with timestamp information at character, word, and sentence levels
- **FR-005**: System MUST store generated audio files in organized directory structure: `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3` where HAVACHAT_KNOWLEDGE_PATH is read from environment variable
- **FR-006**: System MUST generate a concise Description (50-200 characters) of the content using language model analysis and update the Description field in the Notion record
- **FR-007**: System MUST generate relevant Tags (3-7 hashtags with no spaces, format: #tag) based on content analysis using language model and update the Tags field in the Notion record
- **FR-008**: System MUST update the Notion record after successful processing with generated Description and Tags
- **FR-009**: System MUST handle processing errors gracefully without stopping batch processing - log errors and continue with next record
- **FR-010**: System MUST log all processing activities including: records processed, audio files generated, metadata updates, errors encountered, and processing duration
- **FR-011**: System MUST sanitize filename components (ID, Name) to remove or replace invalid filesystem characters before creating file paths
- **FR-012**: System MUST create intermediate directories in the storage path if they don't exist
- **FR-013**: System MUST support processing records without assigned voices by using a default voice configuration
- **FR-014**: System MUST detect and handle duplicate filename scenarios (same ID-Name combination) to prevent overwriting existing files
- **FR-015**: System MUST validate that required environment variables (NOTION_AUDIO_DATABASE_ID, NOTION_VOICE_DATABASE_ID, HAVACHAT_KNOWLEDGE_PATH, ElevenLabs API credentials, LLM credentials) are configured before starting processing

### Key Entities

- **Audio Content Record**: Represents a content item in the Notion Audio Database with attributes: ID (unique identifier), Name (human-readable title), Content (text to convert to audio), Topic (categorical grouping), Sub-Type (categorical sub-grouping), Status (processing state), Voices (relation to voice configuration), Description (generated summary), Tags (generated hashtags)
- **Voice Configuration**: Represents a voice profile in the Voice Database with attributes: Name (voice identifier), Voice Id (external voice service identifier used for audio generation)
- **Generated Audio File**: Represents the audio output with attributes: file path (organized by topic/sub-type), audio format (opus codec), timing information (word-level and sentence-level timestamps), source content reference (links back to Audio Content Record)
- **Processing Metadata**: Represents AI-generated enrichment data with attributes: Description (concise content summary), Tags (relevant hashtags for categorization and discovery)


## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of content records marked "Ready for Audio" complete processing successfully with valid audio files generated
- **SC-002**: Audio generation completes within 30 seconds per 1000 characters of content text under normal load
- **SC-003**: Generated audio files are correctly organized with 100% accuracy in the Topic/Sub-Type folder structure
- **SC-004**: Generated Descriptions are between 50-200 characters for 90% of processed records
- **SC-005**: Generated Tags contain 3-7 hashtags with proper formatting (no spaces) for 95% of processed records
- **SC-006**: Batch processing handles errors gracefully with less than 5% fatal failures (entire batch stops) when individual records fail
- **SC-007**: Processing logs capture sufficient detail to troubleshoot 100% of failures (record ID, error type, timestamp)
- **SC-008**: Voice resolution succeeds for 95% of records with assigned voices, with automatic fallback to default voice for failures
- **SC-009**: File naming conflicts (duplicate ID-Name combinations) are detected and handled without data loss for 100% of cases
- **SC-010**: System validates all required environment variables before processing starts and provides clear error messages for 100% of missing configurations


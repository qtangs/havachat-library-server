# ElevenLabs TTS with Timestamps

## Overview

This feature provides text-to-speech generation using ElevenLabs API with detailed timestamp information. The character-level timing data from ElevenLabs is automatically converted to word-level and sentence-level timing to match our Transcript schema.

**Access via FastAPI**: This tool is exposed as a FastAPI endpoint that can be accessed by n8n or any HTTP client over the internet with API key authentication.

## Features

- **Character-level timing**: Original timing data from ElevenLabs API
- **Word-level timing**: Automatically grouped from characters
- **Sentence-level segments**: Automatically split based on punctuation
- **Transcript schema compatibility**: Outputs match `datatypes.transcript.Transcript`
- **HTTP API access**: RESTful API with API key authentication
- **Audio output options**: Returns audio as base64 in response
- **Alignment fallback**: Uses `normalized_alignment` when available, falls back to `alignment`

## File Structure

```
src/
├── api/
│   ├── main.py                      # FastAPI app with API key auth
│   └── routes/
│       └── audio.py                 # Audio endpoints including TTS
├── tools/audio/
│   └── tts_with_elevenlabs.py      # Core TTS implementation
└── scripts/
    └── run_server.py                # Server startup script
```

## Usage

### Running the Server

```bash
# Development mode with auto-reload
PYTHONPATH=src uv run python scripts/run_server.py

# Or with uvicorn directly
PYTHONPATH=src uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
PYTHONPATH=src uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables

```bash
# Required
ELEVENLABS_API_KEY=your_elevenlabs_api_key
API_KEY=your_api_key_for_authentication

# Optional
HOST=0.0.0.0
PORT=8000
RELOAD=true
CORS_ORIGINS=*
```

### API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### API Endpoints

#### POST /audio/tts-with-timestamps

Generate speech with detailed timestamp information.

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Request Body:**
```json
{
  "text": "Hello world, this is a test.",
  "voice_id": "21m00Tcm4TlvDq8ikWAM",
  "language": "en",
  "model_id": "eleven_multilingual_v2",
  "output_format": "mp3_44100_128",
  "optimize_streaming_latency": 0,
  "return_audio": true
}
```

**Response:**
```json
{
  "success": true,
  "transcript": {
    "segments": [
      {
        "start": 0.0,
        "end": 2.5,
        "text": "Hello world, this is a test.",
        "words": [
          {
            "start": 0.0,
            "end": 0.3,
            "word": "Hello",
            "score": null
          },
          ...
        ]
      }
    ]
  },
  "audio_base64": "base64_encoded_audio_data...",
  "metadata": {
    "character_count": 30,
    "word_count": 6,
    "segment_count": 1,
    "duration_seconds": 2.5,
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "model_id": "eleven_multilingual_v2",
    "language": "en"
  }
}
```

#### GET /audio/voices

List commonly used ElevenLabs voices.

**Headers:**
```
X-API-Key: your_api_key
```

**Response:**
```json
{
  "voices": [
    {
      "id": "21m00Tcm4TlvDq8ikWAM",
      "name": "Rachel",
      "gender": "female",
      "description": "Default voice, calm and clear"
    },
    ...
  ]
}
```

### Using from n8n

In n8n, use the **HTTP Request** node:

**Configuration:**
- Method: POST
- URL: `https://your-server.com/audio/tts-with-timestamps`
- Authentication: Generic Credential Type
  - Add Header: `X-API-Key` with value from credentials
- Body Content Type: JSON
- Body:
```json
{
  "text": "{{$json.text}}",
  "voice_id": "{{$json.voice_id || '21m00Tcm4TlvDq8ikWAM'}}",
  "language": "{{$json.language || 'en'}}",
  "return_audio": true
}
```

**Processing the Response:**

The audio is returned as base64 in `response.audio_base64`. To save it as a file:

1. Use a Code node to decode base64:
```javascript
const audioBase64 = $json.audio_base64;
const audioBuffer = Buffer.from(audioBase64, 'base64');

return [{
  json: $json,
  binary: {
    data: {
      data: audioBuffer.toString('base64'),
      mimeType: 'audio/mpeg',
      fileName: 'output.mp3',
    }
  }
}];
```

2. Use "Write Binary File" node to save to disk

### Using from Python

```python
import requests
import base64

# Configuration
API_URL = "http://localhost:8000"
API_KEY = "your_api_key"

# Make request
response = requests.post(
    f"{API_URL}/audio/tts-with-timestamps",
    headers={"X-API-Key": API_KEY},
    json={
        "text": "Hello world, this is a test.",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "language": "en",
        "return_audio": True,
    }
)

data = response.json()

# Access transcript
for segment in data["transcript"]["segments"]:
    print(f"[{segment['start']:.2f}s - {segment['end']:.2f}s]: {segment['text']}")
    for word in segment["words"]:
        print(f"  {word['word']} ({word['start']:.2f}s)")

# Save audio
if data.get("audio_base64"):
    audio_data = base64.b64decode(data["audio_base64"])
    with open("output.mp3", "wb") as f:
        f.write(audio_data)
```

### Using from curl

```bash
curl -X POST "http://localhost:8000/audio/tts-with-timestamps" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "language": "en"
  }'
```

## ElevenLabs API Details

### Endpoint Used

`client.text_to_speech.convert_with_timestamps()`

### Response Structure

The API returns:
- `audio_base64`: Base64 encoded audio data
- `alignment`: Character-level timing (fallback)
- `normalized_alignment`: Character-level timing (preferred)
  - `characters`: List of characters
  - `character_start_times_seconds`: List of start times
  - `character_end_times_seconds`: List of end times

### Character to Word Conversion Logic

Words are identified by:
- Whitespace boundaries (spaces, tabs, newlines)
- Punctuation marks (`,.:;!?()[]{}"\'-`)

Punctuation is treated as separate "words" with their own timing.

### Word to Sentence Conversion Logic

Sentences are split using regex pattern: `[.!?]+\s*`

If no sentence boundaries found, entire text is treated as one segment.

## Transcript Schema Compatibility

### TranscriptWord
```python
{
    "start": float,      # Start time in seconds
    "end": float,        # End time in seconds
    "word": str,         # The word text
    "score": None        # Confidence score (not provided by ElevenLabs)
}
```

### TranscriptSegment
```python
{
    "start": float,      # Start time of segment
    "end": float,        # End time of segment
    "text": str,         # Complete sentence text
    "words": [...]       # List of TranscriptWord objects
}
```

### Transcript
```python
{
    "segments": [...],           # List of TranscriptSegment
    "doc_id": None,
    "index": 0,
    "is_last_transcript": True,
    "url": None,
    "title": str,                # First 50 chars of text
    "transcriber": "elevenlabs_tts",
    "detected_language": str     # Language code if provided
}
```

## Environment Variables

```bash
ELEVENLABS_API_KEY=your_api_key_here
```

## Common Voice IDs

- `21m00Tcm4TlvDq8ikWAM` - Rachel (default, female)
- `AZnzlk1XvdvUeBnXmlld` - Domi (female)
- `EXAVITQu4vr4xnSDxMaL` - Bella (female)
- `ErXwobaYiN019PkySvjV` - Antoni (male)
- `MF3mGyEYCl7XYWbV9V6O` - Elli (female)
- `TxGEqnHWrfWFTfGW9XjX` - Josh (male)
- `VR6AewLTigWG4xSOukaG` - Arnold (male)
- `pNInz6obpgDQGcFmaJgB` - Adam (male)
- `yoZ06aMxZJJ28mfd3POQ` - Sam (male)

Visit https://elevenlabs.io/voice-library for more voices.

## Error Handling

The function handles:
- Missing ElevenLabs package (raises exception)
- Missing API key (handled by ElevenLabs client)
- No alignment data in response (raises exception)
- Missing audio_base64 in response (handled gracefully)
- File I/O errors (propagated)

In n8n mode, errors are caught and returned as:
```json
{
  "success": false,
  "error": "Error message"
}
```

## Cost Estimation

The logger outputs:
- Time taken (seconds)
- Character count
- Word count
- Segment count

ElevenLabs pricing is typically per character, so character count is most relevant for cost tracking.

## Testing

```bash
# Run unit tests (when available)
uv run python -m pytest tests/tools/audio/test_tts_with_elevenlabs.py
```

## Dependencies

```toml
[project.dependencies]
elevenlabs = "^1.0.0"
pydantic = "^2.0.0"
```

## Future Enhancements

- [ ] Add batch processing for multiple texts
- [ ] Support streaming TTS with incremental timestamps
- [ ] Add voice cloning support
- [ ] Implement retry logic with exponential backoff
- [ ] Add voice settings customization (stability, similarity boost, etc.)
- [ ] Support for SSML markup
- [ ] Cache audio and transcripts to reduce API calls
- [ ] Add pronunciation dictionary support
- [ ] Implement speaker diarization for multi-voice scenarios

## Related Files

- `src/datatypes/transcript.py` - Transcript schema definitions
- `src/tools/audio/transcribe_audio_with_elevenlabs.py` - Audio transcription (speech-to-text)
- `src/libs/logging_helper.py` - Logging utilities

## References

- [ElevenLabs API Documentation](https://elevenlabs.io/docs/api-reference/text-to-speech)
- [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python)
- [n8n Python Code Node Documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/#python-native)

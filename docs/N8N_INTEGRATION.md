# Using Havachat Library Server from n8n

This guide shows how to call the Havachat Library Server API from n8n workflows.

## Prerequisites

1. Havachat Library Server running and accessible (e.g., `https://your-server.com`)
2. API key configured

## Setup n8n Credentials

1. Go to **Credentials** in n8n
2. Click **+ Add Credential**
3. Choose **Header Auth**
4. Configure:
   - **Name**: `Havachat Library Server`
   - **Header Name**: `X-API-Key`
   - **Header Value**: Your API key

## Example Workflows

### Basic TTS Generation

```
[Manual Trigger] → [HTTP Request] → [Code (optional)]
```

**HTTP Request Node Configuration:**

- **Authentication**: Header Auth (select your credential)
- **Method**: POST
- **URL**: `https://your-server.com/audio/tts-with-timestamps`
- **Body Content Type**: JSON
- **Body**:
```json
{
  "text": "Hello world, this is a test.",
  "voice_id": "21m00Tcm4TlvDq8ikWAM",
  "language": "en",
  "return_audio": true
}
```

**Response:**
The node will output JSON with:
- `transcript`: Timing information
- `audio_base64`: Base64 encoded audio
- `metadata`: Generation details

### Dynamic Text from Previous Node

If the text comes from a previous node:

```json
{
  "text": "{{ $json.text }}",
  "voice_id": "{{ $json.voice_id || '21m00Tcm4TlvDq8ikWAM' }}",
  "language": "{{ $json.language || 'en' }}",
  "return_audio": true
}
```

### Save Audio to File

Add a **Code** node after the HTTP Request:

```javascript
// Decode base64 audio and create binary data
const audioBase64 = $json.audio_base64;
const audioBuffer = Buffer.from(audioBase64, 'base64');

return [{
  json: {
    transcript: $json.transcript,
    metadata: $json.metadata
  },
  binary: {
    audio: {
      data: audioBuffer.toString('base64'),
      mimeType: 'audio/mpeg',
      fileName: `tts_${Date.now()}.mp3`,
    }
  }
}];
```

Then add **Write Binary File** node:
- **File Name**: `{{ $json.binary.audio.fileName }}`
- **Binary Property**: `audio`
- **Output Path**: `/path/to/save/`

### Process Multiple Texts

```
[Read File/Spreadsheet] → [Split In Batches] → [HTTP Request] → [Merge]
```

Use **Split In Batches** to process texts one by one (or in batches) to avoid rate limits.

### Extract Word Timing

Add a **Code** node to extract specific timing info:

```javascript
const segments = $json.transcript.segments;
const words = [];

for (const segment of segments) {
  for (const word of segment.words) {
    words.push({
      word: word.word,
      start: word.start,
      end: word.end,
      duration: word.end - word.start
    });
  }
}

return [{
  json: {
    words: words,
    total_words: words.length,
    total_duration: segments[segments.length - 1].end
  }
}];
```

## Advanced: Conditional Voice Selection

Use **Switch** node to select voice based on language:

```javascript
// In Switch node
const lang = $json.language || 'en';

const voiceMap = {
  'en': '21m00Tcm4TlvDq8ikWAM',  // Rachel
  'es': 'ErXwobaYiN019PkySvjV',  // Antoni
  'fr': 'pNInz6obpgDQGcFmaJgB',  // Adam
  'ja': 'yoZ06aMxZJJ28mfd3POQ',  // Sam
};

return voiceMap[lang] || voiceMap['en'];
```

## Error Handling

Add **Error Trigger** node to handle failures:

```
[Your Workflow] → [Error Trigger] → [Send Email/Slack]
```

Or use **Try-Catch** wrapper:

```javascript
// In Code node
try {
  // Your API call logic
  const response = await $http.request({
    method: 'POST',
    url: 'https://your-server.com/audio/tts-with-timestamps',
    headers: {
      'X-API-Key': '{{$credentials.YOUR_CREDENTIAL.headerValue}}',
      'Content-Type': 'application/json'
    },
    body: {
      text: $json.text,
      voice_id: '21m00Tcm4TlvDq8ikWAM',
      language: 'en'
    }
  });
  
  return [{json: response.body}];
} catch (error) {
  return [{
    json: {
      error: true,
      message: error.message,
      original_text: $json.text
    }
  }];
}
```

## Rate Limiting

If processing many requests, add **Wait** node between batches:

```
[Split In Batches] → [HTTP Request] → [Wait: 1 second] → [Continue]
```

## Caching Results

To avoid regenerating the same text:

1. **Hash the input**:
```javascript
const crypto = require('crypto');
const hash = crypto.createHash('md5')
  .update($json.text + $json.voice_id)
  .digest('hex');

return [{json: {...$json, cache_key: hash}}];
```

2. **Check cache** (use Redis node or database)
3. **Skip if exists**, otherwise call API

## Monitoring

Add logging nodes to track:
- Request count
- Error rate
- Average response time

```javascript
// After HTTP Request node
const startTime = new Date($node["HTTP Request"].startTime);
const endTime = new Date();
const duration = endTime - startTime;

return [{
  json: {
    ...data,
    performance: {
      duration_ms: duration,
      timestamp: endTime.toISOString(),
      text_length: $json.text?.length
    }
  }
}];
```

## Complete Example: Multilingual News Reader

```
[RSS Feed Read]
  ↓
[Filter Items: New only]
  ↓
[Set: Extract text & lang]
  ↓
[HTTP Request: TTS]
  ↓
[Code: Save audio]
  ↓
[Write Binary File]
  ↓
[Upload to S3/Storage]
  ↓
[Webhook: Notify completion]
```

## Troubleshooting

### "Invalid or missing API key"
- Check credential is selected in HTTP Request node
- Verify header name is exactly `X-API-Key`

### "Connection refused"
- Ensure server is running and accessible
- Check firewall/network settings
- Verify URL is correct

### "Request timeout"
- Long texts take more time
- Increase timeout in HTTP Request settings
- Consider splitting long texts into chunks

### "Rate limit exceeded"
- Add delays between requests
- Reduce batch size
- Contact server admin for higher limits

## Best Practices

1. **Validate input**: Check text length before sending
2. **Handle errors gracefully**: Always have error handling
3. **Log requests**: Track what was sent and received
4. **Cache when possible**: Don't regenerate identical content
5. **Test with small data first**: Verify workflow before bulk processing
6. **Monitor costs**: Track character usage for billing
7. **Use appropriate voices**: Match voice to language/content
8. **Batch smartly**: Balance speed vs rate limits

## Resources

- API Documentation: `https://your-server.com/docs`
- Server Status: `https://your-server.com/health`
- Voice List: `https://your-server.com/audio/voices`

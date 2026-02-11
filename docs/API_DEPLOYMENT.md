# Havachat Library Server - API Deployment Guide

## Quick Start

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the server:**
   ```bash
   PYTHONPATH=src uv run python scripts/run_server.py
   ```

4. **Access API docs:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Environment Variables

### Required

- `ELEVENLABS_API_KEY`: Your ElevenLabs API key
- `API_KEY`: Secure key for authenticating API requests

### Optional

- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)
- `RELOAD`: Enable auto-reload in development (default: `true`)
- `CORS_ORIGINS`: Comma-separated allowed origins (default: `*`)

## Generating API Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Running in Production

### Using uvicorn with workers

```bash
PYTHONPATH=src uv run uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log
```

### Using Docker

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY scripts/ scripts/

# Install dependencies
RUN uv sync --no-dev

# Set environment
ENV PYTHONPATH=src
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run server
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Build and run:
```bash
docker build -t havachat-library-server .
docker run -p 8000:8000 --env-file .env havachat-library-server
```

### Using Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run:
```bash
docker-compose up -d
```

## Deployment Platforms

### Railway

1. Create new project
2. Connect GitHub repo
3. Add environment variables
4. Set start command: `PYTHONPATH=src uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### Render

1. New Web Service
2. Connect repo
3. Build Command: `pip install uv && uv sync`
4. Start Command: `PYTHONPATH=src uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2`
5. Add environment variables

### Fly.io

```toml
# fly.toml
app = "havachat-library-server"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8000"
  PYTHONPATH = "src"

[[services]]
  http_checks = []
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

Deploy:
```bash
fly deploy
fly secrets set ELEVENLABS_API_KEY=xxx API_KEY=xxx
```

### AWS Lambda with Mangum

```bash
pip install mangum
```

```python
# lambda_handler.py
from mangum import Mangum
from api.main import app

handler = Mangum(app)
```

## Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "service": "Havachat Library Server",
  "version": "1.0.0",
  "elevenlabs_configured": true
}
```

### Logging

Logs are output to stdout/stderr. Configure your deployment platform to collect these logs.

### Metrics

The server includes basic request logging. For production monitoring, consider:
- Prometheus metrics (add middleware)
- Sentry for error tracking
- DataDog or New Relic APM

## Security

### Best Practices

1. **Never commit .env files** - Use platform-specific secret management
2. **Rotate API keys regularly**
3. **Use HTTPS in production** - Configure via reverse proxy (nginx, Caddy)
4. **Restrict CORS origins** - Don't use `*` in production
5. **Rate limiting** - Add middleware to prevent abuse:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
@limiter.limit("5/minute")
async def root(request: Request):
    return {"status": "ok"}
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Testing the API

### Using curl

```bash
# Set your API key
API_KEY="your_api_key"

# Test TTS endpoint
curl -X POST "http://localhost:8000/audio/tts-with-timestamps" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "language": "en"
  }' | jq

# List voices
curl -X GET "http://localhost:8000/audio/voices" \
  -H "X-API-Key: $API_KEY" | jq
```

### Using Python

```python
import requests

API_URL = "http://localhost:8000"
API_KEY = "your_api_key"

response = requests.post(
    f"{API_URL}/audio/tts-with-timestamps",
    headers={"X-API-Key": API_KEY},
    json={
        "text": "Hello world",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "language": "en",
    }
)

print(response.json())
```

## Troubleshooting

### Common Issues

**"Invalid or missing API key"**
- Check X-API-Key header is set correctly
- Verify API_KEY environment variable matches

**"ELEVENLABS_API_KEY not configured"**
- Set ELEVENLABS_API_KEY environment variable
- Check .env file is loaded

**Import errors**
- Ensure PYTHONPATH=src is set
- Run from project root directory

**Port already in use**
- Change PORT environment variable
- Kill process using port: `lsof -ti:8000 | xargs kill`

## Performance

### Benchmarking

```bash
# Install hey
brew install hey

# Run benchmark
hey -n 1000 -c 10 -m POST \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"text":"test","voice_id":"21m00Tcm4TlvDq8ikWAM"}' \
  http://localhost:8000/audio/tts-with-timestamps
```

### Optimization Tips

1. **Use workers**: Run multiple uvicorn workers
2. **Enable HTTP/2**: Use traefik or caddy as reverse proxy
3. **Cache responses**: Add Redis for frequently used TTS
4. **Connection pooling**: ElevenLabs client reuses connections
5. **Async processing**: Consider Celery for long-running tasks

## Support

For issues or questions:
- Check API documentation: http://localhost:8000/docs
- Review logs for error details
- See specs/elevenlabs-tts-timestamps/README.md for feature docs

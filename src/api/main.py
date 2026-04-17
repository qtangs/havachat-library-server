"""
FastAPI application for Havachat Library Server

Exposes tools like TTS, transcription, and other audio processing
capabilities via HTTP API with API key authentication.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware

from libs.logging_helper import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    import os
    from pathlib import Path
    from models.pipeline_run import pipeline_store
    persist_base = Path(os.getenv("HAVACHAT_KNOWLEDGE_PATH", "/tmp"))
    pipeline_store.configure_persistence(persist_base)
    logger.info({"msg": "Starting Havachat Library Server"})
    yield
    logger.info({"msg": "Shutting down Havachat Library Server"})


# Create FastAPI app
app = FastAPI(
    title="Havachat Library Server",
    description="Audio processing tools API including TTS, transcription, and more",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Havachat Library Server",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "Havachat Library Server",
        "version": "1.0.0",
        "elevenlabs_configured": bool(os.getenv("ELEVENLABS_API_KEY")),
    }


# Import and include routers
from api.routes import audio

app.include_router(audio.router, prefix="/audio", tags=["audio"])

from fastapi.staticfiles import StaticFiles
from api.routes import pipeline, pipeline_ui

app.include_router(pipeline.router, tags=["pipeline"])
app.include_router(pipeline_ui.router)

# Serve static files for the pipeline UI
_pipeline_static = Path(__file__).parent.parent / "static" / "pipeline"
if _pipeline_static.exists():
    app.mount("/pipeline/static", StaticFiles(directory=str(_pipeline_static)), name="pipeline_static")

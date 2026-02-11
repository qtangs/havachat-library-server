"""
FastAPI application for Havachat Library Server

Exposes tools like TTS, transcription, and other audio processing
capabilities via HTTP API with API key authentication.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from libs.logging_helper import logger

# API key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Verify API key from request header."""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY not configured on server",
        )
    
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
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

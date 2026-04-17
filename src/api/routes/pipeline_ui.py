"""Serves the pipeline web UI (no auth required — API key handled client-side)."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["pipeline-ui"])

_STATIC_DIR = Path(__file__).parent.parent.parent / "static" / "pipeline"


@router.get("/pipeline/", include_in_schema=False)
@router.get("/pipeline", include_in_schema=False)
async def pipeline_ui():
    """Serve the pipeline web UI HTML page."""
    return FileResponse(str(_STATIC_DIR / "index.html"), media_type="text/html")

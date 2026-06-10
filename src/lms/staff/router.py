"""Serve staff desk UI (Phase 6)."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent / "static"

router = APIRouter(tags=["staff-ui"])


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def staff_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def staff_static_directory() -> Path:
    return STATIC_DIR

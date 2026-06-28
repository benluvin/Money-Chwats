"""Endpoint /health — usado por el popup para saber si el servicio está vivo."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}

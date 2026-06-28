"""POST /import: importa un archivo 'Exportar chat' de WhatsApp y llena las tablas.
Camino principal: sin OCR, sin navegador. Funciona con WhatsApp Desktop/celular."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_config
from ..models.extraction import ExtractionResult
from ..pipeline.dashboard import build_dashboard
from ..pipeline.import_pipeline import ImportError_, import_export_file
from ..pipeline.watcher import load_state, pending_files, scan_inbox_once
from ..structurer.base import StructurerError
from ..structurer.factory import build_structurer

router = APIRouter()
log = logging.getLogger("money_chwats.import_route")


class ImportRequest(BaseModel):
    path: str


class ImportResponse(BaseModel):
    cliente_id: str
    nombre: str
    nickname: str
    extraction: ExtractionResult
    pedidos_added: int
    telefono_pendiente: bool
    requiere_revision: bool
    media: dict
    metodo_extraccion: str
    csv_pending: bool


@router.post("/import", response_model=ImportResponse)
async def import_export(req: ImportRequest) -> ImportResponse:
    cfg = get_config()
    src = Path(req.path).expanduser()
    if not src.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Archivo no existe: {src}")

    structurer = build_structurer(cfg)
    try:
        out = await import_export_file(cfg, src, structurer)
    except ImportError_ as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except StructurerError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return ImportResponse(
        cliente_id=out.cliente_id,
        nombre=out.nombre,
        nickname=out.nickname,
        extraction=out.extraction,
        pedidos_added=out.pedidos_added,
        telefono_pendiente=out.telefono_pendiente,
        requiere_revision=out.requiere_revision,
        media=out.media,
        metodo_extraccion=out.metodo_extraccion,
        csv_pending=out.csv_pending,
    )


@router.get("/dashboard")
def dashboard() -> dict:
    """Resumen de avance leído de las tablas (para el tablero)."""
    return build_dashboard(get_config())


@router.get("/import/status")
def import_status() -> dict:
    """Estado del vigilante: cuántos archivos van procesados y cuántos faltan."""
    cfg = get_config()
    state = load_state(cfg)
    procesados = list(state.get("procesados", {}).values())
    return {
        "inbox_dir": cfg.export.inbox_dir or None,
        "procesados": len(procesados),
        "pendientes": len(pending_files(cfg)),
        "ultimos": procesados[-10:],
    }


@router.post("/import/scan")
async def import_scan() -> dict:
    """Procesa ahora todos los archivos nuevos del buzón (disparo manual)."""
    cfg = get_config()
    if not cfg.export.inbox_dir:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay carpeta-buzón configurada ([export] inbox_dir).")
    resultados = await scan_inbox_once(cfg, build_structurer(cfg))
    return {"procesados_ahora": len(resultados), "resultados": resultados}

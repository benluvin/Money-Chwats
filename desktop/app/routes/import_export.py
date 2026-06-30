"""POST /import: importa un archivo 'Exportar chat' de WhatsApp y llena las tablas.
Camino principal: sin OCR, sin navegador. Funciona con WhatsApp Desktop/celular."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from ..config import get_config
from ..pipeline.dashboard import build_dashboard
from ..pipeline.import_pipeline import (
    ImportError_,
    analizar_cliente,
    crear_cliente_base,
)
from ..pipeline.watcher import load_state, pending_files, scan_inbox_once
from ..structurer.factory import build_structurer

router = APIRouter()
log = logging.getLogger("money_chwats.import_route")


class ImportRequest(BaseModel):
    path: str


class ImportResponse(BaseModel):
    cliente_id: str
    nombre: str
    telefono_pendiente: bool
    media: dict
    estado_analisis: str = "pendiente"


async def _analizar_en_segundo_plano(cliente_id: str) -> None:
    """Corre el análisis (cascada) sin bloquear la respuesta del /import."""
    try:
        await analizar_cliente(get_config(), cliente_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Análisis en segundo plano falló para %s: %s", cliente_id, exc)


@router.post("/import", response_model=ImportResponse)
async def import_export(req: ImportRequest, bg: BackgroundTasks) -> ImportResponse:
    cfg = get_config()
    src = Path(req.path).expanduser()
    if not src.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Archivo no existe: {src}")

    # FASE 1 (instantánea): crea el cliente con datos deterministas.
    try:
        base = await crear_cliente_base(cfg, src)
    except ImportError_ as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # FASE 2 (segundo plano): la cascada rellena pedidos + interpretación.
    bg.add_task(_analizar_en_segundo_plano, base.cliente_id)

    return ImportResponse(
        cliente_id=base.cliente_id,
        nombre=base.nombre,
        telefono_pendiente=base.telefono_pendiente,
        media=base.media,
        estado_analisis="pendiente",
    )


class ReanalizarRequest(BaseModel):
    cliente_id: str


@router.post("/clientes/{cliente_id}/reanalizar")
async def reanalizar(cliente_id: str) -> dict:
    """Vuelve a correr la cascada de modelos sobre la evidencia del cliente."""
    cfg = get_config()
    try:
        return await analizar_cliente(cfg, cliente_id)
    except ImportError_ as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


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

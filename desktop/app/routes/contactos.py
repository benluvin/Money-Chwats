"""Agenda de contactos: importar (.vcf/.csv), listar. GET/POST /contactos."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..config import get_config
from ..pipeline import contactos as cont

router = APIRouter(tags=["contactos"])


class ImportarAgendaIn(BaseModel):
    path: str


@router.get("/contactos")
def listar_contactos(q: str = Query("", description="Buscar nombre o teléfono")) -> dict:
    rows = cont.listar(get_config())
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r.get("nombre", "").lower() or ql in r.get("telefono", "")]
    return {"data": rows, "total": len(rows)}


@router.post("/contactos/importar")
def importar_agenda(req: ImportarAgendaIn) -> dict:
    src = Path(req.path).expanduser()
    if not src.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Archivo no existe: {src}")
    if src.suffix.lower() not in (".vcf", ".csv"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Usa un .vcf (vCard) o .csv (Google Contacts).")
    try:
        resumen = cont.importar_agenda(get_config(), src)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo leer la agenda: {exc}") from exc
    return {"ok": True, **resumen}

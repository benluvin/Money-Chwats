"""GET /clientes y GET /pedidos — lectura de tablas para la UI Electron."""
from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter, Query

from ..config import get_config
from ..utils.paths import data_dir

router = APIRouter(tags=["data"])


def _read_csv(path: Path, sep: str) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f, delimiter=sep)]


@router.get("/clientes")
async def list_clientes(
    q: str = Query("", description="Buscar en nombre / teléfono"),
    estado: str = Query("", description="Filtrar por estado_relacion"),
    etiqueta: str = Query("", description="Filtrar por etiqueta"),
    solo_pendientes: bool = Query(False, description="Solo con multimedia_pendiente"),
):
    cfg = get_config()
    rows = _read_csv(data_dir(cfg.storage.root_path) / "clientes.csv", cfg.csv.separator)
    if q:
        q_low = q.lower()
        rows = [r for r in rows if q_low in r.get("nombre", "").lower() or q_low in r.get("telefono", "")]
    if estado:
        rows = [r for r in rows if r.get("estado_relacion", "").lower() == estado.lower()]
    if etiqueta:
        rows = [r for r in rows if etiqueta.lower() in r.get("etiquetas", "").lower()]
    if solo_pendientes:
        rows = [r for r in rows if r.get("multimedia_pendiente", "").upper() == "TRUE"]
    return {"data": rows, "total": len(rows)}


@router.get("/pedidos")
async def list_pedidos(
    cliente_id: str = Query("", description="Filtrar por cliente_id"),
    estado: str = Query("", description="Filtrar por estado_pago"),
    q: str = Query("", description="Buscar en producto_servicio"),
):
    cfg = get_config()
    d = data_dir(cfg.storage.root_path)
    sep = cfg.csv.separator
    rows = _read_csv(d / "pedidos.csv", sep)

    # Join simple: enriquecer con nombre del cliente.
    clientes = {r["cliente_id"]: r.get("nombre", "") for r in _read_csv(d / "clientes.csv", sep)}
    for r in rows:
        r["_nombre_cliente"] = clientes.get(r.get("cliente_id", ""), "")

    if cliente_id:
        rows = [r for r in rows if r.get("cliente_id", "") == cliente_id]
    if estado:
        rows = [r for r in rows if r.get("estado_pago", "").lower() == estado.lower()]
    if q:
        rows = [r for r in rows if q.lower() in r.get("producto_servicio", "").lower()]
    return {"data": rows, "total": len(rows)}

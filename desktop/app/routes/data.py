"""GET /clientes y /pedidos (lectura) + borrado/edición para la UI Electron."""
from __future__ import annotations

import csv
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel

from ..config import get_config
from ..utils.paths import data_dir

router = APIRouter(tags=["data"])


def _read_csv(path: Path, sep: str) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f, delimiter=sep)]


def _write_csv(path: Path, rows: list[dict], columns: list[str], sep: str, enc: str) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter=sep)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})
    os.replace(tmp, path)


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
        rows = [r for r in rows if r.get("estado_pedido", "").lower() == estado.lower()]
    if q:
        rows = [r for r in rows if q.lower() in r.get("producto_servicio", "").lower()]
    return {"data": rows, "total": len(rows)}


# ── Borrado / edición ───────────────────────────────────────────────────────────

class PedidoIn(BaseModel):
    cliente_id: str
    producto_servicio: str
    cantidad: str = ""
    monto_total: str = ""
    fecha_pedido: str = ""
    estado_pedido: str = "confirmado"
    notas: str = ""


def _cols(name: str) -> list[str]:
    from ..models.extraction import CLIENTES_COLUMNS, PEDIDOS_COLUMNS
    return CLIENTES_COLUMNS if name == "clientes" else PEDIDOS_COLUMNS


@router.delete("/pedidos/{pedido_id}")
def borrar_pedido(pedido_id: str) -> dict:
    cfg = get_config()
    d = data_dir(cfg.storage.root_path)
    path = d / "pedidos.csv"
    rows = _read_csv(path, cfg.csv.separator)
    quedan = [r for r in rows if r.get("pedido_id") != pedido_id]
    if len(quedan) == len(rows):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado.")
    _write_csv(path, quedan, _cols("pedidos"), cfg.csv.separator, cfg.csv.encoding)
    return {"ok": True}


@router.delete("/clientes/{cliente_id}")
def borrar_cliente(cliente_id: str) -> dict:
    """Borra el cliente y, en cascada, sus pedidos."""
    cfg = get_config()
    d = data_dir(cfg.storage.root_path)
    sep, enc = cfg.csv.separator, cfg.csv.encoding

    cpath = d / "clientes.csv"
    crows = _read_csv(cpath, sep)
    cquedan = [r for r in crows if r.get("cliente_id") != cliente_id]
    if len(cquedan) == len(crows):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado.")
    _write_csv(cpath, cquedan, _cols("clientes"), sep, enc)

    ppath = d / "pedidos.csv"
    prows = _read_csv(ppath, sep)
    if prows:
        pquedan = [r for r in prows if r.get("cliente_id") != cliente_id]
        _write_csv(ppath, pquedan, _cols("pedidos"), sep, enc)
    return {"ok": True}


# Campos que el usuario puede editar a mano (whitelist por seguridad).
_EDITABLES_CLIENTE = {
    "nombre", "nickname", "telefono_completo", "estado_relacion",
    "direccion_principal", "especificaciones_importantes", "etiquetas",
    "resumen", "sentimiento_general",
}
_EDITABLES_PEDIDO = {
    "producto_servicio", "cantidad", "unidad", "precio_unitario", "monto_total",
    "moneda", "forma_de_pago", "direccion_envio", "fecha_pedido",
    "fecha_entrega_acordada", "estado_pedido", "notas",
}


@router.patch("/clientes/{cliente_id}")
def editar_cliente(cliente_id: str, cambios: dict = Body(...)) -> dict:
    """Edita campos del cliente. Marca editado_manualmente para que prevalezca."""
    cfg = get_config()
    path = data_dir(cfg.storage.root_path) / "clientes.csv"
    rows = _read_csv(path, cfg.csv.separator)
    encontrado = False
    for r in rows:
        if r.get("cliente_id") == cliente_id:
            for k, v in cambios.items():
                if k in _EDITABLES_CLIENTE:
                    r[k] = "" if v is None else str(v)
            # Si pusieron teléfono, ya no está pendiente.
            if "telefono_completo" in cambios:
                r["telefono_pendiente"] = "false" if str(cambios.get("telefono_completo") or "").strip() else "true"
            r["editado_manualmente"] = "true"
            encontrado = True
            break
    if not encontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado.")
    _write_csv(path, rows, _cols("clientes"), cfg.csv.separator, cfg.csv.encoding)
    return {"ok": True}


@router.patch("/pedidos/{pedido_id}")
def editar_pedido(pedido_id: str, cambios: dict = Body(...)) -> dict:
    cfg = get_config()
    path = data_dir(cfg.storage.root_path) / "pedidos.csv"
    rows = _read_csv(path, cfg.csv.separator)
    encontrado = False
    for r in rows:
        if r.get("pedido_id") == pedido_id:
            for k, v in cambios.items():
                if k in _EDITABLES_PEDIDO:
                    r[k] = "" if v is None else str(v)
            r["editado_manualmente"] = "true"  # el reanálisis ya no lo pisará
            encontrado = True
            break
    if not encontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado.")
    _write_csv(path, rows, _cols("pedidos"), cfg.csv.separator, cfg.csv.encoding)
    return {"ok": True}


@router.post("/pedidos")
def agregar_pedido(req: PedidoIn) -> dict:
    """Agrega un pedido manual (lo que el usuario quiera registrar a mano)."""
    cfg = get_config()
    d = data_dir(cfg.storage.root_path)
    sep, enc = cfg.csv.separator, cfg.csv.encoding

    clientes = {r["cliente_id"]: r for r in _read_csv(d / "clientes.csv", sep)}
    if req.cliente_id not in clientes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no existe.")
    nombre = clientes[req.cliente_id].get("nombre", "")

    ppath = d / "pedidos.csv"
    rows = _read_csv(ppath, sep)
    pedido_id = str(uuid.uuid4())
    nuevo = {
        "pedido_id": pedido_id,
        "cliente_id": req.cliente_id,
        "cliente_nombre": nombre,
        "producto_servicio": req.producto_servicio,
        "cantidad": req.cantidad,
        "monto_total": req.monto_total,
        "moneda": cfg.locale.default_currency,
        "fecha_pedido": req.fecha_pedido or datetime.now().date().isoformat(),
        "estado_pedido": req.estado_pedido,
        "notas": req.notas,
        "metodo_extraccion": "manual",
        "fecha_captura": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(nuevo)
    _write_csv(ppath, rows, _cols("pedidos"), sep, enc)
    return {"ok": True, "pedido_id": pedido_id}

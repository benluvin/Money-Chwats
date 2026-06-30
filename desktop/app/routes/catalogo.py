"""CRUD del catálogo de productos: GET/POST/DELETE /catalogo."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_config
from ..pipeline import catalogo as cat

router = APIRouter(tags=["catalogo"])


class ProductoIn(BaseModel):
    producto_id: str | None = None
    nombre: str
    precio: str = ""
    descripcion: str = ""


@router.get("/catalogo")
def listar_catalogo() -> dict:
    rows = cat.listar(get_config())
    return {"data": rows, "total": len(rows)}


@router.post("/catalogo")
def guardar_producto(req: ProductoIn) -> dict:
    if not req.nombre.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El nombre es obligatorio.")
    nuevo = cat.upsert(
        get_config(),
        nombre=req.nombre,
        precio=req.precio,
        descripcion=req.descripcion,
        producto_id=req.producto_id,
    )
    return {"ok": True, "producto": nuevo}


@router.delete("/catalogo/{producto_id}")
def borrar_producto(producto_id: str) -> dict:
    ok = cat.eliminar(get_config(), producto_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado.")
    return {"ok": True}

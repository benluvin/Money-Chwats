"""Catálogo de productos del negocio.

El usuario lo administra desde la app (añadir/editar/borrar productos). Sirve para
dos cosas: (1) referencia humana, y (2) contexto para el LLM, que así reconoce mejor
los productos y precios reales al interpretar pedidos.

Se guarda en data/catalogo.csv con el mismo separador/encoding del resto.
"""
from __future__ import annotations

import csv
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import AppConfig
from ..utils.paths import data_dir

CATALOGO_COLUMNS = ["producto_id", "nombre", "precio", "descripcion", "fecha_actualizado"]


@dataclass
class Producto:
    producto_id: str
    nombre: str
    precio: str
    descripcion: str
    fecha_actualizado: str


def _path(cfg: AppConfig) -> Path:
    return data_dir(cfg.storage.root_path) / "catalogo.csv"


def listar(cfg: AppConfig) -> list[dict]:
    p = _path(cfg)
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f, delimiter=cfg.csv.separator)]


def _escribir(cfg: AppConfig, filas: list[dict]) -> None:
    p = _path(cfg)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding=cfg.csv.encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=CATALOGO_COLUMNS, delimiter=cfg.csv.separator)
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in CATALOGO_COLUMNS})
    os.replace(tmp, p)


def upsert(cfg: AppConfig, nombre: str, precio: str, descripcion: str,
           producto_id: str | None = None) -> dict:
    """Crea o actualiza un producto. Si viene producto_id, edita; si no, crea."""
    filas = listar(cfg)
    pid = producto_id or str(uuid.uuid4())
    nueva = {
        "producto_id": pid,
        "nombre": nombre.strip(),
        "precio": str(precio).strip(),
        "descripcion": descripcion.strip(),
        "fecha_actualizado": datetime.now().isoformat(timespec="seconds"),
    }
    reemplazado = False
    for i, fila in enumerate(filas):
        if fila.get("producto_id") == pid:
            filas[i] = nueva
            reemplazado = True
            break
    if not reemplazado:
        filas.append(nueva)
    _escribir(cfg, filas)
    return nueva


def eliminar(cfg: AppConfig, producto_id: str) -> bool:
    filas = listar(cfg)
    quedan = [f for f in filas if f.get("producto_id") != producto_id]
    if len(quedan) == len(filas):
        return False
    _escribir(cfg, quedan)
    return True


def texto_para_prompt(cfg: AppConfig) -> str:
    """Render del catálogo para inyectar en el prompt del LLM."""
    filas = listar(cfg)
    if not filas:
        return "(sin catálogo configurado)"
    lineas = []
    for f in filas:
        precio = f.get("precio", "").strip()
        desc = f.get("descripcion", "").strip()
        partes = [f"- {f.get('nombre', '').strip()}"]
        if precio:
            partes.append(f": ${precio} COP")
        if desc:
            partes.append(f" — {desc}")
        lineas.append("".join(partes))
    return "\n".join(lineas)

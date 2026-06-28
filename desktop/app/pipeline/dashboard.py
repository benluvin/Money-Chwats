"""Resumen de avance leído de las tablas — base del tablero (sin Hermes)."""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import AppConfig
from ..utils.paths import data_dir


def _read_rows(path: Path, sep: str, enc: str) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding=enc, newline="") as f:
        return list(csv.DictReader(f, delimiter=sep))


def _to_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def build_dashboard(cfg: AppConfig) -> dict:
    d = data_dir(cfg.storage.root_path)
    sep, enc = cfg.csv.separator, cfg.csv.encoding
    clientes = _read_rows(d / "clientes.csv", sep, enc)
    pedidos = _read_rows(d / "pedidos.csv", sep, enc)

    def cuenta(col: str) -> int:
        return sum(1 for c in clientes if c.get(col) == "true")

    return {
        "clientes_total": len(clientes),
        "clientes_requieren_revision": cuenta("requiere_revision"),
        "clientes_multimedia_pendiente": cuenta("multimedia_pendiente"),
        "clientes_telefono_pendiente": cuenta("telefono_pendiente"),
        "pedidos_total": len(pedidos),
        "monto_total_pedidos": round(sum(_to_float(p.get("monto_total", "")) for p in pedidos), 2),
        "audios_pendientes": sum(int(_to_float(c.get("audios_detectados", "0"))) for c in clientes),
        "imagenes_pendientes": sum(int(_to_float(c.get("imagenes_detectados", "0"))) for c in clientes),
    }

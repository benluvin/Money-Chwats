"""Vigilante de carpeta: procesa solo los .txt de 'Exportar chat' que aparezcan
en la carpeta-buzón. Es la comodidad "sin Hermes": tú exportas, él importa.

Sin dependencias extra: usa sondeo (polling) cada N segundos. El estado de lo ya
procesado se guarda en data/import_state.json (clave: nombre+tamaño del archivo),
así no reprocesa lo mismo aunque reinicies el servicio.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from ..config import AppConfig
from ..structurer.base import Structurer
from ..utils.paths import data_dir
from .import_pipeline import import_export_file

log = logging.getLogger("money_chwats.watcher")

POLL_SECONDS = 4


def _state_path(cfg: AppConfig) -> Path:
    return data_dir(cfg.storage.root_path) / "import_state.json"


def load_state(cfg: AppConfig) -> dict:
    p = _state_path(cfg)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"procesados": {}}


def save_state(cfg: AppConfig, state: dict) -> None:
    _state_path(cfg).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(f: Path) -> str:
    try:
        return f"{f.name}::{f.stat().st_size}"
    except OSError:
        return f.name


def pending_files(cfg: AppConfig) -> list[Path]:
    """Archivos .txt en el buzón que aún no se han procesado."""
    inbox = cfg.export.inbox_dir
    if not inbox:
        return []
    folder = Path(inbox).expanduser()
    if not folder.is_dir():
        return []
    state = load_state(cfg)
    done = set(state.get("procesados", {}).keys())
    return [f for f in sorted(folder.glob("*.txt")) if _key(f) not in done]


async def scan_inbox_once(cfg: AppConfig, structurer: Structurer) -> list[dict]:
    """Procesa todos los archivos nuevos del buzón. Devuelve un resumen por archivo."""
    state = load_state(cfg)
    procesados = state.setdefault("procesados", {})
    resultados: list[dict] = []

    for f in pending_files(cfg):
        try:
            out = await import_export_file(cfg, f, structurer)
            info = {
                "archivo": f.name,
                "cliente_id": out.cliente_id,
                "nombre": out.nombre,
                "pedidos": out.pedidos_added,
                "multimedia_total": out.media.get("total", 0),
                "requiere_revision": out.requiere_revision,
                "ts": datetime.now().isoformat(timespec="seconds"),
                "ok": True,
            }
        except Exception as exc:  # noqa: BLE001 - registramos cualquier fallo por archivo
            log.warning("No se pudo importar %s: %s", f.name, exc)
            info = {"archivo": f.name, "ok": False, "error": str(exc),
                    "ts": datetime.now().isoformat(timespec="seconds")}
        procesados[_key(f)] = info
        resultados.append(info)

    if resultados:
        save_state(cfg, state)
    return resultados


async def watch_loop(cfg: AppConfig, build_structurer) -> None:
    """Bucle de fondo: revisa el buzón cada POLL_SECONDS."""
    inbox = cfg.export.inbox_dir
    log.info("Vigilante de carpeta activo en: %s", inbox)
    while True:
        try:
            res = await scan_inbox_once(cfg, build_structurer(cfg))
            for r in res:
                if r.get("ok"):
                    log.info("Importado %s → %s (%d pedidos)", r["archivo"], r["nombre"], r["pedidos"])
        except Exception as exc:  # noqa: BLE001
            log.warning("Error en el vigilante: %s", exc)
        await asyncio.sleep(POLL_SECONDS)

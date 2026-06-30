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
import re
from datetime import datetime
from pathlib import Path

from ..config import AppConfig
from ..structurer.base import Structurer
from ..utils.paths import data_dir
from .import_pipeline import import_export_file

log = logging.getLogger("money_chwats.watcher")

POLL_SECONDS = 4

# Patrón de nombre de archivo de "Exportar chat" de WhatsApp. Sirve para que el
# vigilante pueda observar una carpeta compartida (p. ej. Descargas) sin procesar
# archivos ajenos. WhatsApp nombra los exports así:
#   - iOS:           "_chat.txt", "_chat 2.txt"
#   - Android ES:    "Chat de WhatsApp con <nombre>.txt"
#   - Android EN:    "WhatsApp Chat with <name>.txt"
#   - Desktop (Mac): "WhatsApp Chat - <nombre>.zip"  (con _chat.txt adentro)
_EXPORT_WHATSAPP_RE = re.compile(r"(^_chat\b)|(whatsapp)", re.IGNORECASE)

# Extensiones que el vigilante acepta como export de WhatsApp.
_EXTENSIONES_EXPORT = ("*.txt", "*.zip")


def es_export_whatsapp(f: Path) -> bool:
    return bool(_EXPORT_WHATSAPP_RE.search(f.name))


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


def get_baseline(cfg: AppConfig) -> float:
    """Marca de tiempo PERSISTENTE desde la cual se vigilan exports nuevos.

    Se fija una sola vez (la primera vez que arranca el vigilante) y NO se mueve
    en cada reinicio. Así "desde que empecé a usar la app" se respeta de verdad:
    los exports que llegan mientras tanto se procesan; el histórico previo no.
    """
    import time

    state = load_state(cfg)
    ts = state.get("vigilancia_desde")
    if ts is None:
        ts = time.time()
        state["vigilancia_desde"] = ts
        save_state(cfg, state)
    return float(ts)


def _key(f: Path) -> str:
    try:
        return f"{f.name}::{f.stat().st_size}"
    except OSError:
        return f.name


def _llego_despues(f: Path, since_ts: float | None) -> bool:
    """True si el archivo se modificó después de since_ts (o si no hay corte)."""
    if since_ts is None:
        return True
    try:
        return f.stat().st_mtime >= since_ts
    except OSError:
        return False


def pending_files(cfg: AppConfig, since_ts: float | None = None) -> list[Path]:
    """Archivos .txt en el buzón aún sin procesar.

    Si se pasa `since_ts`, ignora los que existían/se modificaron antes de ese
    instante: el vigilante solo procesa conversaciones que lleguen DESPUÉS de
    arrancar, no el histórico que ya estaba en la carpeta.
    """
    inbox = cfg.export.inbox_dir
    if not inbox:
        return []
    folder = Path(inbox).expanduser()
    if not folder.is_dir():
        return []
    state = load_state(cfg)
    done = set(state.get("procesados", {}).keys())
    candidatos = sorted(
        f for patron in _EXTENSIONES_EXPORT for f in folder.glob(patron)
    )
    return [
        f for f in candidatos
        if es_export_whatsapp(f) and _key(f) not in done and _llego_despues(f, since_ts)
    ]


async def scan_inbox_once(
    cfg: AppConfig, structurer: Structurer, since_ts: float | None = None
) -> list[dict]:
    """Procesa todos los archivos nuevos del buzón. Devuelve un resumen por archivo."""
    state = load_state(cfg)
    procesados = state.setdefault("procesados", {})
    resultados: list[dict] = []

    for f in pending_files(cfg, since_ts):
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
        # Solo marcamos como procesado si SALIÓ BIEN. Un fallo (Nemotron caído,
        # red) se reintenta en el próximo barrido en vez de perderse para siempre.
        if info.get("ok"):
            procesados[_key(f)] = info
        resultados.append(info)

    if any(r.get("ok") for r in resultados):
        save_state(cfg, state)
    return resultados


async def watch_loop(cfg: AppConfig, build_structurer) -> None:
    """Bucle de fondo: revisa el buzón cada POLL_SECONDS.

    Usa una marca de tiempo PERSISTENTE (get_baseline): solo procesa exports que
    lleguen a partir de ese instante, nunca el histórico previo. Como es persistente,
    los reinicios no mueven la línea de corte.
    """
    inbox = cfg.export.inbox_dir
    arranque = get_baseline(cfg)
    log.info(
        "Vigilante de carpeta activo en: %s (exports nuevos desde %s)",
        inbox, datetime.fromtimestamp(arranque).isoformat(timespec="seconds"),
    )
    while True:
        try:
            res = await scan_inbox_once(cfg, build_structurer(cfg), since_ts=arranque)
            for r in res:
                if r.get("ok"):
                    log.info("Importado %s → %s (%d pedidos)", r["archivo"], r["nombre"], r["pedidos"])
        except Exception as exc:  # noqa: BLE001
            log.warning("Error en el vigilante: %s", exc)
        await asyncio.sleep(POLL_SECONDS)

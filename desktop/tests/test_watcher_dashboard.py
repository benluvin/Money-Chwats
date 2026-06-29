"""Tests del vigilante de carpeta y el tablero."""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import AppConfig, ExportConfig, StorageConfig
from app.pipeline.dashboard import build_dashboard
from app.pipeline.watcher import pending_files, scan_inbox_once
from app.structurer.rules import RulesStructurer

EXPORT = """[10/06/26, 6:25:13 p. m.] Migue: Hola
[10/06/26, 6:26:00 p. m.] Cliente Z: Quiero 1 caja, son $30.000
[10/06/26, 6:27:00 p. m.] Cliente Z: audio omitido"""


def _cfg(tmp: Path, inbox: Path) -> AppConfig:
    return AppConfig(
        storage=StorageConfig(root=str(tmp)),
        export=ExportConfig(owner_name="Migue", inbox_dir=str(inbox)),
    )


def test_vigilante_procesa_y_no_repite(tmp_path: Path):
    inbox = tmp_path / "buzon"
    inbox.mkdir()
    (inbox / "Chat de WhatsApp con Cliente Z.txt").write_text(EXPORT, encoding="utf-8")
    cfg = _cfg(tmp_path, inbox)

    # Hay 1 pendiente
    assert len(pending_files(cfg)) == 1

    res1 = asyncio.run(scan_inbox_once(cfg, RulesStructurer()))
    assert len(res1) == 1 and res1[0]["ok"]

    # Ya no quedan pendientes y no reprocesa
    assert len(pending_files(cfg)) == 0
    res2 = asyncio.run(scan_inbox_once(cfg, RulesStructurer()))
    assert res2 == []


def test_dashboard_resume(tmp_path: Path):
    inbox = tmp_path / "buzon"
    inbox.mkdir()
    (inbox / "Chat de WhatsApp con Cliente Z.txt").write_text(EXPORT, encoding="utf-8")
    cfg = _cfg(tmp_path, inbox)
    asyncio.run(scan_inbox_once(cfg, RulesStructurer()))

    dash = build_dashboard(cfg)
    assert dash["clientes_total"] == 1
    assert dash["clientes_multimedia_pendiente"] == 1
    assert dash["audios_pendientes"] == 1
    assert dash["pedidos_total"] >= 1

"""Test del pipeline de importación (Export → tablas), con backend de reglas."""
from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from app.config import AppConfig, ExportConfig, StorageConfig
from app.pipeline.import_pipeline import import_export_file
from app.structurer.rules import RulesStructurer

EXPORT = """[10/06/26, 6:25:13 p. m.] Migue: Hola, ¿cómo vas?
[10/06/26, 6:37:01 p. m.] Cliente X: Quiero 2 cajas
[10/06/26, 6:38:00 p. m.] Migue: Son $50.000
[10/06/26, 6:39:00 p. m.] Cliente X: audio omitido
[10/06/26, 6:40:00 p. m.] Cliente X: Listo, gracias"""


def _cfg(tmp: Path) -> AppConfig:
    return AppConfig(storage=StorageConfig(root=str(tmp)),
                     export=ExportConfig(owner_name="Migue"))


def test_import_genera_tablas(tmp_path: Path):
    src = tmp_path / "_chat.txt"
    src.write_text(EXPORT, encoding="utf-8")
    cfg = _cfg(tmp_path)

    out = asyncio.run(import_export_file(cfg, src, RulesStructurer()))

    assert out.nombre == "Cliente X"
    assert out.media["audios"] == 1
    assert out.metodo_extraccion == "export+rules"

    # clientes.csv tiene la fila con columnas nuevas
    with (tmp_path / "data" / "clientes.csv").open(encoding="utf-8-sig", newline="") as f:
        clientes = list(csv.DictReader(f, delimiter=";"))
    assert len(clientes) == 1
    fila = clientes[0]
    assert fila["nombre"] == "Cliente X"
    assert fila["audios_detectados"] == "1"
    assert fila["multimedia_pendiente"] == "true"
    assert fila["metodo_extraccion"] == "export+rules"

    # pedidos.csv referencia el cliente_id
    with (tmp_path / "data" / "pedidos.csv").open(encoding="utf-8-sig", newline="") as f:
        pedidos = list(csv.DictReader(f, delimiter=";"))
    assert len(pedidos) >= 1
    assert pedidos[0]["cliente_id"] == fila["cliente_id"]


def test_import_telefono_pendiente_sin_telefono(tmp_path: Path):
    src = tmp_path / "_chat.txt"
    src.write_text(EXPORT, encoding="utf-8")  # no hay teléfono en el texto
    out = asyncio.run(import_export_file(_cfg(tmp_path), src, RulesStructurer()))
    assert out.telefono_pendiente is True

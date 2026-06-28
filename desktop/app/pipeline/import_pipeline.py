"""Importa un archivo 'Exportar chat' → estructura → tablas Clientes/Pedidos.

Reutilizable por el endpoint /import y por el vigilante de carpeta. No depende de
FastAPI; recibe la config, la ruta del archivo y un estructurador ya construido.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import AppConfig
from ..models.extraction import (
    CLIENTES_COLUMNS,
    PEDIDOS_COLUMNS,
    ExtractionResult,
    cliente_row_dict,
    pedido_row_dict,
)
from ..structurer.base import Structurer, StructureContext
from .csv_writer import CsvLockedError, append_pedido_rows, upsert_cliente_row
from .export_reader import parse_export
from .text_sources import FuenteTexto

log = logging.getLogger("money_chwats.import")


class ImportError_(RuntimeError):
    pass


@dataclass
class ImportOutcome:
    cliente_id: str
    nombre: str
    nickname: str
    extraction: ExtractionResult
    pedidos_added: int
    telefono_pendiente: bool
    requiere_revision: bool
    media: dict
    metodo_extraccion: str
    csv_pending: bool


async def import_export_file(
    cfg: AppConfig, path: Path, structurer: Structurer
) -> ImportOutcome:
    if not path.is_file():
        raise ImportError_(f"Archivo no existe: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_export(text, owner_name=cfg.export.owner_name or None)
    if not parsed.fuente.lineas:
        raise ImportError_("No se reconocieron mensajes (¿es un export de WhatsApp?).")

    ctx = StructureContext(
        nombre_contacto=parsed.nombre_contacto,
        fecha_captura=datetime.now().date(),
        moneda_default=cfg.locale.default_currency,
    )
    extraction = await structurer.structure(parsed.fuente, context=ctx)

    metodo = f"export+{structurer.nombre}"
    modelo = (
        cfg.cloud.model if structurer.nombre == "nemotron"
        else cfg.llm.model if structurer.nombre == "local"
        else "reglas"
    )

    # Identidad: teléfono si lo hay; si no, nombre del contacto (push name).
    phone = extraction.cliente.telefono or ""
    nombre = parsed.nombre_contacto or extraction.cliente.nombre or "(sin nombre)"
    telefono_pendiente = not bool(phone)
    seed = phone or nombre
    cliente_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cliente:{seed}"))

    # nickname = nombre alterno que infiera el modelo (si difiere del push name).
    llm_name = extraction.cliente.nombre or ""
    nickname = llm_name if (llm_name and llm_name != nombre) else ""
    # El "nombre" de la fila será el confiable del export.
    extraction.cliente.nombre = nombre

    # Copiar el .txt como evidencia.
    rel_ev = ""
    try:
        from ..utils.paths import exports_dir
        dest = exports_dir(cfg.storage.root_path) / f"{cliente_id}.txt"
        shutil.copyfile(path, dest)
        rel_ev = str(dest.relative_to(cfg.storage.root_path))
    except OSError:
        pass

    redacted = f"{phone[:-7]} *** {phone[-4:]}" if phone and len(phone) > 6 else ""
    monto_total = sum((p.monto_total or 0.0) for p in extraction.pedidos) or None
    thr = cfg.extraction.review_threshold
    requiere_revision = (
        extraction.cliente.confianza_extraccion < thr
        or parsed.media.hay_multimedia
        or any(p.confianza_extraccion < thr for p in extraction.pedidos)
    )

    fecha = datetime.now()
    cliente_dict = cliente_row_dict(
        cliente_id=cliente_id,
        extracted=extraction.cliente,
        telefono_completo=phone,
        telefono_redactado=redacted,
        total_pedidos_detectados=len(extraction.pedidos),
        monto_total_pedidos=monto_total,
        requiere_revision=requiere_revision,
        ruta_imagen_evidencia=rel_ev,
        fecha_captura=fecha,
        modelo_llm=modelo,
        metodo_extraccion=metodo,
        nickname=nickname,
        telefono_pendiente=telefono_pendiente,
        audios_detectados=parsed.media.audio,
        imagenes_detectados=parsed.media.imagen,
        videos_detectados=parsed.media.video,
    )

    pedido_dicts = []
    for p in extraction.pedidos:
        pid_seed = f"{cliente_id}|{p.producto_servicio}|{p.fecha_pedido}|{p.mensaje_origen[:50]}"
        pedido_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pedido:{pid_seed}"))
        pedido_dicts.append(
            pedido_row_dict(
                pedido_id=pedido_id,
                cliente_id=cliente_id,
                cliente_nombre=nombre,
                cliente_telefono_redactado=redacted,
                extracted=p,
                requiere_revision=p.confianza_extraccion < thr,
                ruta_imagen_evidencia=rel_ev,
                fecha_captura=fecha,
                modelo_llm=modelo,
                metodo_extraccion=metodo,
            )
        )

    from ..utils.paths import data_dir
    csv_pending = False
    try:
        upsert_cliente_row(
            cliente_dict, columns=CLIENTES_COLUMNS, id_column="cliente_id",
            csv_path=data_dir(cfg.storage.root_path) / "clientes.csv",
            separator=cfg.csv.separator, encoding=cfg.csv.encoding,
        )
        append_pedido_rows(
            pedido_dicts, columns=PEDIDOS_COLUMNS,
            csv_path=data_dir(cfg.storage.root_path) / "pedidos.csv",
            separator=cfg.csv.separator, encoding=cfg.csv.encoding,
        )
    except CsvLockedError as exc:
        log.warning("CSV bloqueado: %s", exc)
        csv_pending = True

    return ImportOutcome(
        cliente_id=cliente_id,
        nombre=nombre,
        nickname=nickname,
        extraction=extraction,
        pedidos_added=len(pedido_dicts),
        telefono_pendiente=telefono_pendiente,
        requiere_revision=requiere_revision,
        media={"audios": parsed.media.audio, "imagenes": parsed.media.imagen,
               "videos": parsed.media.video, "total": parsed.media.total},
        metodo_extraccion=metodo,
        csv_pending=csv_pending,
    )

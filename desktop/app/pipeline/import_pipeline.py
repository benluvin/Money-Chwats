"""Importa 'Exportar chat' en DOS FASES:

  1) crear_cliente_base: instantáneo. Crea el cliente con datos DETERMINISTAS
     (nombre exacto del chat, teléfono, fechas, multimedia). estado="pendiente".
  2) analizar_cliente: corre la cascada de modelos (Nemotron → backup → reglas)
     sobre la evidencia guardada y rellena PEDIDOS + campos interpretativos.

Así el cliente aparece al instante y el análisis llega después. La función
import_export_file hace las dos fases seguidas (la usa el vigilante y los tests).
"""
from __future__ import annotations

import csv
import logging
import uuid
import zipfile
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
from ..structurer.base import Structurer, StructureContext, StructurerError
from ..utils.paths import data_dir, exports_dir
from ..utils.telefono import normalizar_telefono
from .csv_writer import CsvLockedError, append_pedido_rows, upsert_cliente_row
from .export_reader import parse_export
from .text_sources import FuenteTexto, Linea

log = logging.getLogger("money_chwats.import")


def _fuente_desde_texto_ocr(text: str) -> FuenteTexto:
    """Reconstruye una FuenteTexto desde evidencia OCR ('[NEGOCIO] msg' / '[CLIENTE] msg')."""
    lineas: list[Linea] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        emisor = "desconocido"
        if s.startswith("[NEGOCIO]"):
            emisor, s = "negocio", s[len("[NEGOCIO]"):].strip()
        elif s.startswith("[CLIENTE]"):
            emisor, s = "cliente", s[len("[CLIENTE]"):].strip()
        elif s.startswith("[?]"):
            s = s[3:].strip()
        if s:
            lineas.append(Linea(texto=s, emisor=emisor))
    return FuenteTexto(tipo="ocr", lineas=lineas)


class ImportError_(RuntimeError):
    pass


@dataclass
class ImportOutcome:
    cliente_id: str
    nombre: str
    nickname: str
    extraction: ExtractionResult | None
    pedidos_added: int
    telefono_pendiente: bool
    requiere_revision: bool
    media: dict
    metodo_extraccion: str
    csv_pending: bool


def leer_texto_export(path: Path) -> str:
    """Texto del export, sea .txt o .zip (WhatsApp Desktop comprime en .zip)."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            nombres = z.namelist()
            interno = next(
                (n for n in nombres if n.lower().endswith("_chat.txt")),
                next((n for n in nombres if n.lower().endswith(".txt")), None),
            )
            if not interno:
                raise ImportError_("El .zip no contiene ningún .txt de chat.")
            return z.read(interno).decode("utf-8", errors="replace")
    return path.read_text(encoding="utf-8", errors="replace")


# ── Lectura de filas existentes ───────────────────────────────────────────────

def _leer_cliente(cfg: AppConfig, cliente_id: str) -> dict | None:
    p = data_dir(cfg.storage.root_path) / "clientes.csv"
    if not p.exists():
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=cfg.csv.separator):
            if r.get("cliente_id") == cliente_id:
                return dict(r)
    return None


# ── FASE 1: cliente instantáneo (determinista, sin IA) ────────────────────────

@dataclass
class BaseOutcome:
    cliente_id: str
    nombre: str
    telefono: str
    telefono_pendiente: bool
    media: dict
    evidencia_rel: str
    nombre_contacto: str | None


async def crear_cliente_base(cfg: AppConfig, path: Path) -> BaseOutcome:
    if not path.is_file():
        raise ImportError_(f"Archivo no existe: {path}")
    text = leer_texto_export(path)
    parsed = parse_export(text, owner_name=cfg.export.owner_name or None)
    if not parsed.fuente.lineas:
        raise ImportError_("No se reconocieron mensajes (¿es un export de WhatsApp?).")

    # Nombre EXACTO del chat. Teléfono determinista (+ agenda solo si falta).
    nombre = parsed.nombre_contacto or "(sin nombre)"
    phone = parsed.telefono_contacto or ""
    if not phone:
        from .contactos import buscar as buscar_contacto
        match = buscar_contacto(cfg, nombre=nombre, telefono=None)
        if match and match.get("telefono"):
            phone = match["telefono"]
    telefono_pendiente = not bool(phone)

    cliente_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cliente:{phone or nombre}"))

    # Evidencia: el texto del chat, indexado por cliente_id (para reanalizar).
    rel_ev = ""
    try:
        dest = exports_dir(cfg.storage.root_path) / f"{cliente_id}.txt"
        dest.write_text(text, encoding="utf-8")
        rel_ev = str(dest.relative_to(cfg.storage.root_path))
    except OSError:
        pass

    # Fila base: deterministas + estado "pendiente". Si el cliente ya existe,
    # conservamos sus campos interpretativos (no los borramos mientras reanaliza).
    existente = _leer_cliente(cfg, cliente_id)
    redacted = f"{phone[:-7]} *** {phone[-4:]}" if phone and len(phone) > 6 else ""
    fila = {c: (existente.get(c, "") if existente else "") for c in CLIENTES_COLUMNS}
    fila.update({
        "cliente_id": cliente_id,
        "nombre": nombre,
        "telefono_completo": phone,
        "telefono_redactado": redacted,
        "telefono_pendiente": "true" if telefono_pendiente else "false",
        "primer_mensaje_fecha": fila.get("primer_mensaje_fecha") or "",
        "audios_detectados": str(parsed.media.audio),
        "imagenes_detectados": str(parsed.media.imagen),
        "videos_detectados": str(parsed.media.video),
        "multimedia_pendiente": "true" if parsed.media.hay_multimedia else "false",
        "ruta_imagen_evidencia": rel_ev,
        "fecha_creacion": (existente.get("fecha_creacion") if existente else "") or datetime.now().isoformat(timespec="seconds"),
        "fecha_captura": datetime.now().isoformat(timespec="seconds"),
        "metodo_extraccion": "export+pendiente",
        "estado_analisis": "pendiente",
        "version_schema": fila.get("version_schema") or "clientes-1",
    })
    try:
        upsert_cliente_row(
            fila, columns=CLIENTES_COLUMNS, id_column="cliente_id",
            csv_path=data_dir(cfg.storage.root_path) / "clientes.csv",
            separator=cfg.csv.separator, encoding=cfg.csv.encoding,
        )
    except CsvLockedError as exc:
        log.warning("CSV bloqueado al crear base: %s", exc)

    return BaseOutcome(
        cliente_id=cliente_id, nombre=nombre, telefono=phone,
        telefono_pendiente=telefono_pendiente,
        media={"audios": parsed.media.audio, "imagenes": parsed.media.imagen,
               "videos": parsed.media.video, "total": parsed.media.total},
        evidencia_rel=rel_ev, nombre_contacto=parsed.nombre_contacto,
    )


# ── FASE 2: análisis con cascada (+ fallback offline) ─────────────────────────

def _pedidos_no_auto(cfg: AppConfig, cliente_id: str) -> tuple[list[dict], list[dict]]:
    """Separa pedidos del cliente en (a conservar manuales, a reemplazar auto)."""
    p = data_dir(cfg.storage.root_path) / "pedidos.csv"
    if not p.exists():
        return [], []
    with open(p, encoding="utf-8-sig", newline="") as f:
        filas = [dict(r) for r in csv.DictReader(f, delimiter=cfg.csv.separator)]
    conservar, reemplazables = [], []
    for r in filas:
        if r.get("cliente_id") != cliente_id:
            conservar.append(r)  # de otros clientes: intactos
        elif r.get("metodo_extraccion") == "manual" or str(r.get("editado_manualmente")).lower() == "true":
            conservar.append(r)  # manuales del cliente: se respetan
        else:
            reemplazables.append(r)  # auto del cliente: se reemplazan
    return conservar, reemplazables


def _escribir_pedidos(cfg: AppConfig, filas: list[dict]) -> None:
    import os
    p = data_dir(cfg.storage.root_path) / "pedidos.csv"
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding=cfg.csv.encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=PEDIDOS_COLUMNS, delimiter=cfg.csv.separator)
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in PEDIDOS_COLUMNS})
    os.replace(tmp, p)


async def analizar_cliente(
    cfg: AppConfig, cliente_id: str, structurer: Structurer | None = None
) -> dict:
    """Corre la cascada sobre la evidencia y rellena pedidos + interpretación."""
    existente = _leer_cliente(cfg, cliente_id)
    if not existente:
        raise ImportError_("Cliente no existe.")
    ev = exports_dir(cfg.storage.root_path) / f"{cliente_id}.txt"
    if not ev.exists():
        raise ImportError_("No hay evidencia guardada para reanalizar este cliente.")
    text = ev.read_text(encoding="utf-8", errors="replace")
    parsed = parse_export(text, owner_name=cfg.export.owner_name or None)
    # Si la evidencia no es un export de WhatsApp (p. ej. texto OCR), la
    # reconstruimos para que el modelo igual pueda analizarla.
    if not parsed.fuente.lineas:
        fuente = _fuente_desde_texto_ocr(text)
    else:
        fuente = parsed.fuente

    if structurer is None:
        from ..structurer.factory import build_structurer
        structurer = build_structurer(cfg)

    from .catalogo import texto_para_prompt
    from ..structurer.rules import RulesStructurer
    ctx = StructureContext(
        nombre_contacto=existente.get("nombre"),
        fecha_captura=datetime.now().date(),
        moneda_default=cfg.locale.default_currency,
        catalogo_texto=texto_para_prompt(cfg),
    )
    backend_usado = getattr(structurer, "nombre", "?")
    hubo_fallback = False
    try:
        extraction = await structurer.structure(fuente, context=ctx)
        backend_usado = getattr(structurer, "ultimo_backend", "") or backend_usado
    except StructurerError as exc:
        log.warning("Análisis '%s' falló (%s) → fallback offline a reglas", cliente_id, exc)
        extraction = await RulesStructurer().structure(fuente, context=ctx)
        backend_usado = "rules(fallback)"
        hubo_fallback = True

    # Nombre/teléfono deterministas mandan, CON UNA EXCEPCIÓN: si el contacto NO
    # está guardado (su "nombre" es solo un número), usamos el nombre que el modelo
    # extrajo del CUERPO del chat (presentación, nombre de envío, cómo lo llaman).
    nombre = existente.get("nombre") or "(sin nombre)"
    phone = existente.get("telefono_completo") or ""
    redacted = existente.get("telefono_redactado") or ""

    from ..utils.telefono import es_telefono
    es_no_guardado = es_telefono(nombre) or (phone and nombre.strip() == phone)
    llm_name = (extraction.cliente.nombre or "").strip()
    nombre_inferido = es_no_guardado and llm_name and not es_telefono(llm_name)
    if nombre_inferido:
        nombre = llm_name
    extraction.cliente.nombre = nombre

    metodo = f"export+{backend_usado}"
    modelo = cfg.cloud.model if not hubo_fallback else "reglas"
    thr = cfg.extraction.review_threshold
    monto_total = sum((p.monto_total or 0.0) for p in extraction.pedidos) or None
    requiere_revision = (
        hubo_fallback
        or bool(nombre_inferido)  # nombre sacado del cuerpo: confírmalo de un vistazo
        or extraction.cliente.confianza_extraccion < thr
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
        ruta_imagen_evidencia=existente.get("ruta_imagen_evidencia", ""),
        fecha_captura=fecha,
        modelo_llm=modelo,
        metodo_extraccion=metodo,
        telefono_pendiente=not bool(phone),
        audios_detectados=parsed.media.audio,
        imagenes_detectados=parsed.media.imagen,
        videos_detectados=parsed.media.video,
        fecha_creacion=None,  # el upsert conserva la original
        estado_analisis="fallback" if hubo_fallback else "completo",
    )

    # Pedidos: conservar manuales del cliente y de otros; reemplazar los auto.
    conservar, _reemplazables = _pedidos_no_auto(cfg, cliente_id)
    nuevos = []
    for p in extraction.pedidos:
        pid_seed = f"{cliente_id}|{p.producto_servicio}|{p.fecha_pedido}|{p.mensaje_origen[:50]}"
        pedido_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pedido:{pid_seed}"))
        nuevos.append(pedido_row_dict(
            pedido_id=pedido_id, cliente_id=cliente_id, cliente_nombre=nombre,
            cliente_telefono_redactado=redacted, extracted=p,
            requiere_revision=p.confianza_extraccion < thr,
            ruta_imagen_evidencia=existente.get("ruta_imagen_evidencia", ""),
            fecha_captura=fecha, modelo_llm=modelo, metodo_extraccion=metodo,
        ))

    csv_pending = False
    try:
        upsert_cliente_row(
            cliente_dict, columns=CLIENTES_COLUMNS, id_column="cliente_id",
            csv_path=data_dir(cfg.storage.root_path) / "clientes.csv",
            separator=cfg.csv.separator, encoding=cfg.csv.encoding,
        )
        _escribir_pedidos(cfg, conservar + nuevos)
    except CsvLockedError as exc:
        log.warning("CSV bloqueado al analizar: %s", exc)
        csv_pending = True

    return {
        "cliente_id": cliente_id, "nombre": nombre, "pedidos": len(nuevos),
        "requiere_revision": requiere_revision, "fallback": hubo_fallback,
        "estado_analisis": "fallback" if hubo_fallback else "completo",
        "csv_pending": csv_pending, "ok": True,
    }


# ── Las dos fases seguidas (vigilante / tests) ────────────────────────────────

async def import_export_file(
    cfg: AppConfig, path: Path, structurer: Structurer
) -> ImportOutcome:
    base = await crear_cliente_base(cfg, path)
    res = await analizar_cliente(cfg, base.cliente_id, structurer)
    return ImportOutcome(
        cliente_id=base.cliente_id, nombre=base.nombre, nickname="",
        extraction=None, pedidos_added=res["pedidos"],
        telefono_pendiente=base.telefono_pendiente,
        requiere_revision=res["requiere_revision"], media=base.media,
        metodo_extraccion=f"export+{'rules' if res['fallback'] else 'nemotron'}",
        csv_pending=res["csv_pending"],
    )

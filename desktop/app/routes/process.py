"""POST /process/{capture_id}: corre OCR sobre la imagen, estructura el texto
(reglas / nube Nemotron / local) y escribe filas en clientes.csv + pedidos.csv."""
from __future__ import annotations

import csv
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_config
from ..models.capture import CSV_COLUMNS as CAPTURAS_COLUMNS
from ..models.extraction import (
    CLIENTES_COLUMNS,
    PEDIDOS_COLUMNS,
    ExtractionResult,
    cliente_row_dict,
    pedido_row_dict,
)
from ..pipeline.csv_writer import (
    CsvLockedError,
    append_pedido_rows,
    upsert_cliente_row,
)
from ..pipeline.ocr_client import OcrError, OcrNotInstalled, check_ocr_available, extract_from_image
from ..structurer.base import StructureContext, StructurerError
from ..structurer.factory import build_structurer
from ..utils.paths import data_dir, ocr_dir

router = APIRouter()
log = logging.getLogger("money_chwats.process")


class ProcessResponse(BaseModel):
    capture_id: str
    cliente_id: str
    extraction: ExtractionResult
    cliente_updated: bool
    pedidos_added: int
    requiere_revision: bool
    metodo_extraccion: str
    csv_pending: bool = False


@router.get("/llm/status")
async def pipeline_status() -> dict:
    """Estado del pipeline de extracción (OCR + backend estructurador)."""
    cfg = get_config()
    # OCR
    try:
        ocr_info = check_ocr_available()
        ocr_ready = True
    except OcrNotInstalled as e:
        ocr_info, ocr_ready = {"detail": str(e)}, False

    # Backend estructurador efectivo (con fallback resuelto).
    backend_cfg = cfg.extraction.backend
    backend_real = build_structurer(cfg).nombre
    selected = f"OCR + {backend_real}"
    ready = ocr_ready
    return {
        "enabled": cfg.ocr.enabled,
        "ready": ready,
        "selected": selected,
        "ocr": {"ready": ocr_ready, **ocr_info},
        "backend_configurado": backend_cfg,
        "backend_efectivo": backend_real,
        "cloud_enabled": cfg.cloud.enabled,
        "available_models": [selected],
    }


def _find_capture(root: Path, capture_id: str) -> tuple[Path, dict[str, str]] | None:
    csv_path = data_dir(root) / "capturas.csv"
    if not csv_path.exists():
        return None
    with csv_path.open(encoding=get_config().csv.encoding, newline="") as f:
        for r in csv.DictReader(f, delimiter=get_config().csv.separator):
            if r.get("capture_id") == capture_id:
                img_path = root / r["ruta_imagen"]
                return img_path, r
    return None


@router.post("/process/{capture_id}", response_model=ProcessResponse)
async def process_capture(capture_id: str) -> ProcessResponse:
    cfg = get_config()
    if not cfg.ocr.enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OCR deshabilitado en config.")

    root = cfg.storage.root_path
    found = _find_capture(root, capture_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capture_id no existe en capturas.csv")
    img_path, captura_row = found

    # 1. OCR: imagen → FuenteTexto
    try:
        check_ocr_available()
        fuente = extract_from_image(img_path)
    except OcrNotInstalled as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except OcrError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    # Guardar texto OCR como evidencia.
    (ocr_dir(root) / f"{capture_id}.txt").write_text(fuente.texto_completo, encoding="utf-8")

    # 2. Estructurar (reglas / nemotron / local)
    structurer = build_structurer(cfg)
    fecha_captura = datetime.fromisoformat(captura_row["fecha_captura"])
    ctx = StructureContext(
        nombre_contacto=None,
        fecha_captura=fecha_captura.date(),
        moneda_default=cfg.locale.default_currency,
    )
    try:
        extraction = await structurer.structure(fuente, context=ctx)
    except StructurerError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    metodo = f"ocr+{structurer.nombre}"
    modelo = cfg.cloud.model if structurer.nombre == "nemotron" else (
        cfg.llm.model if structurer.nombre == "local" else "reglas"
    )

    # 3. IDs + filas CSV
    phone = extraction.cliente.telefono or ""
    name = extraction.cliente.nombre or ""
    seed = phone or f"{name}|{captura_row.get('url', '')}"
    cliente_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cliente:{seed}"))
    rel_img = captura_row["ruta_imagen"]

    redacted = ""
    if phone and len(phone) > 6:
        redacted = f"{phone[:-7]} *** {phone[-4:]}"

    monto_total_pedidos = sum((p.monto_total or 0.0) for p in extraction.pedidos) or None
    thr = cfg.extraction.review_threshold
    requiere_revision = extraction.cliente.confianza_extraccion < thr or any(
        p.confianza_extraccion < thr for p in extraction.pedidos
    )

    cliente_dict = cliente_row_dict(
        cliente_id=cliente_id,
        extracted=extraction.cliente,
        telefono_completo=phone,
        telefono_redactado=redacted,
        total_pedidos_detectados=len(extraction.pedidos),
        monto_total_pedidos=monto_total_pedidos,
        requiere_revision=requiere_revision,
        ruta_imagen_evidencia=rel_img,
        fecha_captura=fecha_captura,
        modelo_llm=modelo,
        metodo_extraccion=metodo,
    )

    pedido_dicts = []
    for p in extraction.pedidos:
        pid_seed = f"{cliente_id}|{p.producto_servicio}|{p.fecha_pedido}|{p.mensaje_origen[:50]}"
        pedido_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"pedido:{pid_seed}"))
        pedido_dicts.append(
            pedido_row_dict(
                pedido_id=pedido_id,
                cliente_id=cliente_id,
                cliente_nombre=name,
                cliente_telefono_redactado=redacted,
                extracted=p,
                requiere_revision=p.confianza_extraccion < thr,
                ruta_imagen_evidencia=rel_img,
                fecha_captura=fecha_captura,
                modelo_llm=modelo,
                metodo_extraccion=metodo,
            )
        )

    csv_pending = False
    cliente_csv = data_dir(root) / "clientes.csv"
    pedidos_csv = data_dir(root) / "pedidos.csv"
    try:
        cliente_updated = upsert_cliente_row(
            cliente_dict,
            columns=CLIENTES_COLUMNS,
            id_column="cliente_id",
            csv_path=cliente_csv,
            separator=cfg.csv.separator,
            encoding=cfg.csv.encoding,
        )
        append_pedido_rows(
            pedido_dicts,
            columns=PEDIDOS_COLUMNS,
            csv_path=pedidos_csv,
            separator=cfg.csv.separator,
            encoding=cfg.csv.encoding,
        )
    except CsvLockedError as exc:
        log.warning("CSV bloqueado: %s", exc)
        csv_pending = True
        cliente_updated = False

    _mark_capture_processed(root, capture_id)

    return ProcessResponse(
        capture_id=capture_id,
        cliente_id=cliente_id,
        extraction=extraction,
        cliente_updated=cliente_updated,
        pedidos_added=len(pedido_dicts),
        requiere_revision=requiere_revision,
        metodo_extraccion=metodo,
        csv_pending=csv_pending,
    )


def _mark_capture_processed(root: Path, capture_id: str) -> None:
    cfg = get_config()
    csv_path = data_dir(root) / "capturas.csv"
    if not csv_path.exists():
        return
    with csv_path.open(encoding=cfg.csv.encoding, newline="") as f:
        rows = list(csv.DictReader(f, delimiter=cfg.csv.separator))
    changed = False
    for r in rows:
        if r.get("capture_id") == capture_id:
            if r.get("procesado") != "true":
                r["procesado"] = "true"
                changed = True
            break
    if not changed:
        return
    import io as _io

    buf = _io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CAPTURAS_COLUMNS, delimiter=cfg.csv.separator, lineterminator="\n")
    writer.writeheader()
    writer.writerows({c: r.get(c, "") for c in CAPTURAS_COLUMNS} for r in rows)
    csv_path.write_text(buf.getvalue(), encoding=cfg.csv.encoding)

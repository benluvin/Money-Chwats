"""POST /capture: recibe screenshot(s) + metadata, los une, guarda PNG y registra CSV."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from ..config import get_config
from ..models.capture import CaptureRequest, CaptureRow
from ..pipeline.csv_writer import CsvLockedError, append_capture_row
from ..pipeline.storage import decode_png, relative_path, save_png, stitch_png_parts
from ..utils.paths import data_dir

router = APIRouter()
log = logging.getLogger("money_chwats.capture")


class CaptureResponse(BaseModel):
    capture_id: str
    status: str
    png_path: str
    png_path_abs: str
    parts_received: int
    csv_pending: bool = False


@router.post(
    "/capture",
    response_model=CaptureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def capture(req: CaptureRequest) -> CaptureResponse:
    cfg = get_config()
    root = cfg.storage.root_path

    capture_id = str(uuid.uuid4())
    parts_bytes = [decode_png(p) for p in req.screenshot_parts_b64]
    final_png = stitch_png_parts(parts_bytes)
    png_path = save_png(final_png, root=root, capture_id=capture_id, when=req.captured_at.date())
    rel = relative_path(png_path, root)

    row = CaptureRow(
        capture_id=capture_id,
        fecha_captura=req.captured_at,
        ruta_imagen=rel,
        url=req.tab_url or "",
        titulo=req.tab_title or "",
        contact_name=req.contact_name or "",
        procesado=False,
    )

    csv_path = data_dir(root) / "capturas.csv"
    csv_pending = False
    try:
        append_capture_row(
            row,
            csv_path=csv_path,
            separator=cfg.csv.separator,
            encoding=cfg.csv.encoding,
        )
    except CsvLockedError as exc:
        log.warning("CSV bloqueado: %s", exc)
        csv_pending = True

    log.info(
        "captura %s guardada (%d pedazo(s), final=%s bytes): %s",
        capture_id[:8], len(parts_bytes), len(final_png), rel,
    )
    return CaptureResponse(
        capture_id=capture_id,
        status="stored",
        png_path=rel,
        png_path_abs=str(png_path),
        parts_received=len(parts_bytes),
        csv_pending=csv_pending,
    )

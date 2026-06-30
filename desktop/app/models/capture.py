"""Modelo simple de captura: screenshot (uno o varios pedazos) + metadata mínima."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

SCHEMA_VERSION = "capturas-1.0"

CSV_COLUMNS = [
    "capture_id",
    "fecha_captura",
    "ruta_imagen",
    "url",
    "titulo",
    "contact_name",
    "procesado",
    "version_schema",
]


class CaptureRequest(BaseModel):
    client_version: str = "0.0.0"
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    tab_url: str | None = None
    tab_title: str | None = None
    # Nombre leído del ENCABEZADO de la conversación (DOM), exacto. Es la fuente
    # de verdad del nombre en modo OCR — no se deja a la IA.
    contact_name: str | None = None
    screenshot_parts_b64: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Uno o varios PNGs en base64. Si hay más de uno, se unen verticalmente "
            "(en el mismo orden) para producir una sola imagen final."
        ),
    )


class CaptureRow(BaseModel):
    capture_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fecha_captura: datetime
    ruta_imagen: str
    url: str = ""
    titulo: str = ""
    contact_name: str = ""
    procesado: bool = False
    version_schema: str = SCHEMA_VERSION

    def to_csv_dict(self) -> dict[str, str]:
        return {
            "capture_id": self.capture_id,
            "fecha_captura": self.fecha_captura.isoformat(timespec="seconds"),
            "ruta_imagen": self.ruta_imagen,
            "url": self.url or "",
            "titulo": self.titulo or "",
            "contact_name": self.contact_name or "",
            "procesado": "true" if self.procesado else "false",
            "version_schema": self.version_schema,
        }

"""Persistencia en disco de la captura. Une los pedazos verticalmente con Pillow
y guarda en WebP SIN PÉRDIDA (mucho más liviano que PNG, sin sacrificar nitidez
para el OCR). Acepta pedazos en PNG o WebP."""
from __future__ import annotations

import base64
import binascii
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image

from ..utils.paths import raw_dir_for

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Pillow tiene un límite por defecto contra "decompression bombs". Lo subimos para
# permitir imágenes muy altas (chats largos). El usuario opera localmente.
Image.MAX_IMAGE_PIXELS = None


def _is_png(data: bytes) -> bool:
    return data.startswith(PNG_MAGIC)


def _is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP"


def decode_image(b64: str) -> bytes:
    """Decodifica base64 y valida que sea PNG o WebP."""
    if "," in b64[:64]:
        b64 = b64.split(",", 1)[1]
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "screenshot no es base64 válido"
        ) from exc
    if not (_is_png(data) or _is_webp(data)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "screenshot no es una imagen PNG/WebP válida"
        )
    return data


# Alias retrocompatible.
decode_png = decode_image


def build_final_image(parts: list[bytes]) -> bytes:
    """Une N pedazos verticalmente y devuelve bytes WebP SIN PÉRDIDA."""
    images = [Image.open(BytesIO(p)) for p in parts]
    width = max(im.width for im in images)
    total_h = sum(im.height for im in images)
    # Conserva escala de grises si todos los pedazos vienen en gris; si no, RGB.
    mode = "L" if all(im.mode in ("L", "1") for im in images) else "RGB"
    bg = 255 if mode == "L" else (255, 255, 255)
    final = Image.new(mode, (width, total_h), bg)
    y = 0
    for im in images:
        final.paste(im.convert(mode), (0, y))
        y += im.height
        im.close()
    out = BytesIO()
    final.save(out, format="WEBP", lossless=True, method=4)
    final.close()
    return out.getvalue()


# Alias retrocompatible (la firma cambió de formato de salida).
stitch_png_parts = build_final_image


def save_image(image_bytes: bytes, *, root: Path, capture_id: str, when: date | None = None) -> Path:
    when = when or date.today()
    target = raw_dir_for(root, when) / f"{capture_id}.webp"
    target.write_bytes(image_bytes)
    return target


# Alias retrocompatible.
save_png = save_image


def relative_path(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)

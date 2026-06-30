"""Validación estricta de teléfonos.

Regla del proyecto: el teléfono NO se adivina del contenido del chat (precios,
cantidades, cédulas, etc.). Solo se acepta un número que tenga forma REAL de
teléfono. Así evitamos basura tipo "74.072174".

Fuentes válidas de teléfono:
  - Exportar chat: si el contacto NO está guardado, WhatsApp pone el número como
    remitente (ej. "+57 300 123 4567"). Ese es el teléfono.
  - OCR/DOM: solo si en el encabezado aparece un número con formato de teléfono.
  - Si el contacto está guardado, WhatsApp NO expone el número → queda pendiente
    y se completa a mano (y eso prevalece).
"""
from __future__ import annotations

import re

_LIMPIAR = re.compile(r"[\s\-().]")
# Celular colombiano: 10 dígitos empezando en 3, con o sin prefijo 57/+57.
_CO_CEL = re.compile(r"^(?:\+?57)?(3\d{9})$")
# Internacional explícito: + seguido de 7 a 15 dígitos.
_INTL = re.compile(r"^\+(\d{7,15})$")


def normalizar_telefono(valor: str | None) -> str | None:
    """Devuelve el teléfono normalizado (+57XXXXXXXXXX) o None si no es válido.

    Rechaza decimales/precios (con '.' o ','), números demasiado cortos/largos y
    cualquier cosa que no tenga forma clara de teléfono.
    """
    if not valor:
        return None
    s = str(valor).strip()
    # Un precio o decimal no es teléfono.
    if "." in s or "," in s:
        return None
    limpio = _LIMPIAR.sub("", s)
    if not limpio:
        return None

    m = _CO_CEL.match(limpio)
    if m:
        return "+57" + m.group(1)
    m = _INTL.match(limpio)
    if m:
        return "+" + m.group(1)
    return None


def es_telefono(valor: str | None) -> bool:
    return normalizar_telefono(valor) is not None

"""OCR local liviano (imagen → texto), detrás de una interfaz intercambiable.

Usa RapidOCR (modelos PP-OCR vía ONNXRuntime): corre en CPU, pesa pocos MB y no
requiere GPU ni paddlepaddle. Pensado para correr incluso en PCs de 4 GB de RAM.

Salida: una `FuenteTexto` con tipo "ocr", donde cada línea trae su texto, la
confianza del reconocimiento, y el emisor inferido por la posición horizontal
(burbujas a la derecha = negocio; a la izquierda = cliente, como en WhatsApp).

Las imágenes muy altas (capturas con scroll) se procesan en franjas verticales
con solape, para no cargar un bitmap gigante de una sola vez.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .text_sources import Emisor, FuenteTexto, Linea

log = logging.getLogger("money_chwats.ocr")

# Procesamiento por franjas para imágenes altas.
_FRANJA_ALTURA_PX = 2000
_FRANJA_SOLAPE_PX = 120


class OcrError(RuntimeError):
    pass


class OcrNotInstalled(OcrError):
    pass


def check_ocr_available() -> dict:
    """Verifica que RapidOCR esté instalado. Lanza OcrNotInstalled si no."""
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError as exc:
        raise OcrNotInstalled(
            "RapidOCR no está instalado. Ejecuta: "
            "`pip install rapidocr-onnxruntime` en el entorno del servicio."
        ) from exc
    return {"engine": "rapidocr-onnxruntime"}


# El motor se carga una sola vez (perezoso) y se reutiliza entre capturas.
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise OcrNotInstalled(
                "RapidOCR no está instalado (`pip install rapidocr-onnxruntime`)."
            ) from exc
        log.info("Cargando motor RapidOCR (una sola vez)…")
        _engine = RapidOCR()
    return _engine


def _emisor_por_posicion(centro_x: float, ancho_img: float) -> Emisor:
    """Derecha → negocio, izquierda → cliente. Banda central → desconocido."""
    if ancho_img <= 0:
        return "desconocido"
    frac = centro_x / ancho_img
    if frac >= 0.58:
        return "negocio"
    if frac <= 0.42:
        return "cliente"
    return "desconocido"


def extract_from_image(image_path: Path) -> FuenteTexto:
    """Corre OCR sobre la imagen y devuelve una FuenteTexto (tipo 'ocr')."""
    if not image_path.exists():
        raise OcrError(f"Imagen no existe: {image_path}")

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - deps base del proyecto
        raise OcrError(f"Falta dependencia de imagen: {exc}") from exc

    engine = _get_engine()

    with Image.open(image_path) as im:
        im = im.convert("RGB")
        ancho, alto = im.size
        arr_full = np.asarray(im)

    lineas: list[Linea] = []

    # Franjas verticales con solape para imágenes altas.
    y = 0
    while y < alto:
        y_fin = min(y + _FRANJA_ALTURA_PX, alto)
        franja = arr_full[y:y_fin, :, :]
        resultado, _ = engine(franja)
        if resultado:
            for caja, texto, score in resultado:
                if not texto or not texto.strip():
                    continue
                xs = [pt[0] for pt in caja]
                centro_x = sum(xs) / len(xs)
                lineas.append(
                    Linea(
                        texto=texto.strip(),
                        emisor=_emisor_por_posicion(centro_x, ancho),
                        confianza=float(score) if score is not None else 1.0,
                    )
                )
        if y_fin >= alto:
            break
        y = y_fin - _FRANJA_SOLAPE_PX

    # Quitar duplicados consecutivos exactos (causados por el solape entre franjas).
    deduped: list[Linea] = []
    for ln in lineas:
        if deduped and deduped[-1].texto == ln.texto and deduped[-1].emisor == ln.emisor:
            continue
        deduped.append(ln)

    log.info("OCR %s: %d líneas (de %d brutas)", image_path.name, len(deduped), len(lineas))
    return FuenteTexto(tipo="ocr", lineas=deduped)

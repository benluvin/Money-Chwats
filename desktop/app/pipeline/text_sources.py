"""Fuentes de texto: la abstracción central que hace el pipeline escalable.

Una *fuente* es texto de la conversación proveniente de algún origen:
  - "ocr": leído de la imagen con PaddleOCR/RapidOCR (Fase 1).
  - "dom": leído del DOM de WhatsApp Web por la extensión (Fase 2).

El estructurador y el cross-check trabajan sobre `FuenteTexto`, sin importar el
origen. Hoy hay una sola fuente (ocr); mañana habrá dos y se podrán cruzar sin
cambiar el resto del pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Emisor = Literal["cliente", "negocio", "desconocido"]
TipoFuente = Literal["ocr", "dom"]


@dataclass
class Linea:
    """Una línea/burbuja de la conversación."""

    texto: str
    emisor: Emisor = "desconocido"
    # Confianza del origen en esta línea (OCR: confianza del reconocimiento; DOM: 1.0).
    confianza: float = 1.0


@dataclass
class FuenteTexto:
    """Conjunto de líneas de un mismo origen."""

    tipo: TipoFuente
    lineas: list[Linea] = field(default_factory=list)

    @property
    def texto_completo(self) -> str:
        """Render plano con etiqueta de emisor, para alimentar al estructurador."""
        partes = []
        for ln in self.lineas:
            if not ln.texto.strip():
                continue
            etiqueta = {"cliente": "CLIENTE", "negocio": "NEGOCIO", "desconocido": "?"}[ln.emisor]
            partes.append(f"[{etiqueta}] {ln.texto.strip()}")
        return "\n".join(partes)

    @property
    def nombres_emisores(self) -> list[str]:
        """Nombres detectados como emisores (para blindaje), si los hubiera."""
        return []

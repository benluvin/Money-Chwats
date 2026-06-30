"""Interfaz común de los estructuradores."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from ..models.extraction import ExtractionResult
from ..pipeline.text_sources import FuenteTexto


class StructurerError(RuntimeError):
    pass


@dataclass
class StructureContext:
    """Pistas que el estructurador puede aprovechar."""

    nombre_contacto: str | None = None
    fecha_captura: date | None = None
    moneda_default: str = "COP"
    catalogo_texto: str = "(sin catálogo configurado)"


@runtime_checkable
class Structurer(Protocol):
    """Cualquier backend que convierta texto en datos estructurados."""

    nombre: str

    async def structure(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        ...

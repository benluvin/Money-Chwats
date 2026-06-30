"""Estructurador en cascada: prueba varios backends en orden hasta que uno responda.

Orden típico: Nemotron (primario) → modelo backup gratis → (y el pipeline, si todo
falla, cae a reglas offline). Así una caída del modelo primario no detiene nada.
"""
from __future__ import annotations

import logging

from ..models.extraction import ExtractionResult
from ..pipeline.text_sources import FuenteTexto
from .base import StructureContext, Structurer, StructurerError

log = logging.getLogger("money_chwats.cascade")


class CascadeStructurer:
    nombre = "nemotron"  # mantiene compatibilidad con la selección de modelo

    def __init__(self, eslabones: list[Structurer]) -> None:
        self.eslabones = eslabones
        self.ultimo_backend = ""  # cuál respondió (para diagnóstico)

    async def structure(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        ultimo_error: Exception | None = None
        for s in self.eslabones:
            try:
                res = await s.structure(fuente, context=context)
                self.ultimo_backend = getattr(s, "modelo", s.nombre)
                return res
            except StructurerError as exc:
                ultimo_error = exc
                log.warning("cascada: '%s' falló (%s) → probando siguiente", getattr(s, "modelo", s.nombre), exc)
        # Todos los eslabones de nube fallaron.
        raise StructurerError(f"Todos los modelos de nube fallaron. Último: {ultimo_error}")

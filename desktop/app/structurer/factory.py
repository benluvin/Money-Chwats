"""Selecciona el estructurador según la configuración, con fallback a reglas."""
from __future__ import annotations

import logging

from ..config import AppConfig
from .base import Structurer
from .rules import RulesStructurer

log = logging.getLogger("money_chwats.structurer")


def build_structurer(cfg: AppConfig) -> Structurer:
    """Devuelve el estructurador configurado.

    - 'nemotron' requiere cloud.enabled y API key; si falta, cae a reglas.
    - 'local' usa Ollama (modelo de texto diminuto).
    - 'rules' (default) es offline y siempre disponible.
    """
    backend = cfg.extraction.backend.lower()

    if backend == "nemotron":
        if not cfg.cloud.enabled:
            log.warning("backend 'nemotron' pero cloud.enabled=false → usando reglas")
            return RulesStructurer()
        if not cfg.cloud.resolved_api_key:
            log.warning("backend 'nemotron' sin API key → usando reglas")
            return RulesStructurer()
        from .nemotron import NemotronStructurer

        # Cascada: modelo primario → modelo backup (gratis). Si ambos caen, el
        # pipeline cae a reglas offline (lo maneja import_pipeline / process).
        eslabones = [NemotronStructurer(cfg.cloud, cfg.privacy, modelo=cfg.cloud.model)]
        if cfg.cloud.backup_model and cfg.cloud.backup_model != cfg.cloud.model:
            eslabones.append(NemotronStructurer(cfg.cloud, cfg.privacy, modelo=cfg.cloud.backup_model))
        if len(eslabones) == 1:
            return eslabones[0]
        from .cascade import CascadeStructurer

        return CascadeStructurer(eslabones)

    if backend == "local":
        from .local_tiny import LocalTinyStructurer

        return LocalTinyStructurer(cfg.llm)

    return RulesStructurer()

"""Estructuradores: convierten texto de conversación en ExtractionResult.

Backends disponibles (se eligen por config):
  - "rules":    100% local, sin IA, sin red. Plan B / fallback garantizado.
  - "nemotron": nube (OpenRouter) con blindaje. Principal. (Fase 1, paso nube.)
  - "local":    modelo de texto diminuto vía Ollama. Opcional para PCs holgados.
"""
from __future__ import annotations

from .base import StructureContext, Structurer, StructurerError

__all__ = ["StructureContext", "Structurer", "StructurerError"]

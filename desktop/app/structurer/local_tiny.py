"""Estructurador LOCAL con un modelo de texto diminuto vía Ollama.

Opcional: solo para PCs con RAM holgada que prefieran no usar la nube. Un modelo
de texto chico (p. ej. qwen2.5:1.5b, ~1 GB) NO tiene el pico de memoria de los
modelos de visión, así que es viable donde aquellos no lo eran. Aun así, en 4 GB
lo recomendado es 'rules' o 'nemotron'.
"""
from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from ..config import LlmConfig
from ..models.extraction import ExtractionResult
from ..pipeline.prompts import SYSTEM_PROMPT_TEXT, USER_INSTRUCTION_TEXT
from ..pipeline.text_sources import FuenteTexto
from .base import StructureContext, StructurerError

log = logging.getLogger("money_chwats.local_tiny")


class LocalTinyStructurer:
    nombre = "local"

    def __init__(self, llm: LlmConfig) -> None:
        self.llm = llm

    async def structure(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        user_msg = USER_INSTRUCTION_TEXT.format(conversacion=fuente.texto_completo)
        payload = {
            "model": self.llm.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_TEXT},
                {"role": "user", "content": user_msg},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
        try:
            async with httpx.AsyncClient(timeout=self.llm.timeout_seconds) as client:
                r = await client.post(f"{self.llm.base_url.rstrip('/')}/api/chat", json=payload)
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            raise StructurerError(f"Ollama no respondió: {exc}") from exc
        if r.status_code != 200:
            raise StructurerError(f"Ollama respondió {r.status_code}: {r.text[:200]}")
        content = r.json().get("message", {}).get("content", "")
        if not content:
            raise StructurerError("Respuesta del modelo local vacía")
        try:
            data = json.loads(content)
            return ExtractionResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise StructurerError(f"Modelo local no produjo JSON válido: {exc}") from exc

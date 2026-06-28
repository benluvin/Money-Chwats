"""Estructurador en la NUBE: Nemotron vía OpenRouter, con blindaje integrado.

Flujo:
  1. Arma el texto de la conversación desde la FuenteTexto.
  2. Lo SEUDONIMIZA localmente (teléfonos, nombres, direcciones, emails → tokens).
  3. Envía solo el texto blindado a OpenRouter.
  4. Recibe el JSON (con los mismos tokens) y RESTAURA los valores reales localmente.
  5. Valida contra ExtractionResult.

OpenRouter nunca ve datos personales reales: solo "[[NOMBRE_1]] pidió 3 cajas".
"""
from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import ValidationError

from ..config import CloudConfig, PrivacyConfig
from ..models.extraction import ExtractionResult
from ..pipeline.anonymizer import Anonymizer, AnonymizerConfig
from ..pipeline.prompts import SYSTEM_PROMPT_TEXT, USER_INSTRUCTION_TEXT
from ..pipeline.text_sources import FuenteTexto
from .base import StructureContext, StructurerError
from .merge import merge_results, necesita_troceo, trocear

log = logging.getLogger("money_chwats.nemotron")

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


class NemotronStructurer:
    """Backend de nube con seudonimización."""

    nombre = "nemotron"

    def __init__(self, cloud: CloudConfig, privacy: PrivacyConfig) -> None:
        self.cloud = cloud
        self.anon = Anonymizer(
            AnonymizerConfig(
                redact_phones=privacy.redact_phones,
                redact_emails=privacy.redact_emails,
                redact_addresses=privacy.redact_addresses,
                redact_names=privacy.redact_names,
            )
        )

    async def structure(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        # Chats largos: trocear y unir (map-reduce).
        if necesita_troceo(fuente):
            trozos = trocear(fuente)
            log.info("Nemotron: chat largo → %d trozos", len(trozos))
            results = [await self._structure_one(t, context=context) for t in trozos]
            return merge_results(results)
        return await self._structure_one(fuente, context=context)

    async def _structure_one(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        api_key = self.cloud.resolved_api_key
        if not api_key:
            raise StructurerError(
                "No hay API key de OpenRouter. Configúrala en config.toml [cloud] "
                "api_key o en la variable de entorno OPENROUTER_API_KEY."
            )

        # 1-2. Texto + blindaje local.
        known = [context.nombre_contacto] if context.nombre_contacto else []
        blindado = self.anon.anonymize(fuente.texto_completo, known_names=known)
        log.info("Nemotron: enviando texto blindado (%d datos ocultos)", blindado.replacements)

        user_msg = USER_INSTRUCTION_TEXT.format(conversacion=blindado.text)
        payload = {
            "model": self.cloud.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_TEXT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "Money Chwats",
        }

        # 3. Llamada a la nube.
        try:
            async with httpx.AsyncClient(timeout=self.cloud.timeout_seconds) as client:
                r = await client.post(
                    f"{self.cloud.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            raise StructurerError(f"OpenRouter no respondió: {exc}") from exc

        if r.status_code != 200:
            raise StructurerError(f"OpenRouter respondió {r.status_code}: {r.text[:300]}")

        content = (
            r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        if not content:
            raise StructurerError("Respuesta de Nemotron vacía")

        data = _parse_json(content)
        if data is None:
            raise StructurerError(f"Nemotron no devolvió JSON válido. Inicio: {content[:200]!r}")

        # 4. Restaurar valores reales localmente.
        data = Anonymizer.restore(data, blindado.mapping)

        # 5. Validar.
        try:
            return ExtractionResult.model_validate(data)
        except ValidationError as exc:
            raise StructurerError(f"JSON de Nemotron no pasó validación: {exc.errors()[:3]}") from exc


def _parse_json(content: str) -> dict | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE_RE.search(content)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    # Último intento: primer { … último }.
    start, end = content.find("{"), content.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None

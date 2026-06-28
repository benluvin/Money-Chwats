"""Cliente HTTP de Ollama. Procesa una imagen de chat y devuelve un ExtractionResult."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx
from pydantic import ValidationError

from ..config import LlmConfig
from ..models.extraction import ExtractionResult
from .prompts import SYSTEM_PROMPT, USER_INSTRUCTION

log = logging.getLogger("money_chwats.llm")


class LlmError(RuntimeError):
    pass


class OllamaNotRunning(LlmError):
    pass


class ModelNotInstalled(LlmError):
    pass


def _b64_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


async def check_runtime(cfg: LlmConfig) -> dict:
    """Verifica que Ollama esté corriendo y el modelo configurado disponible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{cfg.base_url.rstrip('/')}/api/tags")
    except (httpx.ConnectError, httpx.ReadTimeout) as exc:
        raise OllamaNotRunning(
            f"No se pudo conectar con Ollama en {cfg.base_url}. "
            "¿Está instalado y corriendo (`ollama serve`)?"
        ) from exc
    if r.status_code != 200:
        raise LlmError(f"Ollama respondió {r.status_code}: {r.text[:200]}")
    models = [m.get("name", "") for m in r.json().get("models", [])]
    target = cfg.model
    has = any(m == target or m.startswith(target.split(":", 1)[0] + ":") for m in models)
    if not has:
        raise ModelNotInstalled(
            f"Modelo '{target}' no instalado en Ollama. "
            f"Ejecuta: `ollama pull {target}` y vuelve a intentar."
        )
    return {"available_models": models, "selected": target}


async def extract_from_image(cfg: LlmConfig, image_path: Path) -> ExtractionResult:
    """Envía la imagen al LLM, valida la respuesta y devuelve un ExtractionResult."""
    if not image_path.exists():
        raise LlmError(f"Imagen no existe: {image_path}")

    image_b64 = _b64_image(image_path)
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_INSTRUCTION, "images": [image_b64]},
        ],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }

    log.info("LLM call: model=%s img=%s (%d KB)", cfg.model, image_path.name, image_path.stat().st_size // 1024)
    try:
        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            r = await client.post(f"{cfg.base_url.rstrip('/')}/api/chat", json=payload)
    except (httpx.ConnectError, httpx.ReadTimeout) as exc:
        raise OllamaNotRunning(f"Ollama no respondió a tiempo: {exc}") from exc

    if r.status_code != 200:
        raise LlmError(f"Ollama respondió {r.status_code}: {r.text[:300]}")

    body = r.json()
    content = body.get("message", {}).get("content", "")
    if not content:
        raise LlmError("Respuesta del LLM vacía")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LlmError(f"El LLM no devolvió JSON válido. Inicio: {content[:200]!r}") from exc

    try:
        return ExtractionResult.model_validate(data)
    except ValidationError as exc:
        log.warning("Validación falló — intentando reparar. Errores: %s", exc.errors()[:3])
        # Reintento: pedir reparación al modelo, una sola vez.
        repair = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_INSTRUCTION, "images": [image_b64]},
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "Tu JSON no pasó la validación con estos errores: "
                        f"{exc.errors()[:5]}. Devuelve únicamente el JSON corregido."
                    ),
                },
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            r2 = await client.post(f"{cfg.base_url.rstrip('/')}/api/chat", json=repair)
        content2 = r2.json().get("message", {}).get("content", "")
        try:
            data2 = json.loads(content2)
            return ExtractionResult.model_validate(data2)
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise LlmError(f"El LLM no produjo JSON válido tras reintento: {exc2}") from exc2

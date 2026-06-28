"""Carga de configuración desde config.toml con defaults sensatos."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from .utils.paths import expand


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5000


class StorageConfig(BaseModel):
    root: str = "~/CapturasWhatsApp"

    @property
    def root_path(self) -> Path:
        return expand(self.root)


class CsvConfig(BaseModel):
    separator: str = ";"
    encoding: str = "utf-8-sig"
    decimal: str = "."


class LocaleConfig(BaseModel):
    default_currency: str = "COP"
    default_language: str = "es"
    default_country_code: str = "+57"


class LlmConfig(BaseModel):
    """Modelo local vía Ollama. Opcional: solo para el backend 'local' (PCs holgados)."""

    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:1.5b"
    timeout_seconds: int = 180
    review_threshold: float = 0.6


class OcrConfig(BaseModel):
    """OCR local liviano (imagen → texto). Corre hasta en PCs de 4 GB."""

    enabled: bool = True
    engine: str = "rapidocr"  # único soportado hoy; detrás de interfaz


class CloudConfig(BaseModel):
    """Nube opt-in para estructurar texto (Nemotron vía OpenRouter).

    Desactivada por defecto. El texto se envía SEUDONIMIZADO (ver PrivacyConfig).
    La API key puede ir aquí o en la variable de entorno OPENROUTER_API_KEY.
    """

    enabled: bool = False
    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    api_key: str = ""
    timeout_seconds: int = 120

    @property
    def resolved_api_key(self) -> str:
        import os

        return self.api_key or os.environ.get("OPENROUTER_API_KEY", "")


class PrivacyConfig(BaseModel):
    """Qué datos sensibles blindar antes de enviar texto a la nube."""

    redact_phones: bool = True
    redact_emails: bool = True
    redact_addresses: bool = True
    redact_names: bool = True


class ExtractionConfig(BaseModel):
    """Qué backend estructura el texto, y umbral de revisión.

    backend: 'rules' (offline, sin red) | 'nemotron' (nube) | 'local' (Ollama).
    """

    backend: str = "rules"
    review_threshold: float = 0.6


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    csv: CsvConfig = Field(default_factory=CsvConfig)
    locale: LocaleConfig = Field(default_factory=LocaleConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)


def _find_config_file() -> Path | None:
    """Busca config.toml en orden: env MONEY_CHWATS_CONFIG, ./config.toml, ../config.toml."""
    import os

    env = os.environ.get("MONEY_CHWATS_CONFIG")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    here = Path.cwd()
    for candidate in (here / "config.toml", here.parent / "config.toml"):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    path = _find_config_file()
    if path is None:
        return AppConfig()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AppConfig.model_validate(data)


def reset_config_cache() -> None:
    """Útil para tests que cambian env vars."""
    get_config.cache_clear()

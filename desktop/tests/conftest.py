"""Fixtures comunes."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import reset_config_cache


@pytest.fixture
def tmp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Apunta el storage a una carpeta temporal y limpia el cache de config."""
    config_content = f"""
[server]
host = "127.0.0.1"
port = 5000

[storage]
root = "{tmp_path.as_posix()}"

[csv]
separator = ";"
encoding = "utf-8-sig"
decimal = "."

[locale]
default_currency = "COP"
default_language = "es"
default_country_code = "+57"
"""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(config_content)
    monkeypatch.setenv("MONEY_CHWATS_CONFIG", str(cfg_path))
    reset_config_cache()
    yield tmp_path
    reset_config_cache()
    if "MONEY_CHWATS_CONFIG" in os.environ:
        del os.environ["MONEY_CHWATS_CONFIG"]

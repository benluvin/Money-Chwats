"""Resolución y creación de rutas en disco."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def expand(path: str | Path) -> Path:
    """Expande ~ y variables de entorno; devuelve un Path absoluto."""
    return Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir_for(root: Path, when: date) -> Path:
    """`<root>/raw/YYYY/MM/DD/`, creado si no existe."""
    return ensure_dir(root / "raw" / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}")


def data_dir(root: Path) -> Path:
    return ensure_dir(root / "data")


def dom_dir(root: Path) -> Path:
    return ensure_dir(root / "data" / "dom")


def ocr_dir(root: Path) -> Path:
    return ensure_dir(root / "data" / "ocr")


def exports_dir(root: Path) -> Path:
    return ensure_dir(root / "data" / "exports")


def logs_dir(root: Path) -> Path:
    return ensure_dir(root / "logs")

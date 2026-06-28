"""Endpoint para abrir una imagen guardada o su carpeta en el visor del sistema."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_config

router = APIRouter()


class OpenRequest(BaseModel):
    """Path absoluto a abrir. Debe estar dentro de `storage.root` por seguridad."""

    path: str
    reveal: bool = False  # True → abre el Finder/Explorer apuntando al archivo


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _open_native(target: Path, reveal: bool) -> None:
    system = platform.system()
    if system == "Darwin":
        if reveal:
            subprocess.run(["open", "-R", str(target)], check=False)
        else:
            subprocess.run(["open", str(target)], check=False)
    elif system == "Windows":
        if reveal:
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        else:
            subprocess.run(["start", "", str(target)], shell=True, check=False)
    else:  # Linux
        cmd = "xdg-open"
        subprocess.run([cmd, str(target.parent if reveal else target)], check=False)


@router.post("/open", status_code=status.HTTP_204_NO_CONTENT)
def open_file(body: OpenRequest) -> None:
    cfg = get_config()
    target = Path(body.path)
    root = cfg.storage.root_path

    if not _is_inside(target, root):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Solo se pueden abrir archivos dentro de la carpeta de capturas.",
        )
    if not target.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo no existe.")

    _open_native(target, body.reveal)

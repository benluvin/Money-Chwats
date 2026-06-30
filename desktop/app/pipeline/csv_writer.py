"""CSV append atómico con filelock — sobrevive a Excel abierto.
Maneja `capturas.csv` (append simple), `clientes.csv` (upsert por id) y `pedidos.csv` (append)."""
from __future__ import annotations

import csv
import io
import os
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

from filelock import FileLock, Timeout

from ..models.capture import CSV_COLUMNS as CAPTURAS_COLUMNS
from ..models.capture import CaptureRow

LOCK_TIMEOUT_SECONDS = 5
RENAME_RETRY_SECONDS = 30


class CsvLockedError(RuntimeError):
    pass


def append_capture_row(
    row: CaptureRow,
    *,
    csv_path: Path,
    separator: str = ";",
    encoding: str = "utf-8-sig",
) -> None:
    _with_lock(
        csv_path,
        lambda: _append_rows(csv_path, [row.to_csv_dict()], CAPTURAS_COLUMNS, separator, encoding),
    )


def upsert_cliente_row(
    row_dict: dict[str, str],
    *,
    columns: list[str],
    id_column: str,
    csv_path: Path,
    separator: str = ";",
    encoding: str = "utf-8-sig",
) -> bool:
    """Inserta o reemplaza por `id_column`. Devuelve True si actualizó."""
    return _with_lock(
        csv_path,
        lambda: _do_upsert(row_dict, columns, id_column, csv_path, separator, encoding),
    )


def append_pedido_rows(
    rows: list[dict[str, str]],
    *,
    columns: list[str],
    csv_path: Path,
    separator: str = ";",
    encoding: str = "utf-8-sig",
) -> None:
    if not rows:
        return
    _with_lock(
        csv_path,
        lambda: _append_rows(csv_path, rows, columns, separator, encoding),
    )


# --- internals ------------------------------------------------------------


def _with_lock(csv_path: Path, fn):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(csv_path) + ".lock")
    try:
        with lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            return fn()
    except Timeout as exc:
        raise CsvLockedError(
            f"No se pudo obtener lock para {csv_path} en {LOCK_TIMEOUT_SECONDS}s"
        ) from exc


def _read_existing(csv_path: Path, columns: list[str], separator: str, encoding: str) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=separator)
        return [{c: r.get(c, "") for c in columns} for r in reader]


def _write_all(csv_path: Path, rows: Iterable[dict[str, str]], columns: list[str], separator: str, encoding: str) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=columns, delimiter=separator, lineterminator="\n", extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write(csv_path, buf.getvalue().encode(encoding))


def _append_rows(
    csv_path: Path, new_rows: list[dict[str, str]], columns: list[str], separator: str, encoding: str,
) -> None:
    existing = _read_existing(csv_path, columns, separator, encoding)
    _write_all(csv_path, existing + new_rows, columns, separator, encoding)


# Campos que el usuario puede editar a mano y que, si lo hizo, deben PREVALECER
# sobre lo que detecte la IA al reprocesar el chat.
_CAMPOS_PROTEGIDOS_MANUAL = (
    "nombre", "nickname", "telefono_completo", "telefono_redactado",
    "telefono_pendiente", "estado_relacion", "direccion_principal",
    "especificaciones_importantes", "etiquetas", "resumen",
)


def _es_verdadero(v: str | None) -> bool:
    return str(v).strip().lower() in ("true", "1", "sí", "si")


def _do_upsert(
    new_row: dict[str, str], columns: list[str], id_column: str, csv_path: Path,
    separator: str, encoding: str,
) -> bool:
    existing = _read_existing(csv_path, columns, separator, encoding)
    found = False
    for i, r in enumerate(existing):
        if r.get(id_column) == new_row.get(id_column):
            fusionada = dict(new_row)
            # fecha_creacion: conservar la original (nunca se reescribe).
            if r.get("fecha_creacion"):
                fusionada["fecha_creacion"] = r["fecha_creacion"]
            # Si el cliente fue editado a mano, sus campos editados prevalecen.
            if "editado_manualmente" in columns and _es_verdadero(r.get("editado_manualmente")):
                for col in _CAMPOS_PROTEGIDOS_MANUAL:
                    if col in columns:
                        fusionada[col] = r.get(col, "")
                fusionada["editado_manualmente"] = "true"
            existing[i] = fusionada
            found = True
            break
    if not found:
        existing.append(new_row)
    _write_all(csv_path, existing, columns, separator, encoding)
    return found


def _atomic_write(target: Path, payload: bytes) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(payload)
        deadline = time.time() + RENAME_RETRY_SECONDS
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                os.replace(tmp_name, target)
                return
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.5)
        pending = target.with_suffix(target.suffix + ".pending")
        os.replace(tmp_name, pending)
        raise CsvLockedError(
            f"No se pudo escribir {target} (¿abierto en Excel?). Se dejó pendiente en {pending}."
        ) from last_exc
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

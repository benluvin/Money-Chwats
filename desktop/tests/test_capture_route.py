"""Tests del POST /capture, incluyendo stitching multi-parte."""
from __future__ import annotations

import base64
import csv
import struct
import zlib
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


def _png_solid(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (width, height), rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_health_endpoint(tmp_root: Path) -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_capture_single_part(tmp_root: Path) -> None:
    client = TestClient(create_app())
    r = client.post(
        "/capture",
        json={
            "captured_at": datetime(2026, 6, 26, 14, 30).isoformat(),
            "tab_url": "https://example.com",
            "tab_title": "Demo",
            "screenshot_parts_b64": [_b64(_png_solid(100, 200, (255, 0, 0)))],
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["parts_received"] == 1

    png_path = tmp_root / body["png_path"]
    assert png_path.exists()
    img = Image.open(png_path)
    assert img.size == (100, 200)


def test_capture_multiple_parts_stitched(tmp_root: Path) -> None:
    client = TestClient(create_app())
    parts = [
        _png_solid(100, 80, (255, 0, 0)),     # rojo
        _png_solid(100, 80, (0, 255, 0)),     # verde
        _png_solid(100, 80, (0, 0, 255)),     # azul
    ]
    r = client.post(
        "/capture",
        json={
            "captured_at": "2026-06-26T14:30:00",
            "screenshot_parts_b64": [_b64(p) for p in parts],
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["parts_received"] == 3

    img = Image.open(tmp_root / body["png_path"])
    assert img.size == (100, 240)  # 80 * 3
    # Verifica los colores en el centro de cada banda
    px = img.load()
    assert px[50, 40] == (255, 0, 0)
    assert px[50, 80 + 40] == (0, 255, 0)
    assert px[50, 160 + 40] == (0, 0, 255)


def test_csv_row_per_capture(tmp_root: Path) -> None:
    client = TestClient(create_app())
    for _ in range(3):
        client.post(
            "/capture",
            json={
                "captured_at": "2026-06-26T14:30:00",
                "screenshot_parts_b64": [_b64(_png_solid(50, 50, (10, 20, 30)))],
            },
        )
    with (tmp_root / "data" / "capturas.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    assert len(rows) == 3
    assert len({r["capture_id"] for r in rows}) == 3


def test_capture_rejects_invalid_png(tmp_root: Path) -> None:
    client = TestClient(create_app())
    r = client.post(
        "/capture",
        json={
            "captured_at": "2026-06-26T14:30:00",
            "screenshot_parts_b64": [_b64(b"NOTAPNG")],
        },
    )
    assert r.status_code == 400


def test_csv_uses_semicolon_and_bom(tmp_root: Path) -> None:
    client = TestClient(create_app())
    client.post(
        "/capture",
        json={
            "captured_at": "2026-06-26T14:30:00",
            "screenshot_parts_b64": [_b64(_png_solid(10, 10, (1, 2, 3)))],
        },
    )
    raw = (tmp_root / "data" / "capturas.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert ";" in raw[3:].decode("utf-8").splitlines()[0]

"""Agenda de contactos (referencia nombre↔teléfono).

NO son clientes: la agenda solo sirve para CRUZAR. Alguien se vuelve cliente
cuando su nombre o número coincide con una conversación; ahí usamos la agenda
para completar el teléfono correcto (y confirmar el nombre).

Fuentes soportadas:
  - vCard (.vcf): exportado del iPhone / Contactos de Mac / iCloud.
  - Google Contacts (.csv): exportado de contacts.google.com.

Cero WhatsApp: la agenda es la libreta del propio teléfono, así que no hay
automatización ni riesgo de ban.
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

from ..config import AppConfig
from ..utils.paths import data_dir
from ..utils.telefono import normalizar_telefono

CONTACTOS_COLUMNS = ["nombre", "telefono", "nombre_norm", "telefono_norm"]


def _path(cfg: AppConfig) -> Path:
    return data_dir(cfg.storage.root_path) / "contactos.csv"


def normalizar_nombre(s: str | None) -> str:
    """Minúsculas, sin tildes, espacios colapsados — para comparar nombres."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.strip().lower())


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_vcard(texto: str) -> list[tuple[str, str]]:
    """Devuelve [(nombre, telefono_crudo)] desde un .vcf (puede traer varios)."""
    out: list[tuple[str, str]] = []
    nombre = ""
    tels: list[str] = []
    for linea in texto.splitlines():
        l = linea.strip()
        up = l.upper()
        if up == "BEGIN:VCARD":
            nombre, tels = "", []
        elif up.startswith("FN:"):
            nombre = l[3:].strip()
        elif up.startswith("FN;"):  # FN con parámetros
            nombre = l.split(":", 1)[1].strip() if ":" in l else ""
        elif up.startswith("TEL"):
            if ":" in l:
                tels.append(l.split(":", 1)[1].strip())
        elif up == "END:VCARD":
            for t in (tels or [""]):
                if nombre or t:
                    out.append((nombre, t))
    return out


def parse_google_csv(texto: str) -> list[tuple[str, str]]:
    """Devuelve [(nombre, telefono)] desde un export CSV de Google Contacts."""
    out: list[tuple[str, str]] = []
    reader = csv.DictReader(texto.splitlines())
    for row in reader:
        nombre = (row.get("Name") or "").strip()
        if not nombre:
            partes = [(row.get("First Name") or "").strip(), (row.get("Middle Name") or "").strip(),
                      (row.get("Last Name") or "").strip()]
            nombre = " ".join(p for p in partes if p)
        # Google numera los teléfonos: "Phone 1 - Value", "Phone 2 - Value", …
        tel = ""
        for k, v in row.items():
            if k and k.startswith("Phone") and k.endswith("Value") and v and v.strip():
                tel = v.split(":::")[0].strip()  # a veces vienen varios con ":::"
                break
        if nombre or tel:
            out.append((nombre, tel))
    return out


def _parse(path: Path) -> list[tuple[str, str]]:
    texto = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".vcf":
        return parse_vcard(texto)
    return parse_google_csv(texto)


# ── Almacenamiento ────────────────────────────────────────────────────────────

def listar(cfg: AppConfig) -> list[dict]:
    p = _path(cfg)
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f, delimiter=cfg.csv.separator)]


def importar_agenda(cfg: AppConfig, path: Path) -> dict:
    """Lee un .vcf o .csv, lo fusiona con la agenda existente y la reescribe.

    Dedup por teléfono normalizado (o por nombre si no hay teléfono).
    """
    crudos = _parse(path)
    existentes = {(_clave(r["nombre_norm"], r["telefono_norm"])): r for r in listar(cfg)}

    nuevos = 0
    for nombre, tel in crudos:
        nn = normalizar_nombre(nombre)
        tn = normalizar_telefono(tel) or ""
        if not nn and not tn:
            continue
        clave = _clave(nn, tn)
        fila = {
            "nombre": nombre.strip(),
            "telefono": tn or re.sub(r"[\s\-().]", "", tel or ""),
            "nombre_norm": nn,
            "telefono_norm": tn,
        }
        if clave not in existentes:
            nuevos += 1
        existentes[clave] = fila

    _escribir(cfg, list(existentes.values()))
    return {"importados": len(crudos), "nuevos": nuevos, "total": len(existentes)}


def _clave(nombre_norm: str, telefono_norm: str) -> str:
    return telefono_norm or f"n:{nombre_norm}"


def _escribir(cfg: AppConfig, filas: list[dict]) -> None:
    p = _path(cfg)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding=cfg.csv.encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=CONTACTOS_COLUMNS, delimiter=cfg.csv.separator)
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in CONTACTOS_COLUMNS})
    os.replace(tmp, p)


# ── Cruce (lo que usa el pipeline) ────────────────────────────────────────────

def buscar(cfg: AppConfig, *, nombre: str | None = None, telefono: str | None = None) -> dict | None:
    """Busca un contacto por teléfono (prioritario) o por nombre. None si no hay."""
    filas = listar(cfg)
    if not filas:
        return None
    tn = normalizar_telefono(telefono) if telefono else None
    if tn:
        for r in filas:
            if r.get("telefono_norm") == tn:
                return r
    nn = normalizar_nombre(nombre) if nombre else ""
    if nn:
        for r in filas:
            if r.get("nombre_norm") == nn:
                return r
    return None

"""Genera un .md de una conversación usando SOLO la tecnología local de la app
(OCR RapidOCR + estructurador por reglas). Sin LLM, sin nube, sin razonamiento
externo: el contenido sale tal cual de los componentes de Money Chwats.

Uso:
    python scripts/exportar_conversacion_md.py <ruta_imagen.png> <salida.md>
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

from app.pipeline.ocr_client import extract_from_image
from app.structurer.base import StructureContext
from app.structurer.rules import RulesStructurer


def main() -> None:
    img = Path(sys.argv[1])
    out = Path(sys.argv[2])

    # 1. OCR local (imagen → texto)
    fuente = extract_from_image(img)

    # 2. Estructurador por reglas (offline)
    ctx = StructureContext(fecha_captura=date.today(), moneda_default="COP")
    res = asyncio.run(RulesStructurer().structure(fuente, context=ctx))

    c = res.cliente
    lineas_md = []
    lineas_md.append(f"# Conversación extraída — {img.stem}")
    lineas_md.append("")
    lineas_md.append("> Generado 100% con la tecnología local de Money Chwats: "
                     "captura (extensión) + OCR RapidOCR + estructurador por reglas. "
                     "**Sin LLM, sin nube, sin análisis externo.**")
    lineas_md.append("")
    lineas_md.append("## Datos estructurados (backend: reglas)")
    lineas_md.append("")
    lineas_md.append("| Campo | Valor |")
    lineas_md.append("| --- | --- |")
    lineas_md.append(f"| Mensajes visibles | {c.total_mensajes_visibles} |")
    lineas_md.append(f"| Mensajes del cliente | {c.mensajes_del_cliente} |")
    lineas_md.append(f"| Mensajes del negocio | {c.mensajes_del_negocio} |")
    lineas_md.append(f"| Sentimiento (por palabras clave) | {c.sentimiento_general} |")
    lineas_md.append(f"| Teléfono detectado | {c.telefono or '—'} |")
    lineas_md.append(f"| Pedidos detectados (por monto) | {len(res.pedidos)} |")
    lineas_md.append(f"| Confianza | {c.confianza_extraccion} |")
    lineas_md.append(f"| Resumen (reglas) | {c.resumen} |")
    lineas_md.append("")

    if res.pedidos:
        lineas_md.append("### Pedidos")
        lineas_md.append("")
        lineas_md.append("| Producto/servicio | Cantidad | Unidad | Monto | Origen |")
        lineas_md.append("| --- | --- | --- | --- | --- |")
        for p in res.pedidos:
            lineas_md.append(
                f"| {p.producto_servicio} | {p.cantidad or ''} | {p.unidad or ''} "
                f"| {p.monto_total or ''} | {p.mensaje_origen[:60]} |"
            )
        lineas_md.append("")

    lineas_md.append("## Conversación reconstruida (OCR)")
    lineas_md.append("")
    lineas_md.append("Cada línea trae el emisor inferido por su posición "
                     "(derecha = NEGOCIO, izquierda = CLIENTE).")
    lineas_md.append("")
    for ln in fuente.lineas:
        etq = {"cliente": "**CLIENTE**", "negocio": "**NEGOCIO**", "desconocido": "_·_"}[ln.emisor]
        lineas_md.append(f"- {etq}: {ln.texto}")
    lineas_md.append("")

    out.write_text("\n".join(lineas_md), encoding="utf-8")
    print(f"OK → {out}  ({len(fuente.lineas)} líneas, {len(res.pedidos)} pedidos)")


if __name__ == "__main__":
    main()

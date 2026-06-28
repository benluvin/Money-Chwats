"""Estructurador por REGLAS — 100% local, sin IA, sin red.

Es el Plan B: si no hay internet, o el usuario no activó la nube, esto garantiza
que la app siga extrayendo lo básico (teléfonos, montos en COP, cantidades,
sentimiento aproximado). No es tan bueno como un LLM, por eso reporta confianza
baja, pero NUNCA deja a la app sin funcionar.
"""
from __future__ import annotations

import re

from ..models.extraction import (
    ExtractedCliente,
    ExtractedPedido,
    ExtractionResult,
)
from ..pipeline.text_sources import FuenteTexto
from .base import StructureContext

# Confianza fija y modesta: son reglas, no comprensión real.
_CONFIANZA_REGLAS = 0.35

_TEL_RE = re.compile(r"(?<![\w])\+?(?:\(?\d{1,4}\)?[\s.\-]?)(?:\d[\s.\-]?){6,12}\d(?![\w])")

# Montos: "$1.200.000", "50.000", "$50,5", "20 mil", "2 millones", "50k".
_MONTO_RE = re.compile(
    r"""
    (?:
        \$\s?\d{1,3}(?:\.\d{3})+(?:,\d+)?      # $1.200.000  / $50.000,5
      | \$\s?\d+(?:,\d+)?                       # $50000 / $50,5
      | \b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b        # 1.200.000 sin $
      | \b\d+\s?(?:mil|millones?|millon|k)\b    # 20 mil / 2 millones / 50k
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CANTIDAD_RE = re.compile(
    r"\b(\d+)\s*"
    r"(unidades?|cajas?|docenas?|kilos?|kg|libras?|lb|litros?|lt|"
    r"paquetes?|bolsas?|metros?|pares?|gramos?|und|uds?)\b",
    re.IGNORECASE,
)

_POSITIVAS = {"gracias", "excelente", "perfecto", "genial", "buenísimo", "buenisimo",
              "encanta", "feliz", "listo", "súper", "super", "bueno", "amable"}
_NEGATIVAS = {"malo", "pésimo", "pesimo", "queja", "reclamo", "molesto", "tarde",
              "demora", "error", "mal", "horrible", "nunca", "cancelar", "devolver"}


def _parse_monto(texto: str) -> float | None:
    t = texto.strip().lower().replace("$", "").strip()
    mult = 1.0
    if t.endswith("k"):
        mult, t = 1000.0, t[:-1].strip()
    elif "millon" in t or "millones" in t:
        mult = 1_000_000.0
        t = re.sub(r"millones?|millon", "", t).strip()
    elif t.endswith("mil"):
        mult, t = 1000.0, t[:-3].strip()
    # En Colombia: '.' separa miles, ',' separa decimales.
    t = t.replace(".", "").replace(",", ".")
    if not t:
        return None
    try:
        return float(t) * mult
    except ValueError:
        return None


def _sentimiento(texto: str) -> str:
    low = texto.lower()
    pos = sum(1 for w in _POSITIVAS if w in low)
    neg = sum(1 for w in _NEGATIVAS if w in low)
    if neg > pos:
        return "negativo"
    if pos > neg:
        return "positivo"
    return "neutral"


class RulesStructurer:
    """Extrae datos básicos con expresiones regulares."""

    nombre = "rules"

    async def structure(
        self, fuente: FuenteTexto, *, context: StructureContext
    ) -> ExtractionResult:
        texto = fuente.texto_completo
        lineas = [ln for ln in fuente.lineas if ln.texto.strip()]

        # Teléfono: primero el que aparezca en el texto.
        tel = None
        m = _TEL_RE.search(texto)
        if m:
            tel = re.sub(r"[\s.\-]", "", m.group(0))

        # Conteo de mensajes por emisor.
        msgs_cliente = sum(1 for ln in lineas if ln.emisor == "cliente")
        msgs_negocio = sum(1 for ln in lineas if ln.emisor == "negocio")

        cliente = ExtractedCliente(
            nombre=context.nombre_contacto,
            telefono=tel,
            sentimiento_general=_sentimiento(texto),
            resumen="Extracción por reglas (sin IA). Revisar manualmente.",
            total_mensajes_visibles=len(lineas),
            mensajes_del_cliente=msgs_cliente,
            mensajes_del_negocio=msgs_negocio,
            etiquetas=["extraccion_reglas"],
            confianza_extraccion=_CONFIANZA_REGLAS,
        )

        # Un pedido por cada línea que mencione un monto.
        pedidos: list[ExtractedPedido] = []
        for ln in lineas:
            montos = _MONTO_RE.findall(ln.texto)
            if not montos:
                continue
            monto_val = _parse_monto(montos[0]) if isinstance(montos[0], str) else None
            cant_m = _CANTIDAD_RE.search(ln.texto)
            cantidad = float(cant_m.group(1)) if cant_m else None
            unidad = cant_m.group(2).lower() if cant_m else None
            pedidos.append(
                ExtractedPedido(
                    producto_servicio=_producto_aprox(ln.texto),
                    cantidad=cantidad,
                    unidad=unidad,
                    monto_total=monto_val,
                    moneda=context.moneda_default,
                    fecha_pedido=context.fecha_captura,
                    estado_pedido="mencionado",
                    mensaje_origen=ln.texto.strip()[:300],
                    confianza_extraccion=_CONFIANZA_REGLAS,
                )
            )

        warnings = ["Estructurado por reglas locales; confianza baja, requiere revisión."]
        return ExtractionResult(cliente=cliente, pedidos=pedidos, warnings=warnings)


def _producto_aprox(texto: str) -> str:
    """Heurística simple para el nombre del producto: el texto sin el monto."""
    limpio = _MONTO_RE.sub("", texto).strip(" .,-:")
    limpio = re.sub(r"\s+", " ", limpio)
    return limpio[:120] if limpio else "producto sin identificar"

"""Trocear conversaciones largas y unir (map-reduce) los resultados del análisis.

Una conversación de miles de mensajes no cabe en una sola llamada al modelo. La
partimos en trozos, analizamos cada trozo por separado, y unimos: los pedidos se
concatenan (sin duplicar) y los datos del cliente se agregan con reglas simples.
"""
from __future__ import annotations

from collections import Counter

from ..models.extraction import ExtractedCliente, ExtractedPedido, ExtractionResult
from ..pipeline.text_sources import FuenteTexto

# Umbral: por encima de esto, troceamos. ~12k caracteres ≈ varios miles de tokens.
UMBRAL_TROCEO = 12_000
MAX_CHARS_TROZO = 10_000


def necesita_troceo(fuente: FuenteTexto) -> bool:
    return len(fuente.texto_completo) > UMBRAL_TROCEO


def trocear(fuente: FuenteTexto, max_chars: int = MAX_CHARS_TROZO) -> list[FuenteTexto]:
    """Parte la fuente en trozos que no excedan max_chars (respetando líneas)."""
    trozos: list[FuenteTexto] = []
    actuales: list = []
    tam = 0
    for ln in fuente.lineas:
        c = len(ln.texto) + 12
        if actuales and tam + c > max_chars:
            trozos.append(FuenteTexto(tipo=fuente.tipo, lineas=actuales))
            actuales, tam = [], 0
        actuales.append(ln)
        tam += c
    if actuales:
        trozos.append(FuenteTexto(tipo=fuente.tipo, lineas=actuales))
    return trozos


def _dedup_pedidos(pedidos: list[ExtractedPedido]) -> list[ExtractedPedido]:
    vistos = set()
    out = []
    for p in pedidos:
        clave = (p.producto_servicio.strip().lower(), p.monto_total, p.mensaje_origen[:40].strip().lower())
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append(p)
    return out


def _primero_no_vacio(valores):
    for v in valores:
        if v:
            return v
    return None


def merge_results(results: list[ExtractionResult]) -> ExtractionResult:
    """Une varios ExtractionResult (uno por trozo) en uno solo."""
    if len(results) == 1:
        return results[0]

    clientes = [r.cliente for r in results]
    pedidos = _dedup_pedidos([p for r in results for p in r.pedidos])

    # Sentimiento: el más frecuente.
    sent = Counter(c.sentimiento_general for c in clientes).most_common(1)[0][0]
    # Etiquetas: unión, máximo 6.
    etiquetas: list[str] = []
    for c in clientes:
        for e in c.etiquetas:
            if e not in etiquetas:
                etiquetas.append(e)
    etiquetas = etiquetas[:6]
    # Resumen: el del primer y último trozo (evita repetición), recortado.
    resumenes = [c.resumen for c in clientes if c.resumen]
    if len(resumenes) > 2:
        resumen = f"{resumenes[0]} […] {resumenes[-1]}"
    else:
        resumen = " ".join(resumenes)
    resumen = resumen[:600]
    # Fechas: mínima y máxima.
    primeras = [c.primer_mensaje_fecha for c in clientes if c.primer_mensaje_fecha]
    ultimas = [c.ultimo_mensaje_fecha for c in clientes if c.ultimo_mensaje_fecha]
    # Estado: el más "avanzado" si alguno superó 'lead'.
    estados = [c.estado_relacion for c in clientes]
    estado = _primero_no_vacio([e for e in estados if e != "lead"]) or "lead"

    cliente = ExtractedCliente(
        nombre=_primero_no_vacio([c.nombre for c in clientes]),
        telefono=_primero_no_vacio([c.telefono for c in clientes]),
        estado_relacion=estado,
        direccion_principal=_primero_no_vacio([c.direccion_principal for c in clientes]),
        especificaciones_importantes=_primero_no_vacio([c.especificaciones_importantes for c in clientes]),
        sentimiento_general=sent,
        etiquetas=etiquetas,
        resumen=resumen,
        idioma_detectado=clientes[0].idioma_detectado,
        primer_mensaje_fecha=min(primeras) if primeras else None,
        ultimo_mensaje_fecha=max(ultimas) if ultimas else None,
        total_mensajes_visibles=sum(c.total_mensajes_visibles for c in clientes),
        mensajes_del_cliente=sum(c.mensajes_del_cliente for c in clientes),
        mensajes_del_negocio=sum(c.mensajes_del_negocio for c in clientes),
        confianza_extraccion=round(sum(c.confianza_extraccion for c in clientes) / len(clientes), 2),
    )

    warnings = [w for r in results for w in r.warnings]
    warnings.append(f"Conversación larga procesada en {len(results)} partes.")
    return ExtractionResult(cliente=cliente, pedidos=pedidos, warnings=warnings)

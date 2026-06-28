"""Tests del troceo y la unión (map-reduce) para chats largos."""
from __future__ import annotations

from datetime import date

from app.models.extraction import ExtractedCliente, ExtractedPedido, ExtractionResult
from app.pipeline.text_sources import FuenteTexto, Linea
from app.structurer.merge import merge_results, necesita_troceo, trocear


def test_trocea_por_tamano():
    lineas = [Linea(texto="x" * 500, emisor="cliente") for _ in range(50)]
    fuente = FuenteTexto(tipo="export", lineas=lineas)
    trozos = trocear(fuente, max_chars=2000)
    assert len(trozos) > 1
    # No se pierde ninguna línea
    assert sum(len(t.lineas) for t in trozos) == 50


def test_no_trocea_si_es_corto():
    fuente = FuenteTexto(tipo="export", lineas=[Linea(texto="hola", emisor="cliente")])
    assert necesita_troceo(fuente) is False


def test_merge_une_pedidos_y_agrega_cliente():
    r1 = ExtractionResult(
        cliente=ExtractedCliente(nombre="Ana", sentimiento_general="positivo",
                                 etiquetas=["vip"], resumen="Parte 1",
                                 primer_mensaje_fecha=date(2026, 1, 1),
                                 ultimo_mensaje_fecha=date(2026, 1, 5),
                                 mensajes_del_cliente=10, confianza_extraccion=0.8),
        pedidos=[ExtractedPedido(producto_servicio="cajas", monto_total=50000)],
    )
    r2 = ExtractionResult(
        cliente=ExtractedCliente(nombre=None, sentimiento_general="positivo",
                                 etiquetas=["recurrente"], resumen="Parte 2",
                                 primer_mensaje_fecha=date(2026, 2, 1),
                                 ultimo_mensaje_fecha=date(2026, 2, 10),
                                 mensajes_del_cliente=5, confianza_extraccion=0.6),
        pedidos=[ExtractedPedido(producto_servicio="cajas", monto_total=50000),  # duplicado
                 ExtractedPedido(producto_servicio="botellas", monto_total=20000)],
    )
    m = merge_results([r1, r2])

    assert m.cliente.nombre == "Ana"  # primero no vacío
    assert m.cliente.mensajes_del_cliente == 15  # sumado
    assert m.cliente.primer_mensaje_fecha == date(2026, 1, 1)  # mínima
    assert m.cliente.ultimo_mensaje_fecha == date(2026, 2, 10)  # máxima
    assert set(m.cliente.etiquetas) == {"vip", "recurrente"}
    # El pedido duplicado se colapsa: quedan 2 (cajas, botellas)
    assert len(m.pedidos) == 2
    assert any("partes" in w for w in m.warnings)

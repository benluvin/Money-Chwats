"""Tests del estructurador por reglas (Plan B offline)."""
from __future__ import annotations

import asyncio
from datetime import date

from app.pipeline.text_sources import FuenteTexto, Linea
from app.structurer.base import StructureContext
from app.structurer.rules import RulesStructurer, _parse_monto


def _run(coro):
    return asyncio.run(coro)


def test_parse_monto_formatos_colombianos():
    assert _parse_monto("$1.200.000") == 1_200_000
    assert _parse_monto("50.000") == 50_000
    assert _parse_monto("20 mil") == 20_000
    assert _parse_monto("2 millones") == 2_000_000
    assert _parse_monto("50k") == 50_000
    assert _parse_monto("$50,5") == 50.5


def test_extrae_pedido_con_monto_y_cantidad():
    fuente = FuenteTexto(
        tipo="ocr",
        lineas=[
            Linea("Hola, quiero 3 cajas de tornillos", emisor="cliente"),
            Linea("Claro, son $50.000", emisor="negocio"),
        ],
    )
    ctx = StructureContext(nombre_contacto="Pedro", fecha_captura=date(2026, 6, 28))
    res = _run(RulesStructurer().structure(fuente, context=ctx))

    assert res.cliente.nombre == "Pedro"
    assert len(res.pedidos) == 1
    assert res.pedidos[0].monto_total == 50_000
    assert res.pedidos[0].moneda == "COP"


def test_cuenta_mensajes_por_emisor():
    fuente = FuenteTexto(
        tipo="ocr",
        lineas=[
            Linea("hola", emisor="cliente"),
            Linea("buenas", emisor="negocio"),
            Linea("gracias", emisor="cliente"),
        ],
    )
    res = _run(RulesStructurer().structure(fuente, context=StructureContext()))
    assert res.cliente.total_mensajes_visibles == 3
    assert res.cliente.mensajes_del_cliente == 2
    assert res.cliente.mensajes_del_negocio == 1


def test_sentimiento_negativo():
    fuente = FuenteTexto(tipo="ocr", lineas=[Linea("esto es pésimo, una queja", emisor="cliente")])
    res = _run(RulesStructurer().structure(fuente, context=StructureContext()))
    assert res.cliente.sentimiento_general == "negativo"


def test_sin_montos_no_genera_pedidos():
    fuente = FuenteTexto(tipo="ocr", lineas=[Linea("hola buenas tardes", emisor="cliente")])
    res = _run(RulesStructurer().structure(fuente, context=StructureContext()))
    assert res.pedidos == []


def test_confianza_baja_en_reglas():
    fuente = FuenteTexto(tipo="ocr", lineas=[Linea("son $10.000", emisor="negocio")])
    res = _run(RulesStructurer().structure(fuente, context=StructureContext()))
    assert res.cliente.confianza_extraccion < 0.5

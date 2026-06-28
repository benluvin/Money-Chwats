"""Schemas de la información extraída por el LLM y de las filas de CSV resultantes."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

CLIENTES_SCHEMA_VERSION = "clientes-1.0"
PEDIDOS_SCHEMA_VERSION = "pedidos-1.0"

EstadoRelacion = Literal[
    "lead", "activo", "negociando", "cerrado_ganado", "cerrado_perdido", "inactivo",
]
Sentimiento = Literal["positivo", "neutral", "negativo"]
EstadoPedido = Literal[
    "mencionado", "confirmado", "en_preparacion", "entregado", "cancelado", "desconocido",
]


# ---------- LLM output ----------------------------------------------------


class ExtractedCliente(BaseModel):
    nombre: str | None = None
    telefono: str | None = None
    estado_relacion: EstadoRelacion = "lead"
    direccion_principal: str | None = None
    especificaciones_importantes: str | None = None
    sentimiento_general: Sentimiento = "neutral"
    etiquetas: list[str] = Field(default_factory=list)
    resumen: str = ""
    idioma_detectado: str = "es"
    primer_mensaje_fecha: date | None = None
    ultimo_mensaje_fecha: date | None = None
    total_mensajes_visibles: int = 0
    mensajes_del_cliente: int = 0
    mensajes_del_negocio: int = 0
    confianza_extraccion: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractedPedido(BaseModel):
    producto_servicio: str
    cantidad: float | None = None
    unidad: str | None = None
    precio_unitario: float | None = None
    monto_total: float | None = None
    moneda: str = "COP"
    forma_de_pago: str | None = None
    direccion_envio: str | None = None
    fecha_pedido: date | None = None
    fecha_entrega_acordada: date | None = None
    estado_pedido: EstadoPedido = "mencionado"
    notas: str | None = None
    mensaje_origen: str = ""
    confianza_extraccion: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    cliente: ExtractedCliente
    pedidos: list[ExtractedPedido] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------- CSV columns ---------------------------------------------------

CLIENTES_COLUMNS: list[str] = [
    "cliente_id",
    "nombre",
    "telefono_completo",
    "telefono_redactado",
    "primer_mensaje_fecha",
    "ultimo_mensaje_fecha",
    "dias_activos_visibles",
    "total_mensajes_visibles",
    "mensajes_del_cliente",
    "mensajes_del_negocio",
    "estado_relacion",
    "direccion_principal",
    "especificaciones_importantes",
    "sentimiento_general",
    "etiquetas",
    "resumen",
    "idioma_detectado",
    "total_pedidos_detectados",
    "monto_total_pedidos",
    "confianza_extraccion",
    "requiere_revision",
    "ruta_imagen_evidencia",
    "fecha_captura",
    "modelo_llm",
    "metodo_extraccion",
    "version_schema",
]

PEDIDOS_COLUMNS: list[str] = [
    "pedido_id",
    "cliente_id",
    "cliente_nombre",
    "cliente_telefono_redactado",
    "producto_servicio",
    "cantidad",
    "unidad",
    "precio_unitario",
    "monto_total",
    "moneda",
    "forma_de_pago",
    "direccion_envio",
    "fecha_pedido",
    "fecha_entrega_acordada",
    "estado_pedido",
    "notas",
    "mensaje_origen",
    "confianza_extraccion",
    "requiere_revision",
    "ruta_imagen_evidencia",
    "fecha_captura",
    "modelo_llm",
    "metodo_extraccion",
    "version_schema",
]


def _csv_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    return str(v)


def cliente_row_dict(
    *,
    cliente_id: str,
    extracted: ExtractedCliente,
    telefono_completo: str,
    telefono_redactado: str,
    total_pedidos_detectados: int,
    monto_total_pedidos: float | None,
    requiere_revision: bool,
    ruta_imagen_evidencia: str,
    fecha_captura: datetime,
    modelo_llm: str,
    metodo_extraccion: str = "ocr",
) -> dict[str, str]:
    dias = 0
    if extracted.primer_mensaje_fecha and extracted.ultimo_mensaje_fecha:
        dias = (extracted.ultimo_mensaje_fecha - extracted.primer_mensaje_fecha).days + 1
    raw = {
        "cliente_id": cliente_id,
        "nombre": extracted.nombre or "",
        "telefono_completo": telefono_completo,
        "telefono_redactado": telefono_redactado,
        "primer_mensaje_fecha": extracted.primer_mensaje_fecha,
        "ultimo_mensaje_fecha": extracted.ultimo_mensaje_fecha,
        "dias_activos_visibles": dias,
        "total_mensajes_visibles": extracted.total_mensajes_visibles,
        "mensajes_del_cliente": extracted.mensajes_del_cliente,
        "mensajes_del_negocio": extracted.mensajes_del_negocio,
        "estado_relacion": extracted.estado_relacion,
        "direccion_principal": extracted.direccion_principal or "",
        "especificaciones_importantes": extracted.especificaciones_importantes or "",
        "sentimiento_general": extracted.sentimiento_general,
        "etiquetas": extracted.etiquetas,
        "resumen": extracted.resumen,
        "idioma_detectado": extracted.idioma_detectado,
        "total_pedidos_detectados": total_pedidos_detectados,
        "monto_total_pedidos": monto_total_pedidos,
        "confianza_extraccion": extracted.confianza_extraccion,
        "requiere_revision": requiere_revision,
        "ruta_imagen_evidencia": ruta_imagen_evidencia,
        "fecha_captura": fecha_captura,
        "modelo_llm": modelo_llm,
        "metodo_extraccion": metodo_extraccion,
        "version_schema": CLIENTES_SCHEMA_VERSION,
    }
    return {col: _csv_value(raw.get(col)) for col in CLIENTES_COLUMNS}


def pedido_row_dict(
    *,
    pedido_id: str,
    cliente_id: str,
    cliente_nombre: str,
    cliente_telefono_redactado: str,
    extracted: ExtractedPedido,
    requiere_revision: bool,
    ruta_imagen_evidencia: str,
    fecha_captura: datetime,
    modelo_llm: str,
    metodo_extraccion: str = "ocr",
) -> dict[str, str]:
    raw = {
        "pedido_id": pedido_id,
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "cliente_telefono_redactado": cliente_telefono_redactado,
        "producto_servicio": extracted.producto_servicio,
        "cantidad": extracted.cantidad,
        "unidad": extracted.unidad,
        "precio_unitario": extracted.precio_unitario,
        "monto_total": extracted.monto_total,
        "moneda": extracted.moneda,
        "forma_de_pago": extracted.forma_de_pago,
        "direccion_envio": extracted.direccion_envio,
        "fecha_pedido": extracted.fecha_pedido,
        "fecha_entrega_acordada": extracted.fecha_entrega_acordada,
        "estado_pedido": extracted.estado_pedido,
        "notas": extracted.notas,
        "mensaje_origen": extracted.mensaje_origen,
        "confianza_extraccion": extracted.confianza_extraccion,
        "requiere_revision": requiere_revision,
        "ruta_imagen_evidencia": ruta_imagen_evidencia,
        "fecha_captura": fecha_captura,
        "modelo_llm": modelo_llm,
        "metodo_extraccion": metodo_extraccion,
        "version_schema": PEDIDOS_SCHEMA_VERSION,
    }
    return {col: _csv_value(raw.get(col)) for col in PEDIDOS_COLUMNS}

"""Tests del lector de 'Exportar chat' de WhatsApp."""
from __future__ import annotations

from app.pipeline.export_reader import parse_export

# Muestra estilo iOS (español), con multilínea y multimedia omitida.
EXPORT_IOS = """[10/06/26, 6:25:13 p. m.] Migue: Hola Luchi, como vas?
[10/06/26, 6:37:01 p. m.] Luchi: Hola Migue, bien
y tú?
[10/06/26, 6:40:00 p. m.] Migue: Te paso el catálogo
[10/06/26, 6:40:05 p. m.] Migue: imagen omitida
[10/06/26, 6:41:00 p. m.] Luchi: audio omitido
[10/06/26, 6:42:00 p. m.] Luchi: Quiero 3 cajas, cuánto sale?"""

# Muestra estilo Android (español), con mensaje de sistema y multimedia genérica.
EXPORT_ANDROID = """10/6/26, 18:25 - Los mensajes están cifrados de extremo a extremo.
10/6/26, 18:25 - Migue: Buenas
10/6/26, 18:26 - Cliente Nuevo: <Multimedia omitido>
10/6/26, 18:27 - Cliente Nuevo: Listo gracias"""


def test_parse_ios_basico():
    r = parse_export(EXPORT_IOS, owner_name="Migue")
    # 6 mensajes con texto (los de media también cuentan como línea)
    assert r.mensajes >= 5
    # El contacto detectado es Luchi (el que no es el dueño)
    assert r.nombre_contacto == "Luchi"
    # Emisores correctos
    textos_negocio = [l.texto for l in r.fuente.lineas if l.emisor == "negocio"]
    assert any("Hola Luchi" in t for t in textos_negocio)
    textos_cliente = [l.texto for l in r.fuente.lineas if l.emisor == "cliente"]
    assert any("Quiero 3 cajas" in t for t in textos_cliente)


def test_multilinea_se_une():
    r = parse_export(EXPORT_IOS, owner_name="Migue")
    # "Hola Migue, bien\ny tú?" debe quedar en UNA sola línea
    assert any("bien" in l.texto and "tú?" in l.texto for l in r.fuente.lineas)


def test_cuenta_multimedia():
    r = parse_export(EXPORT_IOS, owner_name="Migue")
    assert r.media.imagen == 1
    assert r.media.audio == 1
    assert r.media.total == 2
    assert r.media.hay_multimedia is True
    assert any("multimedia" in w.lower() for w in r.warnings)


def test_android_y_mensaje_sistema_se_ignora():
    r = parse_export(EXPORT_ANDROID, owner_name="Migue")
    # El mensaje de sistema (cifrado) NO debe aparecer como línea
    assert all("cifrados" not in l.texto for l in r.fuente.lineas)
    # Multimedia genérica contada
    assert r.media.generico == 1
    assert r.nombre_contacto == "Cliente Nuevo"


def test_sin_owner_emisores_desconocidos():
    r = parse_export(EXPORT_IOS)  # sin owner_name
    assert all(l.emisor == "desconocido" for l in r.fuente.lineas)

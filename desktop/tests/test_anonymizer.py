"""Tests de la capa de blindaje (seudonimización local)."""
from __future__ import annotations

from app.pipeline.anonymizer import Anonymizer, AnonymizerConfig


def test_blinda_telefono_y_restaura():
    anon = Anonymizer()
    r = anon.anonymize("Llámame al +57 300 123 4567 por favor")
    assert "+57 300 123 4567" not in r.text
    assert "[[TEL_1]]" in r.text
    # Restaurar devuelve el valor real.
    restored = Anonymizer.restore({"telefono": "[[TEL_1]]"}, r.mapping)
    assert restored["telefono"] == "+57 300 123 4567"


def test_blinda_email():
    anon = Anonymizer()
    r = anon.anonymize("escríbeme a juan.perez@gmail.com")
    assert "juan.perez@gmail.com" not in r.text
    assert r.mapping["[[EMAIL_1]]"] == "juan.perez@gmail.com"


def test_blinda_nombre_conocido():
    anon = Anonymizer()
    r = anon.anonymize("Hola, soy Juan Pérez", known_names=["Juan Pérez"])
    assert "Juan Pérez" not in r.text
    assert "[[NOMBRE_1]]" in r.text


def test_nombre_largo_no_se_rompe_por_uno_corto():
    anon = Anonymizer()
    r = anon.anonymize("Juan Pérez pidió algo", known_names=["Juan", "Juan Pérez"])
    # "Juan Pérez" debe tokenizarse como una unidad, no dejar "Pérez" suelto.
    assert "Pérez" not in r.text


def test_blinda_direccion_colombiana():
    anon = Anonymizer()
    r = anon.anonymize("Entregar en Calle 5 # 12-34")
    assert "[[DIR_1]]" in r.text
    assert "12-34" not in r.text


def test_mismo_valor_reusa_token():
    anon = Anonymizer()
    r = anon.anonymize("tel 3001234567 ... repito 3001234567")
    # Un solo token para el mismo número repetido.
    assert r.text.count("[[TEL_1]]") == 2
    assert "[[TEL_2]]" not in r.text


def test_no_toca_contenido_comercial():
    anon = Anonymizer(AnonymizerConfig(redact_addresses=False))
    r = anon.anonymize("Quiero 3 cajas de tornillos")
    # Sin teléfonos/emails/direcciones, el texto comercial queda intacto.
    assert r.text == "Quiero 3 cajas de tornillos"
    assert r.replacements == 0


def test_restore_recursivo_en_estructura_anidada():
    mapping = {"[[TEL_1]]": "3001234567", "[[NOMBRE_1]]": "Ana"}
    obj = {"cliente": {"nombre": "[[NOMBRE_1]]", "telefono": "[[TEL_1]]"},
           "pedidos": [{"notas": "llamar a [[NOMBRE_1]]"}]}
    out = Anonymizer.restore(obj, mapping)
    assert out["cliente"]["nombre"] == "Ana"
    assert out["cliente"]["telefono"] == "3001234567"
    assert out["pedidos"][0]["notas"] == "llamar a Ana"

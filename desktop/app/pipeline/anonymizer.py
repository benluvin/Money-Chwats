"""Capa de blindaje (seudonimización local).

Antes de enviar cualquier texto a un servicio en la nube (p. ej. OpenRouter /
Nemotron), reemplazamos los datos personales sensibles por *tokens* opacos.
El mapa token→valor real NUNCA sale del equipo. Cuando la nube devuelve su
respuesta (con los mismos tokens), restauramos los valores reales localmente.

Así el proveedor de la nube solo ve, por ejemplo:

    "[[NOMBRE_1]] pidió 3 cajas, entregar en [[DIR_1]], tel [[TEL_1]]"

y nunca el nombre, la dirección ni el teléfono reales.

Se blindan: teléfonos, emails, direcciones (heurística colombiana) y los nombres
propios que se conozcan de antemano (p. ej. el nombre del contacto). El contenido
comercial (productos, cantidades, precios) NO se toca: es justo lo que el modelo
debe estructurar.

Sin dependencias externas: solo expresiones regulares. Determinístico y testeable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# El token usa dobles corchetes: sobrevive intacto en JSON y es improbable que
# aparezca en una conversación real.
_TOKEN_RE = re.compile(r"\[\[[A-Z]+_\d+\]\]")

# --- Patrones de detección -------------------------------------------------

# Email estándar.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Teléfonos: + opcional, y 7 a 13 dígitos posiblemente separados por espacios,
# guiones o puntos. Cubre +57 300 123 4567, 3001234567, (601) 123 4567, etc.
_PHONE_RE = re.compile(
    r"""
    (?<![\w])                      # no en medio de una palabra/número mayor
    \+?                            # + opcional (código país)
    (?:\(?\d{1,4}\)?[\s.\-]?)      # primer grupo (con paréntesis opcional)
    (?:\d[\s.\-]?){6,12}\d         # resto de dígitos, total razonable
    (?![\w])
    """,
    re.VERBOSE,
)

# Direcciones colombianas: "Calle 5 # 12-34", "Cra 7 No 8-90", "Av. Caracas 45",
# "Diagonal 12 Sur # 3-4", etc. Heurística — no perfecta, pero conservadora.
_ADDRESS_RE = re.compile(
    r"""
    \b
    (?:calle|cll|carrera|cra|kra|avenida|av|diagonal|diag|transversal|trans|tv|
       autopista|manzana|mz|circular)\.?
    \s*\#?\s*\d+[\w]*                       # número de vía
    (?:\s*(?:bis|sur|norte|este|oeste|n))?  # sufijo opcional
    (?:\s*(?:\#|n[o°.]?|nro\.?)\s*\d+\s*-\s*\d+)?  # "# 12-34" opcional
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class AnonymizationResult:
    """Texto seudonimizado más el mapa para restaurar después."""

    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def replacements(self) -> int:
        return len(self.mapping)


@dataclass
class AnonymizerConfig:
    """Qué categorías blindar. Todo activado por defecto."""

    redact_phones: bool = True
    redact_emails: bool = True
    redact_addresses: bool = True
    redact_names: bool = True


class Anonymizer:
    """Seudonimiza texto y restaura los valores reales en la respuesta."""

    def __init__(self, config: AnonymizerConfig | None = None) -> None:
        self.config = config or AnonymizerConfig()

    def anonymize(
        self, text: str, *, known_names: list[str] | None = None
    ) -> AnonymizationResult:
        """Reemplaza datos sensibles por tokens. Devuelve texto + mapa inverso.

        `known_names`: nombres propios a blindar (p. ej. el del contacto).
        """
        mapping: dict[str, str] = {}
        # value_real -> token, para reutilizar el mismo token ante repeticiones.
        seen: dict[str, str] = {}
        counters: dict[str, int] = {}

        def token_for(kind: str, value: str) -> str:
            value = value.strip()
            key = f"{kind}:{value.lower()}"
            if key in seen:
                return seen[key]
            counters[kind] = counters.get(kind, 0) + 1
            tok = f"[[{kind}_{counters[kind]}]]"
            seen[key] = tok
            mapping[tok] = value
            return tok

        result = text

        # Orden importa: emails antes que teléfonos (un email puede tener dígitos),
        # direcciones antes que teléfonos (una dirección tiene números).
        if self.config.redact_emails:
            result = _EMAIL_RE.sub(lambda m: token_for("EMAIL", m.group(0)), result)

        if self.config.redact_addresses:
            result = _ADDRESS_RE.sub(lambda m: token_for("DIR", m.group(0)), result)

        if self.config.redact_names and known_names:
            # Nombres más largos primero (evita romper "Juan" dentro de "Juan Pérez").
            for name in sorted({n.strip() for n in known_names if n.strip()}, key=len, reverse=True):
                pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
                result = pattern.sub(lambda m, n=name: token_for("NOMBRE", n), result)

        if self.config.redact_phones:
            result = _PHONE_RE.sub(lambda m: token_for("TEL", m.group(0)), result)

        return AnonymizationResult(text=result, mapping=mapping)

    @staticmethod
    def restore(obj, mapping: dict[str, str]):
        """Reemplaza tokens por valores reales recursivamente en str/list/dict."""
        if not mapping:
            return obj
        if isinstance(obj, str):
            return _TOKEN_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), obj)
        if isinstance(obj, list):
            return [Anonymizer.restore(x, mapping) for x in obj]
        if isinstance(obj, dict):
            return {k: Anonymizer.restore(v, mapping) for k, v in obj.items()}
        return obj

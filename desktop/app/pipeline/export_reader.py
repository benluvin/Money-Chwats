"""Lector de archivos "Exportar chat" de WhatsApp (.txt).

Convierte el export en una FuenteTexto (tipo "export") y cuenta la multimedia
omitida (audios, imágenes, etc.) para avisar que conviene re-exportar con
multimedia. Maneja los formatos de iOS y Android, en español e inglés, y mensajes
de varias líneas.

No depende de red ni de modelos: solo texto. Determinístico y testeable.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .text_sources import Emisor, FuenteTexto, Linea

# Encabezado de mensaje:
#  iOS:     [12/06/26, 8:25:13 p. m.] Nombre: texto
#  Android: 12/06/26, 8:25 p. m. - Nombre: texto
_HEADER_IOS = re.compile(
    r"^\[(?P<fecha>\d{1,2}/\d{1,2}/\d{2,4}),?\s+"
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?\s?m\.?)?)\]\s*"
    r"(?P<resto>.*)$",
    re.IGNORECASE,
)
_HEADER_ANDROID = re.compile(
    r"^(?P<fecha>\d{1,2}/\d{1,2}/\d{2,4}),?\s+"
    r"(?P<hora>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?\s?m\.?)?)\s-\s"
    r"(?P<resto>.*)$",
    re.IGNORECASE,
)

# "Nombre: mensaje" dentro de `resto`. Si no hay ": " es un mensaje de sistema.
_SENDER_SPLIT = re.compile(r"^(?P<sender>[^:]{1,80}?):\s(?P<texto>.*)$", re.DOTALL)

# Marcadores de multimedia omitida (ES + EN, iOS + Android).
_MEDIA_KEYWORDS = {
    "audio": ["audio omitido", "audio omitted", "audio ocultado"],
    "imagen": ["imagen omitida", "image omitted", "‎imagen", "<adjunto:"],
    "video": ["video omitido", "vídeo omitido", "video omitted"],
    "sticker": ["sticker omitido", "sticker omitted", "stickeromitido"],
    "gif": ["gif omitido", "gif omitted"],
    "documento": ["documento omitido", "document omitted"],
    "contacto": ["contacto omitido", "contact card omitted", "tarjeta de contacto"],
    "ubicacion": ["ubicación:", "location:"],
}
# Genérico (Android suele poner solo esto):
_MEDIA_GENERIC = ["<multimedia omitido>", "<media omitted>", "multimedia omitido"]


@dataclass
class MediaCounts:
    audio: int = 0
    imagen: int = 0
    video: int = 0
    sticker: int = 0
    gif: int = 0
    documento: int = 0
    contacto: int = 0
    ubicacion: int = 0
    generico: int = 0

    @property
    def total(self) -> int:
        return (self.audio + self.imagen + self.video + self.sticker + self.gif
                + self.documento + self.contacto + self.ubicacion + self.generico)

    @property
    def hay_multimedia(self) -> bool:
        return self.total > 0


@dataclass
class ExportResult:
    fuente: FuenteTexto
    media: MediaCounts
    nombre_contacto: str | None = None
    mensajes: int = 0
    warnings: list[str] = field(default_factory=list)


def _strip_invisibles(s: str) -> str:
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf").strip()


def _clasificar_media(texto_low: str, mc: MediaCounts) -> bool:
    """Si el texto es un marcador de multimedia, lo cuenta y devuelve True."""
    for tipo, claves in _MEDIA_KEYWORDS.items():
        if any(k in texto_low for k in claves):
            setattr(mc, tipo, getattr(mc, tipo) + 1)
            return True
    if any(k in texto_low for k in _MEDIA_GENERIC):
        mc.generico += 1
        return True
    return False


def _match_header(line: str):
    m = _HEADER_IOS.match(line)
    if m:
        return m.group("resto")
    m = _HEADER_ANDROID.match(line)
    if m:
        return m.group("resto")
    return None


def parse_export(text: str, *, owner_name: str | None = None) -> ExportResult:
    """Parsea el texto de un export de WhatsApp.

    owner_name: el nombre del dueño del negocio (tú). Sus mensajes se marcan como
    "negocio"; el resto como "cliente". Si no se da, quedan "desconocido".
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    mc = MediaCounts()
    lineas: list[Linea] = []
    senders: dict[str, int] = {}
    owner_norm = _strip_invisibles(owner_name).lower() if owner_name else None

    cur_sender: str | None = None
    cur_text: list[str] = []
    cur_is_media = False

    def flush() -> None:
        nonlocal cur_sender, cur_text, cur_is_media
        if cur_sender is None and not cur_text:
            return
        texto = _strip_invisibles("\n".join(cur_text))
        if cur_sender is not None and texto:
            emisor: Emisor = "desconocido"
            if owner_norm is not None:
                emisor = "negocio" if _strip_invisibles(cur_sender).lower() == owner_norm else "cliente"
            lineas.append(Linea(texto=texto, emisor=emisor, confianza=1.0))
        cur_sender, cur_text, cur_is_media = None, [], False

    for raw in lines:
        resto = _match_header(raw)
        if resto is not None:
            flush()
            sm = _SENDER_SPLIT.match(resto)
            if sm:
                cur_sender = _strip_invisibles(sm.group("sender"))
                msg = sm.group("texto")
                senders[cur_sender] = senders.get(cur_sender, 0) + 1
                low = _strip_invisibles(msg).lower()
                cur_is_media = _clasificar_media(low, mc)
                cur_text = [msg]
            else:
                # Mensaje de sistema (cifrado, llamadas, etc.): se ignora.
                cur_sender, cur_text, cur_is_media = None, [], False
        else:
            # Continuación de un mensaje multilínea.
            if cur_sender is not None:
                cur_text.append(raw)
                if not cur_is_media:
                    cur_is_media = _clasificar_media(_strip_invisibles(raw).lower(), mc)
    flush()

    # El contacto = el remitente más frecuente que NO es el dueño.
    nombre_contacto = None
    if senders:
        candidatos = {s: n for s, n in senders.items()
                      if not (owner_norm and _strip_invisibles(s).lower() == owner_norm)}
        if candidatos:
            nombre_contacto = max(candidatos, key=candidatos.get)

    warnings = []
    if mc.hay_multimedia:
        warnings.append(
            f"Esta conversación tiene {mc.total} elementos multimedia omitidos "
            f"(audios: {mc.audio}, imágenes: {mc.imagen}). Considera re-exportar con multimedia."
        )

    return ExportResult(
        fuente=FuenteTexto(tipo="export", lineas=lineas),
        media=mc,
        nombre_contacto=nombre_contacto,
        mensajes=len(lineas),
        warnings=warnings,
    )

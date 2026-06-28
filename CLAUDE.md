# Money Chwats — Contexto del proyecto

Herramienta local para extraer datos estructurados de conversaciones de WhatsApp Web,
sin riesgo de ban por automatización (arquitectura "Camino B" — extensión puramente
reactiva, ningún click/scroll automatizado dentro de WhatsApp).

## Componentes

- **`extension/`** — Chrome Extension MV3, TypeScript. Se inyecta en `web.whatsapp.com`,
  lee el DOM de la conversación que el usuario tiene abierta, captura screenshot y
  envía todo al servicio desktop. No automatiza navegación entre chats.
- **`desktop/`** — Servicio Python FastAPI escuchando en `127.0.0.1:5000`. Recibe la
  captura, guarda PNG, persiste DOM como JSON, mantiene `clientes.csv` y (en hitos
  futuros) `pedidos.csv` con datos extraídos por LLM local (Qwen2-VL vía Ollama).

## Reglas estrictas

- **Solo localhost.** El servicio bind únicamente a `127.0.0.1`, nunca `0.0.0.0`.
- **Shared secret** entre extensión y servicio vía header `X-Auth-Token`.
- **Sin telemetría, sin red externa** (excepto Google Sheets opcional opt-in en M5).
- **Sin automatización dentro de WhatsApp Web**: el usuario abre cada chat, hace scroll
  él mismo si quiere ver mensajes viejos, y dispara la captura con un shortcut.
  La extensión solo lee el DOM ya cargado y captura lo visible.

## Convenciones

- CSVs con separador `;`, UTF-8 con BOM (Excel-friendly), decimales con `.`.
- Fechas ISO 8601.
- Moneda por defecto **COP** (peso colombiano).
- Idioma 100% español.
- IDs determinísticos: `client_id = uuid5(NAMESPACE_DNS, jid)` → reprocesamiento idempotente.

## Estructura de datos en disco

```
~/CapturasWhatsApp/
├── raw/YYYY/MM/DD/<client_id>_<capture_id>.png
├── data/
│   ├── clientes.csv
│   ├── pedidos.csv               # desde M3
│   └── dom/<client_id>_<capture_id>.json
└── logs/service.log
```

## Stack

- Desktop: Python 3.11+, FastAPI, uvicorn, Pydantic v2, filelock, tomli.
- Extensión: TypeScript, esbuild, Manifest V3, sin frameworks.
- LLM (desde M3): Qwen2-VL-7B-Instruct vía Ollama, fallback Qwen2-VL-2B.

## Roadmap

- **M1** — Esqueleto end-to-end (este hito). Captura + storage + CSV básico, sin LLM.
- **M2** — Renderizador de PNG-evidencia + ingesta vía "Exportar chat" (file watcher).
- **M3** — LLM pipeline (Qwen2-VL) + `pedidos.csv` + schema completo.
- **M4** — UI de revisión (filas con `requiere_revision`).
- **M5** — Empaquetado tri-OS + tray + Google Sheets opt-in + backup zip.
- **M6** — Robustez a escala (rotación, cifrado opt-in, dashboards).

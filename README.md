# Money Chwats

Herramienta local para extraer información estructurada de conversaciones de WhatsApp Web
(clientes, pedidos, sentimiento, etc.) usando un LLM local. Diseñada para negocios con
miles de conversaciones sin levantamiento previo.

**Arquitectura:** extensión Chrome puramente reactiva + servicio Python local en `:5000`.
Sin automatización de navegación dentro de WhatsApp → cero riesgo de ban.

## Estado: M1 (esqueleto end-to-end)

Lo que funciona en M1:
- Servicio FastAPI corriendo en `127.0.0.1:5000`.
- Pairing extensión ↔ servicio vía código de 6 dígitos.
- Captura manual: usuario abre un chat, pulsa shortcut, se guardan PNG + DOM + fila en `clientes.csv`.

Lo que aún NO funciona (siguientes hitos):
- LLM (M3).
- Stitching de scroll completo (M2).
- Pedidos.csv (M3).
- Empaquetado / tray (M5).

## Quick start (desarrollo)

### 1. Servicio desktop

```bash
cd desktop
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp ../config.example.toml config.toml
uvicorn app.main:app --port 5000
```

Comprobar: `curl http://127.0.0.1:5000/health` → `{"status":"ok"}`.

### 2. Extensión Chrome

```bash
cd extension
npm install
npm run build
```

En Chrome: `chrome://extensions` → "Modo desarrollador" → "Cargar descomprimida" → seleccionar `extension/dist/`.

### 3. Emparejar

1. Abrir el popup de la extensión → "Emparejar".
2. La terminal del servicio imprime un código de 6 dígitos.
3. Pegarlo en el popup → "Confirmar".

### 4. Capturar

1. Abrir `web.whatsapp.com`.
2. Entrar en una conversación.
3. Pulsar `Ctrl/Cmd+Shift+S` (o el botón del popup).
4. Verificar en `~/CapturasWhatsApp/` que se generaron PNG, JSON y fila CSV.

## Estructura del repo

- `extension/` — Chrome Extension MV3, TypeScript.
- `desktop/` — Servicio Python FastAPI.
- `config.example.toml` — plantilla de configuración.
- `CLAUDE.md` — contexto del proyecto para asistentes IA.

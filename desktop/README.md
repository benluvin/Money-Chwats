# Money Chwats — Desktop service

Servicio FastAPI local que escucha en `127.0.0.1:5000` y recibe capturas de WhatsApp
desde la extensión Chrome. En M1 solo persiste; el LLM se integra en M3.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../config.example.toml config.toml
```

## Correr

```bash
uvicorn app.main:app --port 5000 --reload
```

## Tests

```bash
pytest
```

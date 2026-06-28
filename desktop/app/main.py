"""FastAPI app entrypoint. Bind exclusivo a 127.0.0.1 — sin auth, sin emparejamiento."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_config
from .routes import capture, files, health, import_export, process

log = logging.getLogger("money_chwats")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    cfg = get_config()
    root = cfg.storage.root_path
    root.mkdir(parents=True, exist_ok=True)
    log.info(
        "Money Chwats v%s lista en http://%s:%d",
        __version__, cfg.server.host, cfg.server.port,
    )
    log.info("Carpeta de datos: %s", root)

    # Vigilante de carpeta (solo si hay buzón configurado).
    watcher_task = None
    if cfg.export.inbox_dir:
        from .pipeline.watcher import watch_loop
        from .structurer.factory import build_structurer

        watcher_task = asyncio.create_task(watch_loop(cfg, build_structurer))

    yield

    if watcher_task:
        watcher_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Money Chwats — Desktop Service",
        version=__version__,
        description="Servicio local que recibe capturas de WhatsApp desde la extensión Chrome.",
        lifespan=_lifespan,
    )

    # CORS abierto a cualquier chrome-extension. Solo escuchamos en 127.0.0.1,
    # así que el alcance ya está limitado a la máquina del usuario.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-z0-9]+$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
        max_age=600,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(capture.router, tags=["capture"])
    app.include_router(files.router, tags=["files"])
    app.include_router(process.router, tags=["process"])
    app.include_router(import_export.router, tags=["import"])
    return app


app = create_app()

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .anchoring.router import router as anchoring_router
from .auth.router import router as auth_router
from .auth.router import users_router
from .core.config import get_settings
from .core.errors import install_error_handlers
from .inspections.ingest import router as ingest_router
from .inspections.router import router as inspections_router
from .registry.router import router as registry_router
from .services.feed import hub


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="LEDGEIT API",
        version=__version__,
        description="Tamper-evident chain of custody for AI inspection decisions.",
    )
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api/v1")
    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(ingest_router)
    api.include_router(inspections_router)
    api.include_router(registry_router)
    api.include_router(anchoring_router)

    @api.get("/health", tags=["meta"])
    def health():
        return {"status": "ok", "version": __version__, "chain": s.chain}

    app.include_router(api)

    @app.on_event("startup")
    async def _bind_feed_loop():
        import asyncio

        hub.bind_loop(asyncio.get_running_loop())

    return app


app = create_app()

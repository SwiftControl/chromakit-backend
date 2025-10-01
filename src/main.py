from __future__ import annotations

from fastapi import FastAPI

from src.infrastructure.api.middlewares import add_default_middlewares
from src.infrastructure.api.routes.auth_routes import router as auth_router
from src.infrastructure.api.routes.image_routes import router as image_router
from src.infrastructure.api.routes.processing_routes import router as processing_router
from src.infrastructure.api.routes.history_routes import router as history_router


def create_app() -> FastAPI:
    app = FastAPI(title="ChromaKit Backend", version="0.1.0")
    add_default_middlewares(app)

    @app.get("/")
    def root():
        return {"status": "ok", "service": "chromakit-backend", "version": app.version}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    app.include_router(auth_router)
    app.include_router(image_router)
    app.include_router(processing_router)
    app.include_router(history_router)
    return app


app = create_app()

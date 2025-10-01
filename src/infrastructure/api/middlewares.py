from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


def add_default_middlewares(app: FastAPI) -> None:
    # Permissive CORS for development; tighten in production as needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

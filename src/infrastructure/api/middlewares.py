from __future__ import annotations

import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


def add_default_middlewares(app: FastAPI) -> None:
    # CORS configuration
    # In development/demo mode, allow common frontend origins
    # In production, this should be restricted to specific domains
    env = os.getenv("ENV", "development")
    
    if env in ("development", "staging"):
        # Allow common development origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",  # Vite default
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
        ]
    else:
        # Production: use wildcard (should be restricted to actual domains)
        allowed_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

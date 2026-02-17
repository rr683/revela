"""
FastAPI application -- REST API for the reconstruction platform.

Usage:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import get_config
from api.routes import router

logger = logging.getLogger(__name__)

config = get_config()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Revela - 3D Reconstruction API",
        description="Convert video and images into 3D models using NeRF and Gaussian Splatting",
        version="0.2.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router, prefix="/api")

    @application.get("/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    return application


app = create_app()

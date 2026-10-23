"""
OfficeVision AI - Main FastAPI Application Server
==================================================

Serves:
  - REST API for Workstation Management, Attendance, and Audit Reporting
  - WebSockets for Edge AI Telemetry Ingestion and Real-time Dashboard Sync
  - Interactive Swagger OpenAPI Documentation at `/docs`
"""

import sys
from pathlib import Path

# Ensure backend/app is in python search path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from api.v1.endpoints import router as api_v1_router
from api.v1.websockets import router as ws_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Workspace presence monitoring and voluntary activity analytics backend.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/", summary="Root Health Check")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "RUNNING",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)

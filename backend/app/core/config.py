"""
OfficeVision AI - Backend Configuration & Settings
===================================================
"""

from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    PROJECT_NAME: str = "OfficeVision AI Backend"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS settings to allow local React development frontend
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",  # Permissive for development prototype
    ]

    # Server parameters
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()

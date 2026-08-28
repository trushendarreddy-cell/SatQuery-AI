import os
from pathlib import Path

class Settings:
    """Application configuration settings."""
    PROJECT_NAME: str = "SatQuery AI Backend"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "temp" / "uploads"
    CACHE_DIR: Path = BASE_DIR / "temp" / "cache"

    def __init__(self):
        # Ensure working directories exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()

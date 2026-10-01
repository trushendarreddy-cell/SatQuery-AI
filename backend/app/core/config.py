import os
from pathlib import Path

class Settings:
    """Application configuration settings."""
    PROJECT_NAME: str = "SatQuery AI Backend"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "temp" / "uploads"
    CACHE_DIR: Path = BASE_DIR / "temp" / "cache"
    STORAGE_ROOT: Path = BASE_DIR / "temp" / "storage"

    # CORS / security configuration
    CORS_ALLOWED_ORIGINS: list[str] = [
        origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if origin.strip()
    ]
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(50 * 1024 * 1024)))

    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    @classmethod
    def resolved_database_url(cls) -> str:
        """Return the database URL, creating the SQLite parent directory.

        On Linux a SQLite file whose parent directory does not exist is not
        created at all, and create_all() then silently leaves an empty
        database behind. The temp/ directory is gitignored, so a fresh clone
        does not have it and every persistence test failed with
        "no such table: sessions" until this was fixed.
        """
        if cls.DATABASE_URL:
            return cls.DATABASE_URL

        db_path = cls.BASE_DIR / "temp" / "satquery.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return "sqlite:///" + db_path.resolve().as_posix()

    # LLM provider configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Vision provider configuration
    VISION_PROVIDER: str = os.getenv("VISION_PROVIDER", "mock")
    VISION_API_KEY: str = os.getenv("VISION_API_KEY", "")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "gpt-4o-mini")
    VISION_BASE_URL: str = os.getenv("VISION_BASE_URL", "https://api.openai.com/v1")
    VISION_MAX_TOKENS: int = int(os.getenv("VISION_MAX_TOKENS", "1024"))
    VISION_TEMPERATURE: float = float(os.getenv("VISION_TEMPERATURE", "0.0"))

    def __init__(self):
        # Ensure working directories exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


settings = Settings()

import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.core.config import settings
from app.schemas.metadata_schema import UnifiedImageMetadata


@dataclass
class SessionData:
    """Holds active session state, images, and file paths."""
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    images: Dict[str, UnifiedImageMetadata] = field(default_factory=dict)
    file_paths: Dict[str, Path] = field(default_factory=dict)
    session_dir: Path = field(init=False)

    def __post_init__(self):
        self.session_dir = settings.CACHE_DIR / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)


class SessionManager:
    """Manages active sessions and intermediate cached files in memory and disk."""

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionData:
        """Retrieves existing session or initializes a new unique session."""
        sid = session_id.strip() if session_id and session_id.strip() else uuid.uuid4().hex[:12]
        if sid not in self._sessions:
            self._sessions[sid] = SessionData(session_id=sid)
        return self._sessions[sid]

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieves session data by ID if it exists."""
        return self._sessions.get(session_id)

    def add_image(
        self, session_id: str, file_path: Path, metadata: UnifiedImageMetadata
    ) -> UnifiedImageMetadata:
        """Registers an uploaded/processed image inside a session."""
        session = self.get_or_create_session(session_id)
        session.images[metadata.image_id] = metadata
        session.file_paths[metadata.image_id] = file_path
        session.updated_at = datetime.now(timezone.utc)
        return metadata

    def get_images(self, session_id: str) -> List[UnifiedImageMetadata]:
        """Returns all image metadata objects in a session in insertion order."""
        session = self.get_session(session_id)
        if not session:
            return []
        return list(session.images.values())

    def get_image_file_path(self, session_id: str, image_id: str) -> Optional[Path]:
        """Returns the disk file path of an image within a session."""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.file_paths.get(image_id)

    def delete_session(self, session_id: str) -> bool:
        """Deletes session data from memory and cleans its cache directory."""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            if session.session_dir.exists():
                try:
                    shutil.rmtree(session.session_dir)
                except Exception:
                    pass
            return True
        return False

    def clear_all(self):
        """Clears all sessions (useful for tests)."""
        self._sessions.clear()


# Global singleton instance
session_manager = SessionManager()

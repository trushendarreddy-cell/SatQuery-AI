"""Safe file path utilities for artifact management."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


def safe_filename(name: str, max_length: int = 255) -> str:
    """Sanitize a filename by removing unsafe characters and limiting length."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[^\w.\-]', '_', name)
    name = name.strip('._-')
    if len(name) > max_length:
        name = name[:max_length]
    return name or 'artifact'


def safe_path(base_dir: Path, filename: str) -> Path:
    """Create a safe file path within base_dir, preventing path traversal."""
    safe_name = safe_filename(filename)
    resolved = (base_dir / safe_name).resolve()
    base_resolved = base_dir.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(f"Path traversal detected: {filename}") from exc
    return resolved

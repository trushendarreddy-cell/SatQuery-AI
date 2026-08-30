"""Agent context service (M15).

Provides stable, structured session/image/storage context to Master Agent.
The Master Agent uses this to understand the session and make decisions.

Key principle: No raw filesystem paths exposed; everything is safe storage keys.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.session_cache import session_manager
from app.core.path_utils import safe_filename
from app.db.models import SessionRecord, ImageRecord, ArtifactRecord
from app.schemas.agent_integration_schema import (
    AgentContextData,
    ImageContextData,
    SpatialContextData,
    ArtifactReferenceData,
    ImageModality,
)


class AgentContextService:
    """Provides session context to Master Agent."""

    @staticmethod
    def get_agent_context(session_id: str) -> Optional[AgentContextData]:
        """Get complete session context for Master Agent.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AgentContextData with images, spatial context, artifacts, or None if not found
        """
        # Get session from runtime cache
        session = session_manager.get_session(session_id)
        if not session:
            return None

        # Build image contexts
        image_contexts = []
        for image_id, image_meta in session.images.items():
            image_context = AgentContextService._build_image_context(session_id, image_id, image_meta)
            if image_context:
                image_contexts.append(image_context)

        # Determine modalities and timestamps
        modalities = set()
        timestamps = set()
        for img_ctx in image_contexts:
            modalities.add(img_ctx.modality)
            if img_ctx.timestamp:
                timestamps.add(img_ctx.timestamp)

        # Get spatial context
        spatial_context = AgentContextService._build_spatial_context(image_contexts)

        # Get artifacts (from cache/session)
        artifact_refs = AgentContextService._build_artifact_references(session_id)

        # Build final context
        return AgentContextData(
            session_id=session_id,
            created_at=session.created_at.isoformat() if hasattr(session, "created_at") else datetime.now().isoformat(),
            image_count=len(image_contexts),
            images=image_contexts,
            modalities=sorted(list(modalities)),
            timestamps=sorted(list(timestamps)),
            spatial_context=spatial_context,
            artifacts=artifact_refs,
            metadata={
                "session_dir": str(session.session_dir),
                "file_count": len(session.file_paths),
            },
        )

    @staticmethod
    def _build_image_context(session_id: str, image_id: str, image_meta) -> Optional[ImageContextData]:
        """Build context for a single image."""
        try:
            filename = getattr(image_meta, "filename", f"image_{image_id}")
            
            # Determine modality
            modality = ImageModality.UNKNOWN
            if hasattr(image_meta, "modality"):
                modality_str = str(image_meta.modality).lower()
                try:
                    modality = ImageModality(modality_str)
                except ValueError:
                    modality = ImageModality.UNKNOWN

            # Build storage key (safe reference, no filesystem path)
            storage_key = AgentContextService._build_storage_key(session_id, image_id, filename)

            # Extract metadata
            metadata = {}
            if hasattr(image_meta, "metadata"):
                metadata = image_meta.metadata if isinstance(image_meta.metadata, dict) else {}

            # Extract spatial info
            bounds_wgs84 = None
            if hasattr(image_meta, "bounds_wgs84"):
                bounds_wgs84 = image_meta.bounds_wgs84
            elif "geospatial" in metadata:
                bounds_wgs84 = metadata["geospatial"].get("bounds_wgs84")

            crs = metadata.get("crs") or (metadata.get("geospatial", {}).get("crs") if "geospatial" in metadata else None)
            timestamp = metadata.get("acquisition_date") or metadata.get("timestamp")

            return ImageContextData(
                image_id=image_id,
                filename=filename,
                storage_key=storage_key,
                modality=modality,
                timestamp=timestamp,
                crs=crs,
                width=metadata.get("width"),
                height=metadata.get("height"),
                band_count=metadata.get("band_count"),
                bounds_wgs84=bounds_wgs84,
                metadata=metadata,
            )
        except Exception:
            return None

    @staticmethod
    def _build_storage_key(session_id: str, image_id: str, filename: str) -> str:
        """Build safe storage reference (no filesystem path).
        
        This key can be used to resolve the image later via get_image_reference.
        """
        safe_name = safe_filename(filename)
        return f"session://{session_id}/image/{image_id}/{safe_name}"

    @staticmethod
    def _build_spatial_context(image_contexts: list) -> SpatialContextData:
        """Determine spatial compatibility."""
        if not image_contexts:
            return SpatialContextData(
                common_crs=None,
                bounds_intersection=None,
                all_georeferenced=False,
                compatible_for_temporal=False,
            )

        # Check if all georeferenced
        all_geo = all(img.crs for img in image_contexts)

        # Find common CRS (if exists)
        common_crs = None
        if all_geo:
            crss = {img.crs for img in image_contexts}
            if len(crss) == 1:
                common_crs = crss.pop()

        # Placeholder for bounds intersection (would require rasterio in production)
        bounds_intersection = None
        if len(image_contexts) > 0:
            first_bounds = image_contexts[0].bounds_wgs84
            if first_bounds:
                bounds_intersection = first_bounds.copy()

        return SpatialContextData(
            common_crs=common_crs,
            bounds_intersection=bounds_intersection,
            all_georeferenced=all_geo,
            compatible_for_temporal=(len(image_contexts) >= 2 and all_geo),
        )

    @staticmethod
    def _build_artifact_references(session_id: str) -> list:
        """Get artifact references for session."""
        session = session_manager.get_session(session_id)
        if not session:
            return []

        artifacts = []
        for artifact_id, file_path in session.file_paths.items():
            if "artifact" in artifact_id.lower() or file_path.suffix in [".tif", ".tiff", ".json", ".geojson"]:
                try:
                    storage_key = f"session://{session_id}/artifact/{artifact_id}"
                    artifacts.append(
                        ArtifactReferenceData(
                            artifact_id=artifact_id,
                            artifact_type="raster" if file_path.suffix in [".tif", ".tiff"] else "vector",
                            filename=file_path.name,
                            storage_key=storage_key,
                            file_size=file_path.stat().st_size if file_path.exists() else 0,
                        )
                    )
                except Exception:
                    pass
        return artifacts


class ImageAccessService:
    """Provides safe image access to Master Agent."""

    @staticmethod
    def resolve_image(session_id: str, image_id: str) -> Optional[Path]:
        """Resolve image file path safely.
        
        Args:
            session_id: Session identifier
            image_id: Image identifier
            
        Returns:
            Safe Path to image file, or None if not found
            
        Raises:
            ValueError: If path traversal is detected
        """
        session = session_manager.get_session(session_id)
        if not session:
            return None

        # Find image by ID
        if image_id not in session.images:
            return None

        # Get image file path from cache
        image_meta = session.images[image_id]
        if hasattr(image_meta, "file_path"):
            file_path = Path(image_meta.file_path)
            # Verify it's within session directory
            try:
                file_path.relative_to(session.session_dir)
                return file_path
            except ValueError:
                raise ValueError(f"Path traversal detected: {file_path}")

        return None

    @staticmethod
    def get_image_reference(session_id: str, image_id: str) -> Optional[dict]:
        """Get complete image reference for Master Agent.
        
        Returns structured dict with filename, storage_key, modality, metadata.
        """
        session = session_manager.get_session(session_id)
        if not session or image_id not in session.images:
            return None

        image_meta = session.images[image_id]
        context = AgentContextService.get_agent_context(session_id)
        if not context:
            return None

        # Find matching image in context
        for img in context.images:
            if img.image_id == image_id:
                return {
                    "image_id": img.image_id,
                    "filename": img.filename,
                    "storage_key": img.storage_key,
                    "modality": img.modality.value,
                    "crs": img.crs,
                    "metadata": img.metadata,
                }

        return None


class ArtifactAccessService:
    """Provides safe artifact access to Master Agent."""

    @staticmethod
    def get_artifact_reference(session_id: str, artifact_id: str) -> Optional[dict]:
        """Get artifact reference for downloading."""
        session = session_manager.get_session(session_id)
        if not session:
            return None

        # Verify artifact belongs to session
        if artifact_id not in session.file_paths:
            return None

        file_path = session.file_paths[artifact_id]
        
        # Verify within session directory
        try:
            file_path.relative_to(session.session_dir)
        except ValueError:
            raise ValueError(f"Path traversal detected: {file_path}")

        return {
            "artifact_id": artifact_id,
            "filename": file_path.name,
            "storage_key": f"session://{session_id}/artifact/{artifact_id}",
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "mime_type": "application/octet-stream",
        }

    @staticmethod
    def download_artifact(session_id: str, artifact_id: str) -> Optional[Path]:
        """Get safe path for artifact download."""
        session = session_manager.get_session(session_id)
        if not session or artifact_id not in session.file_paths:
            return None

        file_path = session.file_paths[artifact_id]
        
        # Verify within session directory
        try:
            file_path.relative_to(session.session_dir)
            if file_path.exists():
                return file_path
        except ValueError:
            raise ValueError(f"Path traversal detected: {file_path}")

        return None

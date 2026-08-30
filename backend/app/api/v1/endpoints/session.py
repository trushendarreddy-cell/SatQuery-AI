from pathlib import Path

from fastapi import APIRouter, File, HTTPException, status
from fastapi.responses import FileResponse

from app.core.path_utils import safe_path
from app.core.session_cache import session_manager
from app.schemas.scene_schema import SessionStateResponse, SceneClassificationResult
from app.pipeline.scene_classifier import SceneClassifier

router = APIRouter()


@router.get(
    "/{session_id}/artifacts",
    status_code=status.HTTP_200_OK,
    summary="List artifacts available in a session",
    description="Returns stored artifact files for a session without exposing raw filesystem paths.",
)
async def list_session_artifacts(session_id: str):
    """Return artifact metadata for a session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    artifacts = []
    seen = set()
    for file_path in session.file_paths.values():
        if not file_path or not file_path.exists():
            continue
        name = file_path.name
        if name in seen:
            continue
        seen.add(name)
        artifacts.append({
            "filename": name,
            "path": str(file_path),
            "size_bytes": file_path.stat().st_size if file_path.is_file() else 0,
        })

    return {"session_id": session_id, "artifacts": artifacts}


@router.get(
    "/{session_id}/artifacts/{filename}",
    status_code=status.HTTP_200_OK,
    summary="Download a single artifact from a session",
    description="Returns a safe, session-relative artifact file while preventing traversal outside the session directory.",
)
async def download_session_artifact(session_id: str, filename: str):
    """Download a specific artifact file from a session, safely enforcing the session directory boundary."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    try:
        safe_file = safe_path(session.session_dir, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not safe_file.exists() or not safe_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found in session '{session_id}'.",
        )

    return FileResponse(path=safe_file, filename=safe_file.name, media_type="application/octet-stream")


@router.get(
    "/{session_id}",
    response_model=SessionStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active session state and image metadata",
    description="Retrieves the current session state, active image profiles, and scene configuration.",
)
async def get_session_state(session_id: str):
    """Retrieves session overview and current classification."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    session_images = session_manager.get_images(session_id)
    classification = SceneClassifier.classify(session_images, session_id)

    return SessionStateResponse(
        session_id=session_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        image_count=len(session_images),
        classification=classification,
    )


@router.get(
    "/{session_id}/scene",
    response_model=SceneClassificationResult,
    status_code=status.HTTP_200_OK,
    summary="Get scene configuration and image relationship analysis",
    description="Returns evidence-based scene classification (single, bi-temporal, optical+SAR, or multi-image).",
)
async def get_scene_classification(session_id: str):
    """Inspects the session's images and returns its scene classification."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    session_images = session_manager.get_images(session_id)
    return SceneClassifier.classify(session_images, session_id)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a session and clear cached files",
    description="Deletes in-memory session metadata and removes all temporary cached rasters on disk.",
)
async def delete_session(session_id: str):
    """Deletes session and clears disk artifacts."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return {"message": f"Session '{session_id}' and all associated files deleted successfully."}

from fastapi import APIRouter, HTTPException, status

from app.core.session_cache import session_manager
from app.schemas.scene_schema import SessionStateResponse, SceneClassificationResult
from app.pipeline.scene_classifier import SceneClassifier

router = APIRouter()


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

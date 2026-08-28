import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Form, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.session_cache import session_manager
from app.schemas.metadata_schema import (
    InspectResponse,
    ValidationResult,
    ImageCategory,
)
from app.schemas.scene_schema import SessionStateResponse
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.scene_classifier import SceneClassifier

router = APIRouter()


@router.post(
    "/inspect",
    response_model=InspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect and profile a single image (JPG/PNG or GeoTIFF)",
    description=(
        "Uploads a single image (JPG/PNG visual photo or GeoTIFF satellite raster), "
        "performs structural validation, determines sensor modality, and returns structured metadata."
    ),
)
async def inspect_image(file: UploadFile = File(...)):
    """
    Dual-path image ingestion endpoint for a single image:
    - GeoTIFF path: Validates CRS, extracts WGS84 bounds, resolution, and band stats.
    - JPG/PNG path: Validates visual readability, dimensions, and channels without fabricating geospatial metadata.
    """
    image_uuid = uuid.uuid4().hex[:8]
    safe_filename = f"{image_uuid}_{file.filename}"
    temp_file_path = settings.UPLOAD_DIR / safe_filename

    try:
        # 1. Stream uploaded file to temporary disk location
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Universal validation (routes to GeoTIFF or Visual pipeline)
        validation_result: ValidationResult = UniversalImageValidator.validate(temp_file_path)

        if not validation_result.is_valid:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=InspectResponse(
                    success=False,
                    message="The uploaded file failed validation checks.",
                    validation=validation_result,
                    metadata=None,
                ).model_dump(),
            )

        # 3. Extract metadata according to validated category
        metadata = UniversalMetadataExtractor.extract(
            file_path=temp_file_path,
            category=validation_result.category,
            image_id=image_uuid,
            compute_stats=True,
        )

        return InspectResponse(
            success=True,
            message=f"Successfully processed {validation_result.category.value.replace('_', ' ')} image.",
            validation=validation_result,
            metadata=metadata,
        )

    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=InspectResponse(
                success=False,
                message=f"An unexpected error occurred during image processing: {str(exc)}",
                validation=ValidationResult(
                    is_valid=False,
                    category=ImageCategory.VISUAL_STANDARD,
                    errors=[str(exc)],
                    warnings=[],
                ),
                metadata=None,
            ).model_dump(),
        )
    finally:
        await file.close()


@router.post(
    "/upload",
    response_model=SessionStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload 1 or more images into a session and classify scene configuration",
    description=(
        "Uploads one or more images into an active or new session. "
        "Validates and registers each image, maintains individual metadata, "
        "and produces evidence-based scene configuration (single, bi-temporal, optical+SAR, or multi-image)."
    ),
)
async def upload_images_to_session(
    files: List[UploadFile] = File(..., description="One or more images to upload"),
    session_id: Optional[str] = Form(None, description="Optional existing session ID to append to"),
):
    """
    Ingests 1 or more images into a session, profiles them, and determines the scene configuration.
    """
    session = session_manager.get_or_create_session(session_id)
    active_session_id = session.session_id

    for file in files:
        image_uuid = uuid.uuid4().hex[:8]
        safe_filename = f"{image_uuid}_{file.filename}"
        temp_file_path = session.session_dir / safe_filename

        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Validate
            validation_result = UniversalImageValidator.validate(temp_file_path)
            if not validation_result.is_valid:
                # If an image fails validation, we still report errors gracefully
                continue

            # Extract metadata
            metadata = UniversalMetadataExtractor.extract(
                file_path=temp_file_path,
                category=validation_result.category,
                image_id=image_uuid,
                compute_stats=True,
            )

            # Register in session
            session_manager.add_image(
                session_id=active_session_id,
                file_path=temp_file_path,
                metadata=metadata,
            )

        finally:
            await file.close()

    # Get all active images in this session and classify the relationship
    session_images = session_manager.get_images(active_session_id)
    classification = SceneClassifier.classify(session_images, active_session_id)

    return SessionStateResponse(
        session_id=active_session_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        image_count=len(session_images),
        classification=classification,
    )

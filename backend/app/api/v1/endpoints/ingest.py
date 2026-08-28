import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.metadata_schema import (
    InspectResponse,
    ValidationResult,
    ImageCategory,
)
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor

router = APIRouter()


@router.post(
    "/inspect",
    response_model=InspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect and profile an image (JPG/PNG or GeoTIFF)",
    description=(
        "Uploads an image (JPG/PNG visual photo or GeoTIFF satellite raster), "
        "performs structural validation, determines sensor modality, and returns structured metadata."
    ),
)
async def inspect_image(file: UploadFile = File(...)):
    """
    Dual-path image ingestion endpoint:
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
            message=(
                f"Successfully processed {validation_result.category.value.replace('_', ' ')} image."
            ),
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

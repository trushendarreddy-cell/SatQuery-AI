from pathlib import Path
from typing import Union
from PIL import Image, UnidentifiedImageError
import rasterio
from rasterio.errors import RasterioIOError, CRSError

from app.schemas.metadata_schema import ValidationResult, ImageCategory


class UniversalImageValidator:
    """Validates both Visual Images (JPG/PNG) and Geospatial Rasters (GeoTIFF/COG)."""

    VISUAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    GEOTIFF_EXTENSIONS = {".tif", ".tiff"}

    @classmethod
    def validate(cls, file_path: Union[str, Path]) -> ValidationResult:
        """
        Detects format and validates structural integrity and readability.
        
        Routing:
        1. GeoTIFF (.tif, .tiff): Validates CRS, affine transform, band count, dimensions via Rasterio.
           - If TIFF is valid but lacks CRS, flags as VISUAL_STANDARD with a clear warning.
        2. Visual Standard (.jpg, .png, etc.): Validates readability, dimensions, and channels via Pillow.
        """
        path = Path(file_path)
        errors = []
        warnings = []

        # 1. Existence and size check
        if not path.exists():
            return ValidationResult(
                is_valid=False,
                category=ImageCategory.VISUAL_STANDARD,
                errors=[f"File does not exist at path: {path}"],
                warnings=[],
            )

        if path.stat().st_size == 0:
            return ValidationResult(
                is_valid=False,
                category=ImageCategory.VISUAL_STANDARD,
                errors=["Uploaded file is empty (0 bytes)."],
                warnings=[],
            )

        ext = path.suffix.lower()

        # 2. Path B: GeoTIFF Inspection
        if ext in cls.GEOTIFF_EXTENSIONS:
            return cls._validate_geotiff(path)

        # 3. Path A: Visual Image Inspection (JPG/PNG/BMP)
        if ext in cls.VISUAL_EXTENSIONS:
            return cls._validate_visual_image(path)

        # 4. Unknown extension fallback - attempt rasterio, then Pillow
        try:
            return cls._validate_geotiff(path)
        except Exception:
            try:
                return cls._validate_visual_image(path)
            except Exception:
                return ValidationResult(
                    is_valid=False,
                    category=ImageCategory.VISUAL_STANDARD,
                    errors=[f"Unsupported or unrecognized image format: '{ext}'"],
                    warnings=[],
                )

    @classmethod
    def _validate_geotiff(cls, path: Path) -> ValidationResult:
        """Performs strict geospatial GeoTIFF validation."""
        errors = []
        warnings = []

        try:
            with rasterio.open(path) as src:
                if src.width <= 0 or src.height <= 0:
                    errors.append(f"Invalid raster dimensions: {src.width}x{src.height}.")

                if src.count <= 0:
                    errors.append("Raster contains 0 bands. At least 1 band is required.")

                # CRS check determines whether it is true GeoTIFF or unreferenced TIFF
                if not src.crs:
                    # Non-fatal for visual inspection, but cannot be used for geospatial processing
                    warnings.append(
                        "TIFF file lacks embedded Coordinate Reference System (CRS). Fallback to standard visual path."
                    )
                    return ValidationResult(
                        is_valid=True,
                        category=ImageCategory.VISUAL_STANDARD,
                        errors=[],
                        warnings=warnings,
                    )

                # Validate affine geotransform
                transform = src.transform
                if transform is None or (transform.a == 0 and transform.e == 0):
                    errors.append("GeoTIFF is missing valid spatial geotransform / resolution.")

                is_valid = len(errors) == 0
                return ValidationResult(
                    is_valid=is_valid,
                    category=ImageCategory.GEOSPATIAL_GEOTIFF if is_valid else ImageCategory.VISUAL_STANDARD,
                    errors=errors,
                    warnings=warnings,
                )

        except RasterioIOError as io_err:
            errors.append(f"Corrupted or unreadable TIFF file: {str(io_err)}")
        except CRSError as crs_err:
            errors.append(f"Invalid CRS definition: {str(crs_err)}")
        except Exception as exc:
            errors.append(f"Unexpected error while opening raster: {str(exc)}")

        return ValidationResult(
            is_valid=False,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def _validate_visual_image(cls, path: Path) -> ValidationResult:
        """Performs visual image validation using Pillow."""
        errors = []
        warnings = []

        try:
            with Image.open(path) as img:
                img.verify()  # Verifies file integrity without decoding full raster

            # Re-open after verify to inspect dimensions & mode
            with Image.open(path) as img:
                w, h = img.size
                if w <= 0 or h <= 0:
                    errors.append(f"Invalid image dimensions: {w}x{h}.")

                if img.mode not in ["RGB", "RGBA", "L", "P", "CMYK"]:
                    warnings.append(f"Non-standard color mode detected: '{img.mode}'.")

            is_valid = len(errors) == 0
            return ValidationResult(
                is_valid=is_valid,
                category=ImageCategory.VISUAL_STANDARD,
                errors=errors,
                warnings=warnings,
            )

        except (UnidentifiedImageError, IOError, SyntaxError) as img_err:
            errors.append(f"Corrupted or unreadable visual image: {str(img_err)}")
        except Exception as exc:
            errors.append(f"Unexpected error during visual validation: {str(exc)}")

        return ValidationResult(
            is_valid=False,
            category=ImageCategory.VISUAL_STANDARD,
            errors=errors,
            warnings=warnings,
        )

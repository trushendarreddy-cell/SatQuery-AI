from app.pipeline.validator import UniversalImageValidator
from app.schemas.metadata_schema import ImageCategory


def test_validator_valid_geotiff(valid_geotiff_path):
    """Test that a valid GeoTIFF is classified as GEOSPATIAL_GEOTIFF."""
    result = UniversalImageValidator.validate(valid_geotiff_path)
    assert result.is_valid is True
    assert result.category == ImageCategory.GEOSPATIAL_GEOTIFF
    assert len(result.errors) == 0


def test_validator_valid_jpeg(valid_jpg_path):
    """Test that a valid JPEG is classified as VISUAL_STANDARD."""
    result = UniversalImageValidator.validate(valid_jpg_path)
    assert result.is_valid is True
    assert result.category == ImageCategory.VISUAL_STANDARD
    assert len(result.errors) == 0


def test_validator_valid_png(valid_png_path):
    """Test that a valid PNG is classified as VISUAL_STANDARD."""
    result = UniversalImageValidator.validate(valid_png_path)
    assert result.is_valid is True
    assert result.category == ImageCategory.VISUAL_STANDARD
    assert len(result.errors) == 0


def test_validator_tiff_without_crs(invalid_geotiff_no_crs):
    """Test that a TIFF missing CRS gracefully falls back to VISUAL_STANDARD with a warning."""
    result = UniversalImageValidator.validate(invalid_geotiff_no_crs)
    assert result.is_valid is True
    assert result.category == ImageCategory.VISUAL_STANDARD
    assert any("TIFF file lacks embedded Coordinate Reference System" in w for w in result.warnings)


def test_validator_nonexistent_file():
    """Test that a nonexistent file fails validation."""
    result = UniversalImageValidator.validate("non_existent_file.jpg")
    assert result.is_valid is False
    assert any("does not exist" in err for err in result.errors)


def test_validator_corrupted_file(corrupted_file_path):
    """Test that a corrupted file fails validation gracefully."""
    result = UniversalImageValidator.validate(corrupted_file_path)
    assert result.is_valid is False
    assert len(result.errors) > 0

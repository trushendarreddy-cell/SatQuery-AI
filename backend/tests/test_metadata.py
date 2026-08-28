from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.metadata_schema import ImageCategory, SensorModality


def test_metadata_extraction_geotiff(valid_geotiff_path):
    """Test full metadata extraction for GeoTIFF including acquisition date, CRS, bounds, resolution, and band stats."""
    meta = UniversalMetadataExtractor.extract(
        valid_geotiff_path, category=ImageCategory.GEOSPATIAL_GEOTIFF, compute_stats=True
    )
    assert meta.category == ImageCategory.GEOSPATIAL_GEOTIFF
    assert meta.has_geospatial_metadata is True
    assert meta.width == 10
    assert meta.height == 10
    assert meta.channels == 2
    assert meta.geospatial is not None
    assert meta.visual is None
    assert meta.geospatial.crs is not None
    assert meta.geospatial.bounds_native.min_x == 500000.0
    assert meta.geospatial.bounds_wgs84 is not None
    assert meta.geospatial.resolution.x_resolution == 10.0
    assert len(meta.geospatial.bands) == 2
    assert meta.geospatial.bands[0].data_type == "uint16"
    assert meta.acquisition_date == "2026:05:14 10:30:00"
    assert meta.geospatial.acquisition_date == "2026:05:14 10:30:00"


def test_metadata_extraction_jpeg(valid_jpg_path):
    """Test metadata extraction for standard JPEG: classified as visual_standard with NO fabricated geospatial data."""
    meta = UniversalMetadataExtractor.extract(
        valid_jpg_path, category=ImageCategory.VISUAL_STANDARD
    )
    assert meta.category == ImageCategory.VISUAL_STANDARD
    assert meta.has_geospatial_metadata is False
    # Verified: Must NOT automatically label arbitrary RGB JPG as satellite optical imagery
    assert meta.modality == SensorModality.VISUAL_STANDARD
    assert meta.width == 64
    assert meta.height == 64
    assert meta.channels == 3
    assert meta.geospatial is None  # Strictly null / never fabricated
    assert meta.visual is not None
    assert meta.visual.color_mode == "RGB"
    assert meta.visual.channel_count == 3


def test_metadata_extraction_png(valid_png_path):
    """Test metadata extraction for standard PNG: classified as visual_standard with NO fabricated geospatial data."""
    meta = UniversalMetadataExtractor.extract(
        valid_png_path, category=ImageCategory.VISUAL_STANDARD
    )
    assert meta.category == ImageCategory.VISUAL_STANDARD
    assert meta.has_geospatial_metadata is False
    assert meta.modality == SensorModality.VISUAL_STANDARD
    assert meta.width == 32
    assert meta.height == 32
    assert meta.channels == 4
    assert meta.geospatial is None  # Strictly null / never fabricated
    assert meta.visual is not None
    assert meta.visual.color_mode == "RGBA"

import pytest
import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_origin
from pathlib import Path


@pytest.fixture(scope="session")
def valid_geotiff_path(tmp_path_factory):
    """Generates a small valid GeoTIFF with CRS, geotransform, and acquisition date tag."""
    fn = tmp_path_factory.mktemp("data") / "sample_valid.tif"
    
    width, height = 10, 10
    transform = from_origin(500000, 3000000, 10, 10)  # 10m pixel size
    crs = "EPSG:32643"
    
    band1 = np.arange(100, dtype=np.uint16).reshape((10, 10))
    band2 = (band1 * 2).astype(np.uint16)
    
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=2,
        dtype=rasterio.uint16,
        crs=crs,
        transform=transform,
        nodata=0,
    ) as dst:
        dst.write(band1, 1)
        dst.write(band2, 2)
        dst.update_tags(TIFFTAG_DATETIME="2026:05:14 10:30:00")
        
    return fn


@pytest.fixture(scope="session")
def valid_jpg_path(tmp_path_factory):
    """Generates a standard valid RGB JPEG image."""
    fn = tmp_path_factory.mktemp("data") / "sample_photo.jpg"
    img = Image.new("RGB", (64, 64), color=(73, 109, 137))
    img.save(fn, format="JPEG")
    return fn


@pytest.fixture(scope="session")
def valid_png_path(tmp_path_factory):
    """Generates a standard valid RGBA PNG image."""
    fn = tmp_path_factory.mktemp("data") / "sample_graphic.png"
    img = Image.new("RGBA", (32, 32), color=(255, 0, 0, 128))
    img.save(fn, format="PNG")
    return fn


@pytest.fixture(scope="session")
def invalid_geotiff_no_crs(tmp_path_factory):
    """Generates a TIFF lacking CRS (falls back to visual standard)."""
    fn = tmp_path_factory.mktemp("data") / "sample_no_crs.tif"
    
    width, height = 10, 10
    band = np.ones((10, 10), dtype=np.uint8)
    
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=rasterio.uint8,
    ) as dst:
        dst.write(band, 1)
        
    return fn


@pytest.fixture(scope="session")
def corrupted_file_path(tmp_path_factory):
    """Generates a corrupted binary non-image file."""
    fn = tmp_path_factory.mktemp("data") / "corrupted.jpg"
    fn.write_bytes(b"Corrupted non-image content bytes...")
    return fn

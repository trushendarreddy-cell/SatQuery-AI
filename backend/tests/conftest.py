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
def geotiff_date1_path(tmp_path_factory):
    """Generates a 4-band optical GeoTIFF acquired on May 1, 2024."""
    fn = tmp_path_factory.mktemp("data") / "scene_2024_05_01.tif"
    width, height = 10, 10
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    data = np.ones((4, height, width), dtype=np.uint16) * 1000
    
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=4,
        dtype=rasterio.uint16,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)
        dst.update_tags(TIFFTAG_DATETIME="2024:05:01 10:00:00")
    return fn


@pytest.fixture(scope="session")
def geotiff_date2_path(tmp_path_factory):
    """Generates a 4-band optical GeoTIFF acquired on Nov 1, 2024."""
    fn = tmp_path_factory.mktemp("data") / "scene_2024_11_01.tif"
    width, height = 10, 10
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    data = np.ones((4, height, width), dtype=np.uint16) * 1500
    
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=4,
        dtype=rasterio.uint16,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)
        dst.update_tags(TIFFTAG_DATETIME="2024:11:01 10:00:00")
    return fn


@pytest.fixture(scope="session")
def sar_geotiff_path(tmp_path_factory):
    """Generates a 1-band SAR Radar GeoTIFF (Sentinel-1 VV polarization)."""
    fn = tmp_path_factory.mktemp("data") / "sar_sentinel1_vv.tif"
    width, height = 10, 10
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    data = np.ones((1, height, width), dtype=np.float32) * 0.15
    
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=rasterio.float32,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)
        dst.update_tags(
            POLARIZATION="VV",
            SENSOR="SENTINEL-1",
            TIFFTAG_DATETIME="2024:05:01 10:00:00",
        )
    return fn


@pytest.fixture(scope="session")
def valid_jpg_path(tmp_path_factory):
    """Generates a standard valid RGB JPEG image."""
    fn = tmp_path_factory.mktemp("data") / "sample_photo.jpg"
    img = Image.new("RGB", (64, 64), color=(73, 109, 137))
    img.save(fn, format="JPEG")
    return fn


@pytest.fixture(scope="session")
def valid_jpg_path_2(tmp_path_factory):
    """Generates a second valid RGB JPEG image."""
    fn = tmp_path_factory.mktemp("data") / "sample_photo_2.jpg"
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
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

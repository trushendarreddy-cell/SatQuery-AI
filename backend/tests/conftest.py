import pytest
import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from pathlib import Path


@pytest.fixture(scope="session")
def valid_geotiff_path(tmp_path_factory):
    """Generates a small valid GeoTIFF with CRS, geotransform, and acquisition date tag (UTM 43N)."""
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
    """Generates a 4-band optical GeoTIFF acquired on May 1, 2024 (UTM 43N)."""
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
    """Generates a 4-band optical GeoTIFF acquired on Nov 1, 2024 with 50% spatial offset."""
    fn = tmp_path_factory.mktemp("data") / "scene_2024_11_01.tif"
    width, height = 10, 10
    # Shifted by 50m to test partial spatial overlap
    transform = from_origin(500050, 3000050, 10, 10)
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
def geotiff_diff_crs_path(tmp_path_factory, valid_geotiff_path):
    """Generates a GeoTIFF covering the same region as valid_geotiff_path but defined in EPSG:4326."""
    fn = tmp_path_factory.mktemp("data") / "scene_epsg4326.tif"
    with rasterio.open(valid_geotiff_path) as ref:
        wgs_bounds = transform_bounds(ref.crs, "EPSG:4326", *ref.bounds)
        
    min_lon, min_lat, max_lon, max_lat = wgs_bounds
    width, height = 10, 10
    res_x = (max_lon - min_lon) / width
    res_y = (max_lat - min_lat) / height
    transform = from_origin(min_lon, max_lat, res_x, res_y)
    
    data = np.ones((2, height, width), dtype=np.uint16) * 500
    with rasterio.open(
        fn,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=2,
        dtype=rasterio.uint16,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data)
        dst.update_tags(TIFFTAG_DATETIME="2024:06:01 12:00:00")
    return fn


@pytest.fixture(scope="session")
def geotiff_no_overlap_path(tmp_path_factory):
    """Generates a GeoTIFF located in New York (UTM 18N), completely disjoint from India scenes."""
    fn = tmp_path_factory.mktemp("data") / "scene_new_york.tif"
    width, height = 10, 10
    transform = from_origin(580000, 4500000, 10, 10)
    crs = "EPSG:32618"
    data = np.ones((2, height, width), dtype=np.uint16) * 800
    
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
    ) as dst:
        dst.write(data)
        dst.update_tags(TIFFTAG_DATETIME="2024:05:01 10:00:00")
    return fn


@pytest.fixture(scope="session")
def geotiff_30m_res_path(tmp_path_factory):
    """Generates a GeoTIFF with 30m resolution covering same region."""
    fn = tmp_path_factory.mktemp("data") / "scene_30m.tif"
    width, height = 5, 5
    transform = from_origin(500000, 3000000, 30, 30)  # 30m pixel size
    crs = "EPSG:32643"
    data = np.ones((2, height, width), dtype=np.uint16) * 1200
    
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
    ) as dst:
        dst.write(data)
        dst.update_tags(TIFFTAG_DATETIME="2024:05:01 10:00:00")
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
def geotiff_no_date_path(tmp_path_factory):
    """Georeferenced GeoTIFF with no acquisition timestamp tags."""
    fn = tmp_path_factory.mktemp("data") / "scene_no_date.tif"
    transform = from_origin(500000, 3000000, 10, 10)
    data = np.ones((2, 10, 10), dtype=np.uint16) * 400
    with rasterio.open(
        fn, "w", driver="GTiff", height=10, width=10, count=2,
        dtype=rasterio.uint16, crs="EPSG:32643", transform=transform, nodata=0,
    ) as dst:
        dst.write(data)
    return fn


@pytest.fixture(scope="session")
def geotiff_scl_path(tmp_path_factory):
    """Optical scene plus Sentinel-2 SCL band (3=shadow, 8=cloud, 4=vegetation)."""
    fn = tmp_path_factory.mktemp("data") / "scene_with_scl.tif"
    transform = from_origin(500000, 3000000, 10, 10)
    optical = np.ones((3, 10, 10), dtype=np.uint16) * 800
    scl = np.full((10, 10), 4, dtype=np.uint8)
    scl[0:2, 0:5] = 8
    scl[8:10, 8:10] = 3
    with rasterio.open(
        fn, "w", driver="GTiff", height=10, width=10, count=4,
        dtype=rasterio.uint16, crs="EPSG:32643", transform=transform, nodata=0,
    ) as dst:
        dst.write(optical[0], 1)
        dst.write(optical[1], 2)
        dst.write(optical[2], 3)
        dst.write(scl.astype(np.uint16), 4)
        dst.set_band_description(1, "B2")
        dst.set_band_description(2, "B3")
        dst.set_band_description(3, "B4")
        dst.set_band_description(4, "SCL")
        dst.update_tags(TIFFTAG_DATETIME="2024:05:01 10:00:00")
    return fn


@pytest.fixture(scope="session")
def geotiff_qa_pixel_path(tmp_path_factory):
    """Single-band Landsat-style QA_PIXEL with cloud (bit 3) and shadow (bit 4)."""
    fn = tmp_path_factory.mktemp("data") / "qa_pixel.tif"
    transform = from_origin(500000, 3000000, 10, 10)
    qa = np.zeros((10, 10), dtype=np.uint16)
    qa[0:3, 0:3] = np.uint16(1 << 3)
    qa[5:7, 5:7] = np.uint16(1 << 4)
    with rasterio.open(
        fn, "w", driver="GTiff", height=10, width=10, count=1,
        dtype=rasterio.uint16, crs="EPSG:32643", transform=transform,
    ) as dst:
        dst.write(qa, 1)
        dst.set_band_description(1, "QA_PIXEL")
    return fn


@pytest.fixture(scope="session")
def geotiff_binary_mask_path(tmp_path_factory):
    """Binary mask with a 4x4 block of valid pixels (1) and the rest 0."""
    fn = tmp_path_factory.mktemp("data") / "binary_mask.tif"
    transform = from_origin(500000, 3000000, 10, 10)
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0:4, 0:4] = 1
    with rasterio.open(
        fn, "w", driver="GTiff", height=10, width=10, count=1,
        dtype=rasterio.uint8, crs="EPSG:32643", transform=transform, nodata=255,
    ) as dst:
        dst.write(mask, 1)
        dst.set_band_description(1, "change_mask")
        dst.update_tags(MASK_TYPE="binary")
    return fn


@pytest.fixture(scope="session")
def geotiff_empty_mask_path(tmp_path_factory):
    """Georeferenced mask with no valid pixels."""
    fn = tmp_path_factory.mktemp("data") / "empty_mask.tif"
    transform = from_origin(500000, 3000000, 10, 10)
    mask = np.zeros((10, 10), dtype=np.uint8)
    with rasterio.open(
        fn, "w", driver="GTiff", height=10, width=10, count=1,
        dtype=rasterio.uint8, crs="EPSG:32643", transform=transform, nodata=255,
    ) as dst:
        dst.write(mask, 1)
        dst.set_band_description(1, "change_mask")
    return fn


@pytest.fixture(scope="session")
def corrupted_file_path(tmp_path_factory):
    """Generates a corrupted binary non-image file."""
    fn = tmp_path_factory.mktemp("data") / "corrupted.jpg"
    fn.write_bytes(b"Corrupted non-image content bytes...")
    return fn

import pytest
import numpy as np
from pathlib import Path
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.change_detection import run_change_detection
from app.schemas.change_detection_schema import ChangeDetectionRequest, ChangeDetectionMethod
import rasterio
from rasterio.transform import from_origin


def _setup(session_id, paths):
    session_manager.clear_all()
    session_manager.get_or_create_session(session_id)
    ids = []
    for p in paths:
        val = UniversalImageValidator.validate(p)
        meta = UniversalMetadataExtractor.extract(p, category=val.category)
        session_manager.add_image(session_id, p, meta)
        ids.append(meta.image_id)
    return ids


def test_rejects_visual_jpg(valid_jpg_path):
    """Test change detection rejects visual JPG images."""
    ids = _setup("cd_vis_jpg", [valid_jpg_path])
    payload = ChangeDetectionRequest(
        session_id="cd_vis_jpg",
        image_id_1=ids[0],
        image_id_2=ids[0],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "unreferenced" in res.message.lower() or "geospatial" in res.message.lower()


def test_rejects_visual_png(valid_png_path):
    """Test change detection rejects visual PNG images."""
    ids = _setup("cd_vis_png", [valid_png_path])
    payload = ChangeDetectionRequest(
        session_id="cd_vis_png",
        image_id_1=ids[0],
        image_id_2=ids[0],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "unreferenced" in res.message.lower() or "geospatial" in res.message.lower()


def test_invalid_session():
    payload = ChangeDetectionRequest(
        session_id="nonexistent",
        image_id_1="a",
        image_id_2="b",
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "session" in res.message.lower()


def test_no_spatial_overlap(geotiff_date1_path, geotiff_no_overlap_path):
    """Test change detection fails when scenes don't overlap."""
    ids = _setup("cd_no_overlap", [geotiff_date1_path, geotiff_no_overlap_path])
    payload = ChangeDetectionRequest(
        session_id="cd_no_overlap",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "no spatial overlap" in res.message.lower() or "empty" in res.message.lower()


def test_obvious_change(tmp_path):
    """Test change detection detects obvious spectral change."""
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    arr1 = np.ones((10, 10), dtype=np.uint16) * 100
    arr2 = np.ones((10, 10), dtype=np.uint16) * 500

    p1 = tmp_path / "scene_a.tif"
    p2 = tmp_path / "scene_b.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr1, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr2, 1)

    ids = _setup("cd_obvious", [p1, p2])
    payload = ChangeDetectionRequest(
        session_id="cd_obvious",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is True
    assert res.changed_pixel_count == 100
    assert res.unchanged_pixel_count == 0
    assert res.valid_pixel_count == 100
    assert res.change_percentage == 100.0
    assert "PIXEL/SPECTRAL CHANGE" in res.message


def test_no_change(tmp_path):
    """Test change detection reports no change for identical scenes."""
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    arr = np.ones((10, 10), dtype=np.uint16) * 300

    p1 = tmp_path / "scene_same_a.tif"
    p2 = tmp_path / "scene_same_b.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr, 1)

    ids = _setup("cd_nochange", [p1, p2])
    payload = ChangeDetectionRequest(
        session_id="cd_nochange",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is True
    assert res.changed_pixel_count == 0
    assert res.unchanged_pixel_count == 100
    assert res.valid_pixel_count == 100
    assert res.change_percentage == 0.0


def test_nodata_handling(tmp_path):
    """Test change detection correctly excludes NoData pixels."""
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    arr1 = np.ones((10, 10), dtype=np.float32) * 100
    arr2 = np.ones((10, 10), dtype=np.float32) * 500
    arr1[0, 0] = -9999
    arr2[5, 5] = -9999

    p1 = tmp_path / "scene_nodata1.tif"
    p2 = tmp_path / "scene_nodata2.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform, nodata=-9999) as dst:
        dst.write(arr1, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform, nodata=-9999) as dst:
        dst.write(arr2, 1)

    ids = _setup("cd_nodata", [p1, p2])
    payload = ChangeDetectionRequest(
        session_id="cd_nodata",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is True
    assert res.valid_pixel_count == 98
    assert res.changed_pixel_count == 98
    assert res.unchanged_pixel_count == 0


def test_crs_mismatch(tmp_path):
    """Test change detection fails on CRS mismatch."""
    transform1 = from_origin(500000, 3000000, 10, 10)
    transform2 = from_origin(0, 0, 0.001, 0.001)
    arr = np.ones((10, 10), dtype=np.uint16) * 100

    p1 = tmp_path / "scene_crs1.tif"
    p2 = tmp_path / "scene_crs2.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs="EPSG:32643", transform=transform1) as dst:
        dst.write(arr, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs="EPSG:4326", transform=transform2) as dst:
        dst.write(arr, 1)

    ids = _setup("cd_crs_mismatch", [p1, p2])
    payload = ChangeDetectionRequest(
        session_id="cd_crs_mismatch",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "mismatch" in res.message.lower() or "no spatial overlap" in res.message.lower() or "empty" in res.message.lower()


def test_artifact_creation_and_metadata(tmp_path):
    """Test change detection creates a valid GeoTIFF artifact with preserved metadata."""
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    arr1 = np.ones((10, 10), dtype=np.uint16) * 100
    arr2 = np.ones((10, 10), dtype=np.uint16) * 500

    p1 = tmp_path / "scene_artifact_a.tif"
    p2 = tmp_path / "scene_artifact_b.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr1, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.uint16, crs=crs, transform=transform) as dst:
        dst.write(arr2, 1)

    ids = _setup("cd_artifact", [p1, p2])
    payload = ChangeDetectionRequest(
        session_id="cd_artifact",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is True
    assert res.change_mask_image_id != ""
    assert res.artifact_filename.endswith(".tif")

    session = session_manager.get_session("cd_artifact")
    mask_path = session.session_dir / res.artifact_filename
    assert mask_path.exists()

    with rasterio.open(mask_path) as mask_ds:
        assert mask_ds.crs.to_string() == crs
        assert mask_ds.width == 10
        assert mask_ds.height == 10
        assert mask_ds.count == 1
        assert mask_ds.dtypes[0] == rasterio.uint8
        data = mask_ds.read(1)
        assert int((data == 1).sum()) == 100


def test_threshold_behavior(tmp_path):
    """Test threshold controls change detection sensitivity."""
    transform = from_origin(500000, 3000000, 10, 10)
    crs = "EPSG:32643"
    arr1 = np.ones((10, 10), dtype=np.float32) * 0.4
    arr2 = np.ones((10, 10), dtype=np.float32) * 0.6

    p1 = tmp_path / "scene_thresh1.tif"
    p2 = tmp_path / "scene_thresh2.tif"
    with rasterio.open(p1, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(arr1, 1)
    with rasterio.open(p2, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(arr2, 1)

    ids = _setup("cd_threshold", [p1, p2])
    payload_high = ChangeDetectionRequest(
        session_id="cd_threshold",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.5,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res_high = run_change_detection(payload_high)
    assert res_high.success is True
    assert res_high.changed_pixel_count == 0

    payload_low = ChangeDetectionRequest(
        session_id="cd_threshold",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.01,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res_low = run_change_detection(payload_low)
    assert res_low.success is True
    assert res_low.changed_pixel_count == 100

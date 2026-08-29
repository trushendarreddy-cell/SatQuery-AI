import pytest
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.analysis import compute_spectral_index
from app.schemas.analysis_schema import SpectralIndexType

client = TestClient(app)


def _upload(path: Path) -> tuple[str, str]:
    with open(path, "rb") as f:
        res = client.post(
            "/api/v1/ingest/upload",
            files=[("files", (path.name, f, "image/tiff"))],
        )
    assert res.status_code == 200
    data = res.json()
    return data["session_id"], data["classification"]["image_ids"][0]


def test_api_spectral_index_ndvi(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index with NDVI."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndvi",
            "red_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["index_type"] == "ndvi"
    assert data["index_image_id"] != ""
    assert data["artifact_filename"].endswith(".tif")
    assert data["width"] == 10
    assert data["height"] == 10
    assert data["band_count"] == 1
    assert data["crs"] == "EPSG:32643"
    assert data["red_band"] == 1
    assert data["nir_band"] == 2
    assert data["valid_pixel_count"] == 100
    assert data["nodata_pixel_count"] == 0
    assert data["min_value"] == 0.0
    assert data["max_value"] == 0.0
    assert data["mean_value"] == 0.0
    assert "NDVI" in data["message"]


def test_api_spectral_index_rejects_jpg(valid_jpg_path):
    """Test POST /api/v1/analysis/spectral-index rejects visual JPG."""
    sid, img_id = _upload(valid_jpg_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndvi",
            "red_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "geospatial" in data["message"].lower() or "visual" in data["message"].lower()


def test_api_spectral_index_invalid_red_band(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index rejects out-of-range red band."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndvi",
            "red_band": 99,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "red band" in data["message"].lower() or "out of range" in data["message"].lower()


def test_api_spectral_index_invalid_nir_band(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index rejects out-of-range NIR band."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndvi",
            "red_band": 1,
            "nir_band": 99,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "nir band" in data["message"].lower() or "out of range" in data["message"].lower()


def test_api_spectral_index_missing_session():
    """Test POST /api/v1/analysis/spectral-index with invalid session."""
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": "nonexistent_session_123",
            "image_id": "img1",
            "index_type": "ndvi",
            "red_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "session" in data["message"].lower()


def test_spectral_index_unit_ndvi_values():
    """Unit test: NDVI values are correct for known red/NIR arrays."""
    from app.geospatial.spectral_index import compute_ndvi
    import rasterio
    from rasterio.transform import from_origin

    red_arr = np.full((5, 5), 100, dtype=np.float32)
    nir_arr = np.full((5, 5), 500, dtype=np.float32)

    transform = from_origin(0, 0, 1, 1)
    crs = "EPSG:32643"

    red_path = Path("test_red.tif")
    nir_path = Path("test_nir.tif")
    out_path = Path("test_ndvi.tif")

    with rasterio.open(red_path, "w", driver="GTiff", height=5, width=5, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform, nodata=-9999) as dst:
        dst.write(red_arr, 1)
    with rasterio.open(nir_path, "w", driver="GTiff", height=5, width=5, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform, nodata=-9999) as dst:
        dst.write(nir_arr, 1)

    try:
        result = compute_ndvi(red_path, nir_path, out_path, red_band=1, nir_band=1)
        assert result["valid_pixel_count"] == 25
        assert result["nodata_pixel_count"] == 0
        expected = (500 - 100) / (500 + 100)
        assert result["min_value"] == pytest.approx(expected)
        assert result["max_value"] == pytest.approx(expected)
        assert result["mean_value"] == pytest.approx(expected)
    finally:
        for p in (red_path, nir_path, out_path):
            if p.exists():
                p.unlink()


def test_spectral_index_divide_by_zero_safe():
    """Unit test: NDVI handles zero denominator without crashing."""
    from app.geospatial.spectral_index import compute_ndvi
    import rasterio
    from rasterio.transform import from_origin

    red_arr = np.zeros((3, 3), dtype=np.float32)
    nir_arr = np.zeros((3, 3), dtype=np.float32)
    nir_arr[1, 1] = 1

    transform = from_origin(0, 0, 1, 1)
    crs = "EPSG:32643"

    red_path = Path("test_red2.tif")
    nir_path = Path("test_nir2.tif")
    out_path = Path("test_ndvi2.tif")

    with rasterio.open(red_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(red_arr, 1)
    with rasterio.open(nir_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(nir_arr, 1)

    try:
        result = compute_ndvi(red_path, nir_path, out_path, red_band=1, nir_band=1)
        assert result["valid_pixel_count"] == 9
        assert result["min_value"] == pytest.approx(1.0)
        assert result["max_value"] == pytest.approx(1.0)
    finally:
        for p in (red_path, nir_path, out_path):
            if p.exists():
                p.unlink()


def test_spectral_index_rejects_visual_jpg(valid_jpg_path):
    """Unit test: spectral index rejects visual JPG."""
    session_manager.clear_all()
    sid = "cd_vis_jpg"
    session_manager.get_or_create_session(sid)
    val = UniversalImageValidator.validate(valid_jpg_path)
    meta = UniversalMetadataExtractor.extract(valid_jpg_path, category=val.category)
    session_manager.add_image(sid, valid_jpg_path, meta)

    res = compute_spectral_index(sid, meta.image_id, SpectralIndexType.NDVI, 1, 2)
    assert res.success is False
    assert "geospatial" in res.message.lower() or "visual" in res.message.lower()


def test_spectral_index_rejects_no_crs(invalid_geotiff_no_crs):
    """Unit test: spectral index rejects raster without CRS."""
    session_manager.clear_all()
    sid = "cd_no_crs"
    session_manager.get_or_create_session(sid)
    val = UniversalImageValidator.validate(invalid_geotiff_no_crs)
    meta = UniversalMetadataExtractor.extract(invalid_geotiff_no_crs, category=val.category)
    session_manager.add_image(sid, invalid_geotiff_no_crs, meta)

    res = compute_spectral_index(sid, meta.image_id, SpectralIndexType.NDVI, 1, 2)
    assert res.success is False
    assert "georeferenced" in res.message.lower() or "crs" in res.message.lower()


def test_spectral_index_invalid_session():
    """Unit test: spectral index handles invalid session."""
    res = compute_spectral_index("nonexistent", "img1", SpectralIndexType.NDVI, 1, 2)
    assert res.success is False
    assert "session" in res.message.lower()


def test_spectral_index_crs_mismatch():
    """Unit test: compute_ndvi rejects rasters with different CRS."""
    from app.geospatial.spectral_index import compute_ndvi
    import rasterio
    from rasterio.transform import from_origin

    transform = from_origin(0, 0, 1, 1)
    red_path = Path("test_red_crs.tif")
    nir_path = Path("test_nir_crs.tif")
    out_path = Path("test_ndvi_crs.tif")

    with rasterio.open(red_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs="EPSG:32643", transform=transform) as dst:
        dst.write(np.ones((3, 3), dtype=np.float32), 1)
    with rasterio.open(nir_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs="EPSG:4326", transform=transform) as dst:
        dst.write(np.ones((3, 3), dtype=np.float32), 1)

    try:
        with pytest.raises(ValueError, match="mismatch"):
            compute_ndvi(red_path, nir_path, out_path, red_band=1, nir_band=1)
    finally:
        for p in (red_path, nir_path, out_path):
            if p.exists():
                p.unlink()


def test_spectral_index_nodata_handling(geotiff_date1_path):
    """Unit test: NDVI respects NoData pixels."""
    session_manager.clear_all()
    sid = "cd_nodata"
    session_manager.get_or_create_session(sid)
    val = UniversalImageValidator.validate(geotiff_date1_path)
    meta = UniversalMetadataExtractor.extract(geotiff_date1_path, category=val.category)
    session_manager.add_image(sid, geotiff_date1_path, meta)

    res = compute_spectral_index(sid, meta.image_id, SpectralIndexType.NDVI, 1, 2)
    assert res.success is True
    assert res.valid_pixel_count >= 0
    assert res.nodata_pixel_count >= 0


def test_spectral_index_artifact_preserves_metadata(geotiff_date1_path):
    """Unit test: NDVI output preserves geospatial reference."""
    session_manager.clear_all()
    sid = "cd_meta"
    session_manager.get_or_create_session(sid)
    val = UniversalImageValidator.validate(geotiff_date1_path)
    meta = UniversalMetadataExtractor.extract(geotiff_date1_path, category=val.category)
    session_manager.add_image(sid, geotiff_date1_path, meta)

    res = compute_spectral_index(sid, meta.image_id, SpectralIndexType.NDVI, 1, 2)
    assert res.success is True
    assert res.crs == "EPSG:32643"
    assert len(res.transform) == 6
    assert res.width == 10
    assert res.height == 10


def test_api_spectral_index_evi(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index with EVI."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "evi",
            "red_band": 1,
            "nir_band": 2,
            "blue_band": 3,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["index_type"] == "evi"
    assert data["blue_band"] == 3
    assert data["artifact_filename"].endswith(".tif")


def test_api_spectral_index_ndwi(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index with NDWI."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndwi",
            "green_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["index_type"] == "ndwi"
    assert data["green_band"] == 1
    assert data["artifact_filename"].endswith(".tif")


def test_api_spectral_index_evi_missing_blue(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index rejects EVI without blue_band."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "evi",
            "red_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "blue_band" in data["message"].lower()


def test_api_spectral_index_ndwi_missing_green(geotiff_date1_path):
    """Test POST /api/v1/analysis/spectral-index rejects NDWI without green_band."""
    sid, img_id = _upload(geotiff_date1_path)
    res = client.post(
        "/api/v1/analysis/spectral-index",
        json={
            "session_id": sid,
            "image_id": img_id,
            "index_type": "ndwi",
            "red_band": 1,
            "nir_band": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "green_band" in data["message"].lower()


def test_spectral_index_unit_evi_values():
    """Unit test: EVI values are correct for known arrays."""
    from app.geospatial.spectral_index import compute_evi
    import rasterio
    from rasterio.transform import from_origin

    red = np.full((3, 3), 100, dtype=np.float32)
    nir = np.full((3, 3), 500, dtype=np.float32)
    blue = np.full((3, 3), 50, dtype=np.float32)

    transform = from_origin(0, 0, 1, 1)
    crs = "EPSG:32643"

    red_path = Path("test_evi_red.tif")
    nir_path = Path("test_evi_nir.tif")
    blue_path = Path("test_evi_blue.tif")
    out_path = Path("test_evi.tif")

    with rasterio.open(red_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(red, 1)
    with rasterio.open(nir_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(nir, 1)
    with rasterio.open(blue_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(blue, 1)

    try:
        result = compute_evi(red_path, nir_path, blue_path, out_path, red_band=1, nir_band=1, blue_band=1)
        expected = 2.5 * (500 - 100) / (500 + 6 * 100 - 7.5 * 50 + 1)
        assert result["valid_pixel_count"] == 9
        assert pytest.approx(result["min_value"]) == expected
        assert pytest.approx(result["max_value"]) == expected
        assert pytest.approx(result["mean_value"]) == expected
    finally:
        for p in (red_path, nir_path, blue_path, out_path):
            if p.exists():
                p.unlink()


def test_spectral_index_unit_ndwi_values():
    """Unit test: NDWI values are correct for known arrays."""
    from app.geospatial.spectral_index import compute_ndwi
    import rasterio
    from rasterio.transform import from_origin

    green = np.full((3, 3), 400, dtype=np.float32)
    nir = np.full((3, 3), 100, dtype=np.float32)

    transform = from_origin(0, 0, 1, 1)
    crs = "EPSG:32643"

    green_path = Path("test_ndwi_green.tif")
    nir_path = Path("test_ndwi_nir.tif")
    out_path = Path("test_ndwi.tif")

    with rasterio.open(green_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(green, 1)
    with rasterio.open(nir_path, "w", driver="GTiff", height=3, width=3, count=1,
                       dtype=rasterio.float32, crs=crs, transform=transform) as dst:
        dst.write(nir, 1)

    try:
        result = compute_ndwi(green_path, nir_path, out_path, green_band=1, nir_band=1)
        expected = (400 - 100) / (400 + 100)
        assert result["valid_pixel_count"] == 9
        assert pytest.approx(result["min_value"]) == expected
        assert pytest.approx(result["max_value"]) == expected
        assert pytest.approx(result["mean_value"]) == expected
    finally:
        for p in (green_path, nir_path, out_path):
            if p.exists():
                p.unlink()

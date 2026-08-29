from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _upload_test_pair(file1_path, file2_path):
    with open(file1_path, "rb") as f1, open(file2_path, "rb") as f2:
        res = client.post(
            "/api/v1/ingest/upload",
            files=[
                ("files", ("img1.tif", f1, "image/tiff")),
                ("files", ("img2.tif", f2, "image/tiff")),
            ],
        )
    assert res.status_code == 200
    data = res.json()
    return data["session_id"], data["classification"]["image_ids"]


def test_api_spatial_overlap(geotiff_date1_path, geotiff_date2_path):
    """Test POST /api/v1/spatial/overlap endpoint."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_date2_path)
    
    res = client.post(
        "/api/v1/spatial/overlap",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["overlap_exists"] is True
    assert data["intersection_geojson"] is not None


def test_api_spatial_compatibility(geotiff_date1_path, geotiff_date2_path):
    """Test POST /api/v1/spatial/compatibility endpoint."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_date2_path)
    
    res = client.post(
        "/api/v1/spatial/compatibility",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["compatible"] is True
    assert data["temporal"]["has_dates"] is True
    assert data["resolution"]["compatible"] is True


def test_api_spatial_align(valid_geotiff_path, geotiff_diff_crs_path):
    """Test POST /api/v1/spatial/align endpoint."""
    sid, img_ids = _upload_test_pair(valid_geotiff_path, geotiff_diff_crs_path)
    
    res = client.post(
        "/api/v1/spatial/align",
        json={
            "session_id": sid,
            "reference_image_id": img_ids[0],
            "target_image_id": img_ids[1],
            "resampling_method": "bilinear",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["aligned_image_id"] != ""
    assert data["width"] == 10
    assert data["height"] == 10
    assert data["aligned_metadata"] is not None


def test_api_spatial_clip(geotiff_date1_path, geotiff_date2_path):
    """Test POST /api/v1/spatial/clip endpoint JSON types and clipped pair."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_date2_path)

    res = client.post(
        "/api/v1/spatial/clip",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "resampling_method": "nearest",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert isinstance(data["success"], bool)
    assert isinstance(data["width"], int)
    assert isinstance(data["height"], int)
    assert isinstance(data["resolution"][0], float)
    assert data["width"] == 5
    assert data["height"] == 5
    assert data["clipped_image_id_1"] != ""
    assert data["clipped_image_id_2"] != ""
    assert data["clipped_metadata_1"] is not None
    assert data["intersection_bounds_wgs84"]["min_lon"] is not None

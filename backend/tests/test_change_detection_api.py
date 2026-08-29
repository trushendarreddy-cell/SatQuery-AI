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


def test_api_change_detection_rejects_jpg(valid_jpg_path, valid_jpg_path_2):
    """Test POST /api/v1/analysis/change-detection rejects visual images."""
    sid, img_ids = _upload_test_pair(valid_jpg_path, valid_jpg_path_2)

    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "threshold": 0.1,
            "threshold_method": "relative_normalized",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "unreferenced" in data["message"].lower() or "geospatial" in data["message"].lower()


def test_api_change_detection_rejects_png(valid_png_path, valid_jpg_path):
    """Test POST /api/v1/analysis/change-detection rejects PNG visual."""
    sid, img_ids = _upload_test_pair(valid_png_path, valid_jpg_path)

    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "threshold": 0.1,
            "threshold_method": "relative_normalized",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False


def test_api_change_detection_basic(geotiff_date1_path, geotiff_date2_path):
    """Test POST /api/v1/analysis/change-detection with identical scenes."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_date2_path)

    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "threshold": 0.1,
            "threshold_method": "relative_normalized",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["change_mask_image_id"] != ""
    assert data["artifact_filename"].endswith(".tif")
    assert data["band_count"] == 1
    assert data["width"] == 5
    assert data["height"] == 5
    assert "changed_pixel_count" in data
    assert "valid_pixel_count" in data
    assert "change_percentage" in data
    assert data["threshold_method"] == "relative_normalized"


def test_api_change_detection_absolute_threshold(geotiff_date1_path, geotiff_date2_path):
    """Test POST /api/v1/analysis/change-detection with absolute threshold."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_date2_path)

    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "threshold": 100.0,
            "threshold_method": "absolute_difference",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["threshold_method"] == "absolute_difference"


def test_api_change_detection_no_overlap(geotiff_date1_path, geotiff_no_overlap_path):
    """Test POST /api/v1/analysis/change-detection with non-overlapping scenes."""
    sid, img_ids = _upload_test_pair(geotiff_date1_path, geotiff_no_overlap_path)

    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": sid,
            "image_id_1": img_ids[0],
            "image_id_2": img_ids[1],
            "threshold": 0.1,
            "threshold_method": "relative_normalized",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "no spatial overlap" in data["message"].lower() or "empty" in data["message"].lower()


def test_api_change_detection_missing_session():
    """Test POST /api/v1/analysis/change-detection with invalid session."""
    res = client.post(
        "/api/v1/analysis/change-detection",
        json={
            "session_id": "nonexistent_session_123",
            "image_id_1": "img1",
            "image_id_2": "img2",
            "threshold": 0.1,
            "threshold_method": "relative_normalized",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "session" in data["message"].lower()

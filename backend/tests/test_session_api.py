from fastapi.testclient import TestClient  # type: ignore[reportMissingImports]
from app.main import app

client = TestClient(app)


def test_session_upload_single_file(valid_jpg_path):
    """Test uploading a single image to create a new session."""
    with open(valid_jpg_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest/upload",
            files=[("files", ("photo.jpg", f, "image/jpeg"))],
        )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["image_count"] == 1
    assert data["classification"]["scene_config"] == "single_image"
    assert len(data["classification"]["images"]) == 1


def test_session_upload_bitemporal_pair(geotiff_date1_path, geotiff_date2_path):
    """Test uploading two multi-temporal GeoTIFFs into a session via multi-file array."""
    with open(geotiff_date1_path, "rb") as f1, open(geotiff_date2_path, "rb") as f2:
        response = client.post(
            "/api/v1/ingest/upload",
            files=[
                ("files", ("t1.tif", f1, "image/tiff")),
                ("files", ("t2.tif", f2, "image/tiff")),
            ],
        )
    assert response.status_code == 200
    data = response.json()
    assert data["image_count"] == 2
    assert data["classification"]["scene_config"] == "bi_temporal_pair"
    assert data["classification"]["confidence"] == "high"
    assert data["classification"]["temporal_relationship"]["has_temporal_information"] is True


def test_session_upload_pair_explicit_slots(geotiff_date1_path, geotiff_date2_path):
    """Test uploading two images using the dedicated POST /api/v1/ingest/upload-pair endpoint."""
    with open(geotiff_date1_path, "rb") as f1, open(geotiff_date2_path, "rb") as f2:
        response = client.post(
            "/api/v1/ingest/upload-pair",
            files={
                "file_1": ("scene_may.tif", f1, "image/tiff"),
                "file_2": ("scene_nov.tif", f2, "image/tiff"),
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["image_count"] == 2
    assert data["classification"]["scene_config"] == "bi_temporal_pair"
    assert data["classification"]["confidence"] == "high"
    assert len(data["classification"]["images"]) == 2


def test_get_session_state_and_scene(geotiff_date1_path, sar_geotiff_path):
    """Test retrieving session state and scene endpoints."""
    with open(geotiff_date1_path, "rb") as f1, open(sar_geotiff_path, "rb") as f2:
        res = client.post(
            "/api/v1/ingest/upload",
            files=[
                ("files", ("opt.tif", f1, "image/tiff")),
                ("files", ("sar.tif", f2, "image/tiff")),
            ],
        )
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    state_res = client.get(f"/api/v1/session/{session_id}")
    assert state_res.status_code == 200
    assert state_res.json()["session_id"] == session_id
    assert state_res.json()["image_count"] == 2

    scene_res = client.get(f"/api/v1/session/{session_id}/scene")
    assert scene_res.status_code == 200
    scene_data = scene_res.json()
    assert scene_data["scene_config"] == "optical_sar_pair"
    assert scene_data["modality_relationship"]["is_multimodal"] is True


def test_delete_session(valid_png_path):
    """Test deleting a session and clearing its artifacts."""
    with open(valid_png_path, "rb") as f:
        res = client.post(
            "/api/v1/ingest/upload",
            files=[("files", ("test.png", f, "image/png"))],
        )
    session_id = res.json()["session_id"]

    del_res = client.delete(f"/api/v1/session/{session_id}")
    assert del_res.status_code == 200

    get_res = client.get(f"/api/v1/session/{session_id}")
    assert get_res.status_code == 404

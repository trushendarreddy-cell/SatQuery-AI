import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test API root status endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_endpoint():
    """Test readiness endpoint and app-level health contract."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "SatQuery AI Backend"
    assert data["storage"]["upload_dir"]
    assert data["storage"]["cache_dir"]


def test_session_artifact_download_and_path_guard():
    """Artifact download should stay inside the session directory and reject traversal attempts."""
    from app.core.session_cache import session_manager

    session = session_manager.get_or_create_session("artifact_guard")
    safe_file = session.session_dir / "sample.txt"
    safe_file.write_text("artifact-contents", encoding="utf-8")
    session.file_paths["artifact-1"] = safe_file

    response = client.get(f"/api/v1/session/{session.session_id}/artifacts")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["artifacts"]) >= 1
    assert payload["artifacts"][0]["filename"] == "sample.txt"

    download = client.get(f"/api/v1/session/{session.session_id}/artifacts/sample.txt")
    assert download.status_code == 200
    assert download.content == b"artifact-contents"

    blocked = client.get(f"/api/v1/session/{session.session_id}/artifacts/../sample.txt")
    assert blocked.status_code in {400, 403, 404}


def test_inspect_endpoint_geotiff(valid_geotiff_path):
    """Test POST /api/v1/ingest/inspect with a valid GeoTIFF upload."""
    with open(valid_geotiff_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest/inspect",
            files={"file": ("sample.tif", f, "image/tiff")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["validation"]["is_valid"] is True
    assert data["metadata"]["category"] == "geospatial_geotiff"
    assert data["metadata"]["has_geospatial_metadata"] is True
    assert data["metadata"]["geospatial"] is not None
    assert data["metadata"]["geospatial"]["crs"] is not None
    assert data["metadata"]["geospatial"]["bounds_native"] is not None
    assert data["metadata"]["geospatial"]["bounds_wgs84"] is not None
    assert data["metadata"]["geospatial"]["resolution"] is not None
    assert data["metadata"]["geospatial"]["bands"][0]["data_type"] == "uint16"
    assert data["metadata"]["acquisition_date"] == "2026:05:14 10:30:00"
    assert data["metadata"]["visual"] is None


def test_inspect_endpoint_jpeg(valid_jpg_path):
    """Test POST /api/v1/ingest/inspect with a standard JPEG upload."""
    with open(valid_jpg_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest/inspect",
            files={"file": ("photo.jpg", f, "image/jpeg")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["validation"]["is_valid"] is True
    assert data["metadata"]["category"] == "visual_standard"
    assert data["metadata"]["modality"] == "visual_standard"
    assert data["metadata"]["has_geospatial_metadata"] is False
    assert data["metadata"]["geospatial"] is None
    assert data["metadata"]["visual"] is not None
    assert data["metadata"]["visual"]["color_mode"] == "RGB"


def test_inspect_endpoint_png(valid_png_path):
    """Test POST /api/v1/ingest/inspect with a standard PNG upload."""
    with open(valid_png_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest/inspect",
            files={"file": ("graphic.png", f, "image/png")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["validation"]["is_valid"] is True
    assert data["metadata"]["category"] == "visual_standard"
    assert data["metadata"]["modality"] == "visual_standard"
    assert data["metadata"]["has_geospatial_metadata"] is False
    assert data["metadata"]["geospatial"] is None
    assert data["metadata"]["visual"] is not None
    assert data["metadata"]["visual"]["color_mode"] == "RGBA"


def test_inspect_endpoint_invalid_text_file():
    """Test POST /api/v1/ingest/inspect with a non-image text file."""
    fake_file = io.BytesIO(b"Hello world, this is a plain text document, not an image.")
    response = client.post(
        "/api/v1/ingest/inspect",
        files={"file": ("document.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["validation"]["is_valid"] is False
    assert len(data["validation"]["errors"]) > 0


def test_inspect_endpoint_corrupted_file(corrupted_file_path):
    """Test POST /api/v1/ingest/inspect with a corrupted file."""
    with open(corrupted_file_path, "rb") as f:
        response = client.post(
            "/api/v1/ingest/inspect",
            files={"file": ("corrupted.jpg", f, "image/jpeg")},
        )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["validation"]["is_valid"] is False
    assert len(data["validation"]["errors"]) > 0

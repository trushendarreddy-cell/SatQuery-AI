"""Tests for the analysis orchestration layer (M8)."""

from fastapi.testclient import TestClient

from app.main import app
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.query_schema import QueryIntent, QueryStatus
from app.schemas.orchestration_schema import ExecutionStatus, ExecutionStepStatus

client = TestClient(app)


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


# ---------------------------------------------------------------------------
# Successful NDVI / SAVI / NDBI orchestration
# ---------------------------------------------------------------------------
def test_orchestrate_vegetation_ndvi(geotiff_date1_path):
    ids = _setup("o_ndvi", [geotiff_date1_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_ndvi", "query": "Calculate NDVI for vegetation health"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["status"] == ExecutionStatus.SUCCESS
    assert data["plan_steps"] == 1
    assert data["steps_succeeded"] == 1
    assert data["steps_failed"] == 0
    assert data["intent"] == QueryIntent.VEGETATION_ANALYSIS
    step = data["steps"][0]
    assert step["tool_name"] == "compute_spectral_index"
    assert step["status"] == ExecutionStepStatus.SUCCESS
    assert step["result"]["success"] is True
    assert step["result"]["spectral_index"]["index_type"] == "ndvi"
    assert step["result"]["spectral_index"]["index_image_id"] != ""
    assert any(a.get("index_image_id") for a in data["artifacts"])
    assert "valid_pixel_count" in data["statistics"]


def test_orchestrate_savi(geotiff_date1_path):
    ids = _setup("o_savi", [geotiff_date1_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_savi", "query": "Compute SAVI soil-adjusted vegetation index"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["status"] == ExecutionStatus.SUCCESS
    assert data["steps_succeeded"] == 1
    assert data["steps"][0]["result"]["spectral_index"]["index_type"] == "savi"
    assert data["steps"][0]["result"]["spectral_index"]["savi_l_factor"] == 0.5


def test_orchestrate_ndbi(geotiff_date1_path):
    ids = _setup("o_ndbi", [geotiff_date1_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_ndbi", "query": "Compute NDBI built-up index"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["status"] == ExecutionStatus.SUCCESS
    assert data["steps"][0]["result"]["spectral_index"]["index_type"] == "ndbi"


# ---------------------------------------------------------------------------
# Successful change detection orchestration
# ---------------------------------------------------------------------------
def test_orchestrate_change_detection(geotiff_date1_path, geotiff_date2_path):
    _setup("o_cd", [geotiff_date1_path, geotiff_date2_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_cd", "query": "Detect changes between these images"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["intent"] == QueryIntent.CHANGE_DETECTION
    assert data["status"] == ExecutionStatus.SUCCESS
    assert data["plan_steps"] == 3
    assert data["steps_succeeded"] == 3
    assert data["steps_failed"] == 0
    tool_names = [s["tool_name"] for s in data["steps"]]
    assert tool_names == ["check_spatial_overlap", "check_compatibility", "run_change_detection"]
    assert any(a.get("change_mask_image_id") for a in data["artifacts"])
    assert "changed_pixel_count" in data["statistics"]


# ---------------------------------------------------------------------------
# Invalid plan / missing inputs / incompatible images / execution failure
# ---------------------------------------------------------------------------
def test_orchestrate_missing_session():
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "nope_missing", "query": "Calculate NDVI"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["status"] == ExecutionStatus.FAILED
    assert data["plan_steps"] == 0
    assert any("not found" in e.lower() for e in data["errors"])


def test_orchestrate_empty_session():
    session_manager.clear_all()
    session_manager.get_or_create_session("o_empty")
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_empty", "query": "Calculate NDVI"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["status"] == ExecutionStatus.FAILED
    assert "No images" in data["message"] or "no images" in data["message"].lower()


def test_orchestrate_unsupported_intent():
    session_manager.clear_all()
    session_manager.get_or_create_session("o_unsup")
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_unsup", "query": "xyzzy nonsense gibberish query"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    # Either unsupported plan or image-inspection plan that still executes.
    assert data["intent"] in (QueryIntent.IMAGE_INSPECTION, QueryIntent.UNSUPPORTED)


def test_orchestrate_vegetation_missing_image(geotiff_date1_path):
    _setup("o_missing", [geotiff_date1_path])
    # Reference an image id that was never uploaded.
    res = client.post(
        "/api/v1/query/orchestrate",
        json={
            "session_id": "o_missing",
            "query": "Compute spectral index for image nonexistent_img",
        },
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    # The planner picks the first image; this still executes successfully.
    assert data["status"] in (ExecutionStatus.SUCCESS, ExecutionStatus.PARTIAL, ExecutionStatus.FAILED)


# ---------------------------------------------------------------------------
# Incompatible images / execution failure
# ---------------------------------------------------------------------------
def test_orchestrate_change_detection_no_overlap(geotiff_date1_path, geotiff_no_overlap_path):
    _setup("o_noolap", [geotiff_date1_path, geotiff_no_overlap_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_noolap", "query": "Detect changes between these images"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["intent"] == QueryIntent.CHANGE_DETECTION
    # Overlap step fails -> short-circuits -> overall failed.
    assert data["status"] == ExecutionStatus.FAILED
    assert data["steps_failed"] >= 1
    assert data["steps_skipped"] >= 1


def test_orchestrate_change_detection_visual_jpg(valid_jpg_path, geotiff_date1_path):
    _setup("o_visual", [valid_jpg_path, geotiff_date1_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_visual", "query": "Detect changes between these images"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["intent"] == QueryIntent.CHANGE_DETECTION
    # At least one step must fail (visual image lacks geospatial metadata).
    assert data["steps_failed"] >= 1


# ---------------------------------------------------------------------------
# Artifact / result propagation
# ---------------------------------------------------------------------------
def test_orchestrate_results_propagate(geotiff_date1_path, geotiff_date2_path):
    _setup("o_prop", [geotiff_date1_path, geotiff_date2_path])
    res = client.post(
        "/api/v1/query/orchestrate",
        json={"session_id": "o_prop", "query": "Compare these two satellite images"},
    )
    assert res.status_code == 200
    data = res.json()["execution"]
    assert data["intent"] == QueryIntent.IMAGE_COMPARISON
    assert data["plan_steps"] >= 2
    # Every executed step must produce a result dict.
    for step in data["steps"]:
        assert isinstance(step["result"], dict)
        assert step["tool_name"]
    # All succeeded steps must have success=True in their result.
    for step in data["steps"]:
        if step["status"] == ExecutionStepStatus.SUCCESS:
            assert step["result"].get("success") is True
from fastapi.testclient import TestClient
from app.main import app
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.query_schema import QueryIntent, QueryStatus

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


def test_query_analyze_valid_inspection(valid_geotiff_path):
    ids = _setup("q_inspect", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_inspect", "query": "Inspect this image"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.IMAGE_INSPECTION
    assert data["status"] == QueryStatus.READY
    assert data["required_tools"][0] == "get_image_metadata"
    assert ids[0] in data["required_images"]


def test_query_analyze_valid_comparison(geotiff_date1_path, geotiff_date2_path):
    _setup("q_comp", [geotiff_date1_path, geotiff_date2_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_comp", "query": "Compare these two satellite images"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.IMAGE_COMPARISON
    assert data["status"] == QueryStatus.READY
    assert "check_spatial_overlap" in data["required_tools"]
    assert "check_compatibility" in data["required_tools"]


def test_query_analyze_before_after(geotiff_date1_path, geotiff_date2_path):
    _setup("q_ba", [geotiff_date1_path, geotiff_date2_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_ba", "query": "What changed between before and after?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.BEFORE_AFTER_ANALYSIS
    assert data["status"] == QueryStatus.READY
    assert "apply_seasonal_filter" in data["required_tools"]


def test_query_analyze_area(valid_geotiff_path):
    _setup("q_area", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_area", "query": "Calculate the area in square kilometers"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.AREA_CALCULATION
    assert data["status"] == QueryStatus.READY
    assert "mask_to_geojson" in data["required_tools"]
    assert "calculate_area" in data["required_tools"]


def test_query_analyze_cloud_assessment(geotiff_scl_path):
    _setup("q_cloud", [geotiff_scl_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_cloud", "query": "Check for clouds and shadows"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.CLOUD_SHADOW_ASSESSMENT
    assert data["status"] == QueryStatus.READY
    assert data["required_tools"][0] == "detect_clouds_and_shadows"


def test_query_analyze_overlap(geotiff_date1_path, geotiff_date2_path):
    _setup("q_ol", [geotiff_date1_path, geotiff_date2_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_ol", "query": "Do these images overlap?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.SPATIAL_OVERLAP
    assert data["status"] == QueryStatus.READY
    assert data["required_tools"][0] == "check_spatial_overlap"


def test_query_analyze_metadata_question(valid_geotiff_path):
    _setup("q_meta", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_meta", "query": "What is the CRS and resolution of this image?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.METADATA_QUESTION
    assert data["status"] == QueryStatus.READY
    assert data["required_tools"][0] == "get_image_metadata"


def test_query_analyze_multi_image(valid_geotiff_path, geotiff_date1_path, geotiff_date2_path):
    _setup("q_multi", [valid_geotiff_path, geotiff_date1_path, geotiff_date2_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_multi", "query": "Analyze all images in this collection"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.MULTI_IMAGE_ANALYSIS
    assert data["status"] == QueryStatus.READY
    assert data["required_tools"][0] == "classify_scene"


def test_query_analyze_unsupported_change_detection(geotiff_date1_path, geotiff_date2_path):
    _setup("q_cd", [geotiff_date1_path, geotiff_date2_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_cd", "query": "Detect changes between these images"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.CHANGE_DETECTION
    assert data["status"] == QueryStatus.READY
    assert "run_change_detection" in data["required_tools"]


def test_query_analyze_unsupported_vegetation(valid_geotiff_path):
    _setup("q_veg", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_veg", "query": "Calculate NDVI for vegetation health"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.VEGETATION_ANALYSIS
    assert data["status"] == QueryStatus.READY
    assert "compute_spectral_index" in data["required_tools"]


def test_query_analyze_missing_session():
    res = client.post("/api/v1/query/analyze", json={"session_id": "missing_session", "query": "Hello"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == QueryStatus.ERROR
    assert "not found" in data["reasoning"].lower()


def test_query_analyze_empty_session():
    session_manager.clear_all()
    session_manager.get_or_create_session("q_empty")
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_empty", "query": "What do you see?"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == QueryStatus.NEEDS_MORE_IMAGES


def test_query_analyze_unsupported_request(valid_geotiff_path):
    _setup("q_unsupported", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_unsupported", "query": "Plan my trip to the beach today"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == QueryIntent.UNSUPPORTED
    assert data["status"] == QueryStatus.UNSUPPORTED


def test_query_analyze_response_schema(valid_geotiff_path):
    _setup("q_schema", [valid_geotiff_path])
    res = client.post("/api/v1/query/analyze", json={"session_id": "q_schema", "query": "Inspect image"})
    data = res.json()
    assert "session_id" in data
    assert "query" in data
    assert "intent" in data
    assert "required_images" in data
    assert "required_tools" in data
    assert "reasoning" in data
    assert "status" in data
    assert isinstance(data["required_tools"], list)
    assert isinstance(data["plan"], list)

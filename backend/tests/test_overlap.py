from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.overlap import check_spatial_overlap, SpatialOverlapEngine


def _setup_session_images(session_id, paths):
    session_manager.clear_all()
    session = session_manager.get_or_create_session(session_id)
    image_ids = []
    for p in paths:
        val = UniversalImageValidator.validate(p)
        meta = UniversalMetadataExtractor.extract(p, category=val.category)
        session_manager.add_image(session_id, p, meta)
        image_ids.append(meta.image_id)
    return image_ids


def test_overlap_identical_bounds(valid_geotiff_path):
    """Test 100% spatial overlap when identical image bounds are compared."""
    ids = _setup_session_images("s_overlap_1", [valid_geotiff_path, valid_geotiff_path])
    result = check_spatial_overlap("s_overlap_1", ids[0], ids[1])
    
    assert result.overlap_exists is True
    assert result.overlap_percentage == 100.0
    assert result.overlap_percentage_image_1 == 100.0
    assert result.overlap_percentage_image_2 == 100.0
    assert result.intersection_geojson is not None
    assert result.intersection_geojson["type"] == "Polygon"
    assert result.intersection_bounds_wgs84 is not None


def test_overlap_partial(geotiff_date1_path, geotiff_date2_path):
    """Test partial spatial overlap between two spatially shifted scenes."""
    ids = _setup_session_images("s_overlap_2", [geotiff_date1_path, geotiff_date2_path])
    result = check_spatial_overlap("s_overlap_2", ids[0], ids[1])
    
    assert result.overlap_exists is True
    assert 0.0 < result.overlap_percentage < 100.0
    assert result.intersection_geojson is not None
    assert result.intersection_area_sqkm is not None


def test_overlap_zero_disjoint_scenes(valid_geotiff_path, geotiff_no_overlap_path):
    """Test that disjoint scenes (India vs New York) produce zero overlap."""
    ids = _setup_session_images("s_overlap_3", [valid_geotiff_path, geotiff_no_overlap_path])
    result = check_spatial_overlap("s_overlap_3", ids[0], ids[1])
    
    assert result.overlap_exists is False
    assert result.overlap_percentage == 0.0
    assert result.intersection_geojson is None
    assert any("do not geographically intersect" in m for m in result.messages)


def test_overlap_different_crs(valid_geotiff_path, geotiff_diff_crs_path):
    """Test spatial overlap between scenes defined in different coordinate systems (UTM 43N vs EPSG:4326)."""
    ids = _setup_session_images("s_overlap_4", [valid_geotiff_path, geotiff_diff_crs_path])
    result = check_spatial_overlap("s_overlap_4", ids[0], ids[1])
    
    assert result.overlap_exists is True
    assert result.overlap_percentage > 90.0
    assert result.intersection_geojson is not None


def test_overlap_rejects_visual_jpg(valid_geotiff_path, valid_jpg_path):
    """Test that unreferenced visual images are gracefully rejected."""
    ids = _setup_session_images("s_overlap_5", [valid_geotiff_path, valid_jpg_path])
    result = check_spatial_overlap("s_overlap_5", ids[0], ids[1])
    
    assert result.overlap_exists is False
    assert result.intersection_geojson is None
    assert any("lacks geospatial metadata" in w for w in result.warnings)

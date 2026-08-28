from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.compatibility import check_compatibility


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


def test_compatibility_valid_pair(geotiff_date1_path, geotiff_date2_path):
    """Test compatibility evaluation for two multi-temporal scenes."""
    ids = _setup_session_images("s_compat_1", [geotiff_date1_path, geotiff_date2_path])
    result = check_compatibility("s_compat_1", ids[0], ids[1])
    
    assert result.compatible is True
    assert result.temporal.has_dates is True
    assert 180 <= result.temporal.time_delta_days <= 186
    assert result.resolution.compatible is True
    assert result.resolution.ratio == 1.0
    assert result.crs.same_crs is True
    assert result.spatial.overlap_exists is True
    assert len(result.recommendations) > 0


def test_compatibility_different_crs(valid_geotiff_path, geotiff_diff_crs_path):
    """Test compatibility between different CRSs (UTM 43N vs EPSG:4326)."""
    ids = _setup_session_images("s_compat_2", [valid_geotiff_path, geotiff_diff_crs_path])
    result = check_compatibility("s_compat_2", ids[0], ids[1])
    
    assert result.crs.same_crs is False
    assert result.crs.reprojection_required is True
    assert result.spatial.overlap_exists is True
    assert any("align_images" in rec for rec in result.recommendations)


def test_compatibility_no_overlap(valid_geotiff_path, geotiff_no_overlap_path):
    """Test compatibility between completely disjoint scenes (zero overlap)."""
    ids = _setup_session_images("s_compat_3", [valid_geotiff_path, geotiff_no_overlap_path])
    result = check_compatibility("s_compat_3", ids[0], ids[1])
    
    assert result.compatible is False
    assert result.spatial.overlap_exists is False
    assert any("not geographically overlap" in msg.lower() or "not possible" in msg.lower() for msg in result.messages)


def test_compatibility_rejects_jpg(valid_geotiff_path, valid_jpg_path):
    """Test that visual JPG is identified as unreferenced and incompatible."""
    ids = _setup_session_images("s_compat_4", [valid_geotiff_path, valid_jpg_path])
    result = check_compatibility("s_compat_4", ids[0], ids[1])
    
    assert result.compatible is False
    assert any("lacks geospatial metadata" in w for w in result.warnings)

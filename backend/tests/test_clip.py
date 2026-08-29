import rasterio
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.clip import clip_to_common_extent


def _setup_session_images(session_id, paths):
    session_manager.clear_all()
    session_manager.get_or_create_session(session_id)
    image_ids = []
    for p in paths:
        val = UniversalImageValidator.validate(p)
        meta = UniversalMetadataExtractor.extract(p, category=val.category)
        session_manager.add_image(session_id, p, meta)
        image_ids.append(meta.image_id)
    return image_ids


def test_clip_identical_extent(valid_geotiff_path):
    ids = _setup_session_images("s_clip_1", [valid_geotiff_path, valid_geotiff_path])
    orig_size = valid_geotiff_path.stat().st_size

    result = clip_to_common_extent("s_clip_1", ids[0], ids[1])

    assert result.success is True
    assert result.width == 10
    assert result.height == 10
    assert result.target_crs == "EPSG:32643"
    assert result.clipped_metadata_1 is not None
    assert result.clipped_metadata_2 is not None
    assert result.intersection_bounds_wgs84 is not None
    assert valid_geotiff_path.stat().st_size == orig_size

    path1 = session_manager.get_image_file_path("s_clip_1", result.clipped_image_id_1)
    path2 = session_manager.get_image_file_path("s_clip_1", result.clipped_image_id_2)
    with rasterio.open(path1) as a, rasterio.open(path2) as b:
        assert a.crs == b.crs
        assert a.transform == b.transform
        assert a.width == b.width == 10
        assert a.height == b.height == 10


def test_clip_partial_overlap_smaller_than_source(geotiff_date1_path, geotiff_date2_path):
    ids = _setup_session_images("s_clip_2", [geotiff_date1_path, geotiff_date2_path])
    result = clip_to_common_extent("s_clip_2", ids[0], ids[1])

    assert result.success is True
    assert result.width == 5
    assert result.height == 5
    assert result.width < 10
    assert result.resolution == [10.0, 10.0]
    assert isinstance(result.width, int)
    assert isinstance(result.height, int)

    path1 = session_manager.get_image_file_path("s_clip_2", result.clipped_image_id_1)
    path2 = session_manager.get_image_file_path("s_clip_2", result.clipped_image_id_2)
    with rasterio.open(path1) as a, rasterio.open(path2) as b:
        assert a.transform == b.transform
        assert a.width == b.width == 5
        assert a.height == b.height == 5


def test_clip_no_overlap(valid_geotiff_path, geotiff_no_overlap_path):
    ids = _setup_session_images("s_clip_3", [valid_geotiff_path, geotiff_no_overlap_path])
    result = clip_to_common_extent("s_clip_3", ids[0], ids[1])

    assert result.success is False
    assert result.width == 0
    assert result.clipped_image_id_1 == ""
    assert "empty extent" in result.message.lower() or "common spatial" in result.message.lower()
    assert "No spatial overlap" in " ".join(result.warnings)


def test_clip_different_crs(valid_geotiff_path, geotiff_diff_crs_path):
    ids = _setup_session_images("s_clip_4", [valid_geotiff_path, geotiff_diff_crs_path])
    result = clip_to_common_extent("s_clip_4", ids[0], ids[1])

    assert result.success is True
    assert "32643" in result.target_crs
    assert result.width >= 1
    assert result.height >= 1
    path1 = session_manager.get_image_file_path("s_clip_4", result.clipped_image_id_1)
    with rasterio.open(path1) as clipped, rasterio.open(valid_geotiff_path) as ref:
        assert clipped.crs == ref.crs


def test_clip_rejects_visual_jpg(valid_geotiff_path, valid_jpg_path):
    ids = _setup_session_images("s_clip_5", [valid_geotiff_path, valid_jpg_path])
    result = clip_to_common_extent("s_clip_5", ids[0], ids[1])

    assert result.success is False
    assert "unreferenced visual image" in result.message
    assert any("lacks geospatial metadata" in w for w in result.warnings)


def test_clip_missing_session():
    result = clip_to_common_extent("does-not-exist", "a", "b")
    assert result.success is False
    assert "not found" in result.message


def test_clip_resolution_mismatch_uses_reference_grid(valid_geotiff_path, geotiff_30m_res_path):
    ids = _setup_session_images("s_clip_6", [valid_geotiff_path, geotiff_30m_res_path])
    result = clip_to_common_extent("s_clip_6", ids[0], ids[1])

    assert result.success is True
    assert result.resolution[0] == 10.0
    assert result.width == 10
    assert result.height == 10

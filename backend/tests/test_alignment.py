import rasterio
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.alignment import align_images


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


def test_alignment_same_crs(valid_geotiff_path, geotiff_date2_path):
    """Test alignment where both rasters share the same CRS (UTM 43N)."""
    ids = _setup_session_images("s_align_1", [valid_geotiff_path, geotiff_date2_path])
    ref_id, tgt_id = ids[0], ids[1]
    
    orig_src_size = geotiff_date2_path.stat().st_size
    orig_ref_size = valid_geotiff_path.stat().st_size
    
    result = align_images("s_align_1", reference_image_id=ref_id, target_image_id=tgt_id)
    
    assert result.success is True
    assert result.target_crs == "EPSG:32643"
    assert result.width == 10
    assert result.height == 10
    assert result.band_count == 4
    assert result.aligned_image_id != ""
    assert result.aligned_metadata is not None
    assert result.aligned_metadata.geospatial.crs == "EPSG:32643"
    
    # Verify original files were NEVER modified
    assert valid_geotiff_path.stat().st_size == orig_ref_size
    assert geotiff_date2_path.stat().st_size == orig_src_size


def test_alignment_different_crs(valid_geotiff_path, geotiff_diff_crs_path):
    """Test reprojection and grid alignment from EPSG:4326 to EPSG:32643."""
    ids = _setup_session_images("s_align_2", [valid_geotiff_path, geotiff_diff_crs_path])
    ref_id, tgt_id = ids[0], ids[1]
    
    result = align_images("s_align_2", reference_image_id=ref_id, target_image_id=tgt_id)
    
    assert result.success is True
    assert "4326" in result.source_crs
    assert "32643" in result.target_crs
    assert result.width == 10
    assert result.height == 10
    assert result.band_count == 2
    
    # Check aligned file on disk directly with rasterio
    aligned_path = session_manager.get_image_file_path("s_align_2", result.aligned_image_id)
    assert aligned_path.exists()
    with rasterio.open(aligned_path) as aligned_ds, rasterio.open(valid_geotiff_path) as ref_ds:
        assert aligned_ds.crs == ref_ds.crs
        assert aligned_ds.transform == ref_ds.transform
        assert aligned_ds.width == ref_ds.width
        assert aligned_ds.height == ref_ds.height


def test_alignment_different_resolution(valid_geotiff_path, geotiff_30m_res_path):
    """Test resampling from 30m grid (5x5) to 10m reference grid (10x10)."""
    ids = _setup_session_images("s_align_3", [valid_geotiff_path, geotiff_30m_res_path])
    ref_id, tgt_id = ids[0], ids[1]
    
    result = align_images("s_align_3", reference_image_id=ref_id, target_image_id=tgt_id)
    assert result.success is True
    assert result.width == 10
    assert result.height == 10


def test_alignment_rejects_visual_jpg(valid_geotiff_path, valid_jpg_path):
    """Test that visual JPG is rejected for CRS alignment."""
    ids = _setup_session_images("s_align_4", [valid_geotiff_path, valid_jpg_path])
    ref_id, tgt_id = ids[0], ids[1]
    
    result = align_images("s_align_4", reference_image_id=ref_id, target_image_id=tgt_id)
    assert result.success is False
    assert "unreferenced visual image" in result.message

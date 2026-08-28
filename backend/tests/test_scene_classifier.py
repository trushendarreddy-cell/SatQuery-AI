from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.scene_classifier import SceneClassifier
from app.schemas.scene_schema import SceneConfiguration
from app.schemas.metadata_schema import SensorModality


def _extract_meta(file_path):
    val = UniversalImageValidator.validate(file_path)
    return UniversalMetadataExtractor.extract(file_path, category=val.category)


def test_scene_single_jpg(valid_jpg_path):
    """Test scene classification for a single visual JPEG image."""
    img = _extract_meta(valid_jpg_path)
    result = SceneClassifier.classify([img], session_id="s1")
    assert result.scene_config == SceneConfiguration.SINGLE_IMAGE
    assert result.image_count == 1
    assert result.confidence == "high"
    assert result.modality_relationship.is_multimodal is False
    assert len(result.modality_relationship.visual_image_ids) == 1


def test_scene_single_png(valid_png_path):
    """Test scene classification for a single visual PNG image."""
    img = _extract_meta(valid_png_path)
    result = SceneClassifier.classify([img], session_id="s2")
    assert result.scene_config == SceneConfiguration.SINGLE_IMAGE
    assert result.image_count == 1
    assert result.confidence == "high"


def test_scene_single_geotiff(valid_geotiff_path):
    """Test scene classification for a single GeoTIFF scene."""
    img = _extract_meta(valid_geotiff_path)
    result = SceneClassifier.classify([img], session_id="s3")
    assert result.scene_config == SceneConfiguration.SINGLE_IMAGE
    assert result.image_count == 1
    assert result.spatial_overview.all_georeferenced is True
    assert len(result.spatial_overview.crs_list) == 1


def test_scene_bitemporal_pair(geotiff_date1_path, geotiff_date2_path):
    """Test classification of two optical scenes acquired at different dates."""
    img1 = _extract_meta(geotiff_date1_path)
    img2 = _extract_meta(geotiff_date2_path)
    
    result = SceneClassifier.classify([img1, img2], session_id="s4")
    assert result.scene_config == SceneConfiguration.BI_TEMPORAL_PAIR
    assert result.image_count == 2
    assert result.confidence == "high"
    assert result.temporal_relationship is not None
    assert result.temporal_relationship.has_temporal_information is True
    assert result.temporal_relationship.earlier_image_id == img1.image_id
    assert result.temporal_relationship.later_image_id == img2.image_id
    # May 1 to Nov 1 = ~184 days
    assert 180 <= result.temporal_relationship.time_delta_days <= 186
    assert result.spatial_overview.all_georeferenced is True
    assert result.spatial_overview.shared_crs is True


def test_scene_optical_sar_pair(geotiff_date1_path, sar_geotiff_path):
    """Test classification of an Optical + SAR multimodal pair."""
    opt_img = _extract_meta(geotiff_date1_path)
    sar_img = _extract_meta(sar_geotiff_path)
    
    assert opt_img.modality == SensorModality.OPTICAL_MULTISPECTRAL
    assert sar_img.modality == SensorModality.SAR_RADAR
    
    result = SceneClassifier.classify([opt_img, sar_img], session_id="s5")
    assert result.scene_config == SceneConfiguration.OPTICAL_SAR_PAIR
    assert result.image_count == 2
    assert result.confidence == "high"
    assert result.modality_relationship.is_multimodal is True
    assert len(result.modality_relationship.optical_image_ids) == 1
    assert len(result.modality_relationship.sar_image_ids) == 1


def test_scene_two_visual_images(valid_jpg_path, valid_jpg_path_2):
    """Test classification of two standard photographic images without geospatial metadata."""
    img1 = _extract_meta(valid_jpg_path)
    img2 = _extract_meta(valid_jpg_path_2)
    
    result = SceneClassifier.classify([img1, img2], session_id="s6")
    assert result.scene_config == SceneConfiguration.VISUAL_PAIR_UNREFERENCED
    assert result.image_count == 2
    assert result.spatial_overview.all_georeferenced is False
    assert any("unreferenced" in msg.lower() or "without embedded geospatial" in msg.lower() for msg in result.messages)


def test_scene_heterogeneous_pair(geotiff_date1_path, valid_jpg_path):
    """Test classification of a mixed GeoTIFF + JPG pair."""
    geo_img = _extract_meta(geotiff_date1_path)
    jpg_img = _extract_meta(valid_jpg_path)
    
    result = SceneClassifier.classify([geo_img, jpg_img], session_id="s7")
    assert result.scene_config == SceneConfiguration.HETEROGENEOUS_COLLECTION
    assert result.image_count == 2
    assert result.spatial_overview.all_georeferenced is False


def test_scene_multi_image(geotiff_date1_path, geotiff_date2_path, sar_geotiff_path):
    """Test classification for 3 or more scenes."""
    img1 = _extract_meta(geotiff_date1_path)
    img2 = _extract_meta(geotiff_date2_path)
    img3 = _extract_meta(sar_geotiff_path)
    
    result = SceneClassifier.classify([img1, img2, img3], session_id="s8")
    assert result.scene_config == SceneConfiguration.MULTI_IMAGE
    assert result.image_count == 3


def test_scene_empty():
    """Test classification for an empty session."""
    result = SceneClassifier.classify([], session_id="s_empty")
    assert result.scene_config == SceneConfiguration.UNKNOWN
    assert result.image_count == 0

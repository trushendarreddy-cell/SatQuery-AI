import rasterio
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.analysis import (
    calculate_spatial_area,
    calculate_spatial_statistics,
    detect_clouds_and_shadows,
    filter_seasonal_false_positives,
    mask_to_geojson,
)
from app.geospatial.area import calculate_geojson_area
from app.schemas.analysis_schema import CloudMaskStatus, SeasonalRisk


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


def test_cloud_mask_from_scl(geotiff_scl_path):
    ids = _setup("s_cloud_1", [geotiff_scl_path])
    result = detect_clouds_and_shadows("s_cloud_1", ids[0])
    assert result.success is True
    assert result.status == CloudMaskStatus.PERFORMED
    assert result.qa_band_index == 4
    assert result.cloud_pixel_count == 10
    assert result.shadow_pixel_count == 4
    assert isinstance(result.cloud_fraction, float)
    assert result.mask_image_id != ""
    path = session_manager.get_image_file_path("s_cloud_1", result.mask_image_id)
    with rasterio.open(path) as ds:
        data = ds.read(1)
        assert int((data == 1).sum()) == 10
        assert int((data == 2).sum()) == 4


def test_cloud_mask_from_qa_pixel(geotiff_qa_pixel_path):
    ids = _setup("s_cloud_2", [geotiff_qa_pixel_path])
    result = detect_clouds_and_shadows("s_cloud_2", ids[0])
    assert result.success is True
    assert result.cloud_pixel_count == 9
    assert result.shadow_pixel_count == 4


def test_cloud_mask_missing_qa(valid_geotiff_path):
    ids = _setup("s_cloud_3", [valid_geotiff_path])
    result = detect_clouds_and_shadows("s_cloud_3", ids[0])
    assert result.success is False
    assert result.status == CloudMaskStatus.NOT_PERFORMED
    assert result.mask_image_id == ""
    assert "Insufficient QA" in " ".join(result.warnings) or "not performed" in result.message.lower()


def test_cloud_mask_rejects_jpg(valid_jpg_path):
    ids = _setup("s_cloud_4", [valid_jpg_path])
    result = detect_clouds_and_shadows("s_cloud_4", ids[0])
    assert result.success is False
    assert result.status == CloudMaskStatus.NOT_PERFORMED
    assert "not fabricated" in " ".join(result.warnings).lower() or "visual" in result.message.lower()


def test_seasonal_opposite_season_not_confirmed_event(geotiff_date1_path, geotiff_date2_path):
    ids = _setup("s_seas_1", [geotiff_date1_path, geotiff_date2_path])
    result = filter_seasonal_false_positives("s_seas_1", ids[0], ids[1])
    assert result.success is True
    assert result.seasonal_risk == SeasonalRisk.HIGH
    assert result.event_confirmed is False
    assert result.mask_modified is False
    assert result.same_phenological_window is False
    assert any("not" in w.lower() and "real event" in w.lower() for w in result.warnings)


def test_seasonal_same_window_low_risk(geotiff_date1_path, valid_geotiff_path):
    ids = _setup("s_seas_2", [geotiff_date1_path, valid_geotiff_path])
    result = filter_seasonal_false_positives("s_seas_2", ids[0], ids[1])
    assert result.success is True
    assert result.seasonal_risk == SeasonalRisk.LOW
    assert result.event_confirmed is False
    assert result.same_phenological_window is True


def test_seasonal_missing_dates(geotiff_no_date_path, geotiff_date1_path):
    ids = _setup("s_seas_3", [geotiff_no_date_path, geotiff_date1_path])
    result = filter_seasonal_false_positives("s_seas_3", ids[0], ids[1])
    assert result.success is False
    assert result.seasonal_risk == SeasonalRisk.UNKNOWN
    assert result.event_confirmed is False


def test_seasonal_does_not_modify_mask(geotiff_date1_path, geotiff_date2_path, geotiff_binary_mask_path):
    ids = _setup("s_seas_4", [geotiff_date1_path, geotiff_date2_path, geotiff_binary_mask_path])
    result = filter_seasonal_false_positives("s_seas_4", ids[0], ids[1], mask_image_id=ids[2])
    assert result.mask_modified is False
    assert result.filtered_mask_image_id == ids[2]
    assert result.event_confirmed is False


def test_mask_to_geojson_valid(geotiff_binary_mask_path):
    ids = _setup("s_vec_1", [geotiff_binary_mask_path])
    result = mask_to_geojson("s_vec_1", ids[0])
    assert result.success is True
    assert result.feature_count >= 1
    assert result.geojson["type"] == "FeatureCollection"
    geom = result.geojson["features"][0]["geometry"]
    coords = geom["coordinates"][0][0]
    assert coords[0] > 70  # longitude, UTM 43N India
    assert 20 < coords[1] < 35  # latitude
    assert 1500 < result.area_m2 < 1700
    assert result.area_ha > 0
    assert isinstance(result.area_sqkm, float)


def test_mask_to_geojson_empty(geotiff_empty_mask_path):
    ids = _setup("s_vec_2", [geotiff_empty_mask_path])
    result = mask_to_geojson("s_vec_2", ids[0])
    assert result.success is True
    assert result.feature_count == 0
    assert result.geojson["features"] == []
    assert result.area_m2 == 0.0
    assert result.area_sqkm == 0.0


def test_mask_to_geojson_rejects_jpg(valid_jpg_path):
    ids = _setup("s_vec_3", [valid_jpg_path])
    result = mask_to_geojson("s_vec_3", ids[0])
    assert result.success is False
    assert result.feature_count == 0
    assert result.geojson["features"] == []


def test_mask_to_geojson_no_crs(invalid_geotiff_no_crs):
    ids = _setup("s_vec_4", [invalid_geotiff_no_crs])
    result = mask_to_geojson("s_vec_4", ids[0])
    assert result.success is False


def test_geodesic_area_empty_collection():
    result = calculate_spatial_area({"type": "FeatureCollection", "features": []})
    assert result.success is True
    assert result.feature_count == 0
    assert result.area_m2 == 0.0
    assert result.area_ha == 0.0


def test_geodesic_area_not_planar_degrees():
    # 1 degree square at equator is ~111 km on a side, ~12321 km2 geodesic, not 1.0
    square = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
    }
    area_m2, count = calculate_geojson_area(square)
    result = calculate_spatial_area(square)
    assert count == 1
    assert result.success is True
    assert result.area_sqkm > 10000
    assert result.area_sqkm < 14000
    assert abs(result.area_ha - result.area_m2 / 10000.0) < 1e-6
    assert abs(result.area_sqkm - result.area_m2 / 1_000_000.0) < 1e-8


def test_zonal_stats_full_raster(valid_geotiff_path):
    ids = _setup("s_zon_1", [valid_geotiff_path])
    result = calculate_spatial_statistics("s_zon_1", ids[0])
    assert result.success is True
    assert len(result.bands) == 2
    assert result.bands[0].valid_pixel_count > 0
    assert result.bands[0].mean_value is not None
    assert isinstance(result.bands[0].mean_value, float)


def test_zonal_stats_with_mask(valid_geotiff_path, geotiff_binary_mask_path):
    ids = _setup("s_zon_2", [valid_geotiff_path, geotiff_binary_mask_path])
    full = calculate_spatial_statistics("s_zon_2", ids[0])
    masked = calculate_spatial_statistics("s_zon_2", ids[0], mask_image_id=ids[1])
    assert masked.success is True
    assert masked.used_mask is True
    assert masked.bands[0].valid_pixel_count == 15
    assert masked.bands[0].valid_pixel_count < full.bands[0].valid_pixel_count


def test_zonal_stats_rejects_jpg(valid_jpg_path):
    ids = _setup("s_zon_3", [valid_jpg_path])
    result = calculate_spatial_statistics("s_zon_3", ids[0])
    assert result.success is False


def test_zonal_stats_misaligned_mask(valid_geotiff_path, geotiff_date2_path):
    ids = _setup("s_zon_4", [valid_geotiff_path, geotiff_date2_path])
    result = calculate_spatial_statistics("s_zon_4", ids[0], mask_image_id=ids[1])
    assert result.success is False
    assert "pixel grid" in result.message.lower()

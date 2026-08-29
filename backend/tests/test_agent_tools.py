import pytest
from pathlib import Path

from app.agent.schemas import AgentToolCall, ToolDefinition
from app.agent.tools import (
    get_tool_registry,
    find_tool_definition,
    invoke_agent_tool,
    validate_and_ingest_image,
    get_image_metadata,
    classify_scene,
    check_spatial_overlap_tool,
    check_compatibility_tool,
    align_images_tool,
    clip_images_tool,
    detect_clouds_and_shadows_tool,
    apply_seasonal_filter_tool,
    mask_to_geojson_tool,
    calculate_spatial_statistics_tool,
    calculate_area_tool,
)
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor


def _setup_session(session_id, paths):
    session_manager.clear_all()
    session_manager.get_or_create_session(session_id)
    ids = []
    for p in paths:
        val = UniversalImageValidator.validate(p)
        meta = UniversalMetadataExtractor.extract(p, category=val.category)
        session_manager.add_image(session_id, Path(p), meta)
        ids.append(meta.image_id)
    return ids


def test_tool_registry_has_all_tools():
    registry = get_tool_registry()
    names = {t.name for t in registry}
    expected = {
        "validate_and_ingest_image",
        "get_image_metadata",
        "classify_scene",
        "check_spatial_overlap",
        "check_compatibility",
        "align_images",
        "clip_images",
        "detect_clouds_and_shadows",
        "apply_seasonal_filter",
        "mask_to_geojson",
        "calculate_spatial_statistics",
        "calculate_area",
    }
    assert expected.issubset(names)
    assert len(registry) >= len(expected)


def test_find_tool_definition():
    t = find_tool_definition("detect_clouds_and_shadows")
    assert t is not None
    assert isinstance(t, ToolDefinition)
    assert t.name == "detect_clouds_and_shadows"
    assert len(t.required_parameters) >= 2
    assert len(t.failure_conditions) >= 1


def test_invoke_unknown_tool():
    result = invoke_agent_tool(AgentToolCall(tool_name="does_not_exist", arguments={}))
    assert result.status.value == "failure"
    assert result.error is not None
    assert "not registered" in result.error


def test_validate_and_ingest_success(valid_geotiff_path):
    sid = "agent_ingest_ok"
    out = validate_and_ingest_image(sid, str(valid_geotiff_path))
    assert out["success"] is True
    assert out["image_id"] != ""
    assert out["session_id"] == sid
    assert "metadata" in out


def test_validate_and_ingest_missing_file():
    out = validate_and_ingest_image("agent_ingest_missing", r"D:\nonexistent\file.tif")
    assert out["success"] is False
    assert "not found" in out["message"].lower()


def test_get_image_metadata_success(valid_geotiff_path):
    ids = _setup_session("agent_meta_ok", [valid_geotiff_path])
    out = get_image_metadata("agent_meta_ok", ids[0])
    assert out["success"] is True
    assert out["metadata"]["image_id"] == ids[0]
    assert out["metadata"]["has_geospatial_metadata"] is True


def test_get_image_metadata_invalid_session():
    out = get_image_metadata("agent_meta_no_sess", "abc")
    assert out["success"] is False
    assert "not found" in out["message"].lower()


def test_get_image_metadata_invalid_image(valid_geotiff_path):
    _setup_session("agent_meta_no_img", [valid_geotiff_path])
    out = get_image_metadata("agent_meta_no_img", "zzz")
    assert out["success"] is False
    assert "not found" in out["message"].lower()


def test_classify_scene_single(valid_jpg_path):
    _setup_session("agent_cls_single", [valid_jpg_path])
    out = classify_scene("agent_cls_single")
    assert out["success"] is True
    assert out["classification"]["scene_config"] == "single_image"


def test_classify_scene_bitemporal(geotiff_date1_path, geotiff_date2_path):
    _setup_session("agent_cls_bi", [geotiff_date1_path, geotiff_date2_path])
    out = classify_scene("agent_cls_bi")
    assert out["success"] is True
    assert out["classification"]["scene_config"] == "bi_temporal_pair"


def test_classify_scene_missing_session():
    out = classify_scene("agent_cls_missing")
    assert out["success"] is False
    assert "not found" in out["message"].lower()


def test_check_spatial_overlap_success(geotiff_date1_path, geotiff_date2_path):
    ids = _setup_session("agent_ol_ok", [geotiff_date1_path, geotiff_date2_path])
    out = check_spatial_overlap_tool("agent_ol_ok", ids[0], ids[1])
    assert out["success"] is True
    assert out["overlap"]["overlap_exists"] is True
    assert out["overlap"]["overlap_percentage"] > 0


def test_check_spatial_overlap_missing_image(valid_geotiff_path):
    ids = _setup_session("agent_ol_miss", [valid_geotiff_path])
    out = check_spatial_overlap_tool("agent_ol_miss", ids[0], "missing")
    assert out["success"] is False


def test_check_spatial_overlap_jpg_rejected(valid_jpg_path, valid_jpg_path_2):
    _setup_session("agent_ol_jpg", [valid_jpg_path, valid_jpg_path_2])
    ids = session_manager.get_images("agent_ol_jpg")
    out = check_spatial_overlap_tool("agent_ol_jpg", ids[0].image_id, ids[1].image_id)
    assert out["success"] is False


def test_check_compatibility_success(geotiff_date1_path, geotiff_date2_path):
    ids = _setup_session("agent_comp_ok", [geotiff_date1_path, geotiff_date2_path])
    out = check_compatibility_tool("agent_comp_ok", ids[0], ids[1])
    assert out["success"] is True
    assert "compatibility" in out


def test_check_compatibility_missing_session():
    out = check_compatibility_tool("agent_comp_no", "a", "b")
    assert out["success"] is False
    assert "not found" in out["message"].lower()


def test_align_images_success(valid_geotiff_path, geotiff_diff_crs_path):
    ids = _setup_session("agent_align_ok", [valid_geotiff_path, geotiff_diff_crs_path])
    out = align_images_tool("agent_align_ok", ids[0], ids[1], "nearest")
    assert out["success"] is True
    assert out["alignment"]["width"] > 0


def test_align_images_missing_session():
    out = align_images_tool("agent_align_no", "a", "b")
    assert out["success"] is False


def test_align_images_jpg_rejected(valid_jpg_path, valid_geotiff_path):
    ids = _setup_session("agent_align_jpg", [valid_jpg_path, valid_geotiff_path])
    out = align_images_tool("agent_align_jpg", ids[1], ids[0])
    assert out["success"] is False


def test_clip_images_success(geotiff_date1_path, geotiff_date2_path):
    ids = _setup_session("agent_clip_ok", [geotiff_date1_path, geotiff_date2_path])
    out = clip_images_tool("agent_clip_ok", ids[0], ids[1])
    assert out["success"] is True
    assert out["clip"]["width"] > 0


def test_clip_images_no_overlap(geotiff_date1_path, geotiff_no_overlap_path):
    ids = _setup_session("agent_clip_no", [geotiff_date1_path, geotiff_no_overlap_path])
    out = clip_images_tool("agent_clip_no", ids[0], ids[1])
    assert out["success"] is False


def test_detect_clouds_and_shadows_success(geotiff_scl_path):
    ids = _setup_session("agent_cld_ok", [geotiff_scl_path])
    out = detect_clouds_and_shadows_tool("agent_cld_ok", ids[0])
    assert out["success"] is True
    assert "cloud_mask" in out


def test_detect_clouds_and_shadows_no_qa(valid_geotiff_path):
    ids = _setup_session("agent_cld_noqa", [valid_geotiff_path])
    out = detect_clouds_and_shadows_tool("agent_cld_noqa", ids[0])
    assert out["success"] is False


def test_detect_clouds_and_shadows_jpg(valid_jpg_path):
    ids = _setup_session("agent_cld_jpg", [valid_jpg_path])
    out = detect_clouds_and_shadows_tool("agent_cld_jpg", ids[0])
    assert out["success"] is False


def test_apply_seasonal_filter_success(geotiff_date1_path, geotiff_date2_path):
    ids = _setup_session("agent_sea_ok", [geotiff_date1_path, geotiff_date2_path])
    out = apply_seasonal_filter_tool("agent_sea_ok", ids[0], ids[1])
    assert out["success"] is True
    assert "seasonal_filter" in out
    assert out["seasonal_filter"]["event_confirmed"] is False


def test_apply_seasonal_filter_missing_dates(geotiff_no_date_path, geotiff_date1_path):
    ids = _setup_session("agent_sea_nodate", [geotiff_no_date_path, geotiff_date1_path])
    out = apply_seasonal_filter_tool("agent_sea_nodate", ids[0], ids[1])
    assert out["success"] is False


def test_mask_to_geojson_success(geotiff_binary_mask_path):
    ids = _setup_session("agent_vec_ok", [geotiff_binary_mask_path])
    out = mask_to_geojson_tool("agent_vec_ok", ids[0])
    assert out["success"] is True
    assert out["geojson"]["geojson"]["type"] == "FeatureCollection"
    assert out["geojson"]["feature_count"] >= 1


def test_mask_to_geojson_empty_mask(geotiff_empty_mask_path):
    ids = _setup_session("agent_vec_empty", [geotiff_empty_mask_path])
    out = mask_to_geojson_tool("agent_vec_empty", ids[0])
    assert out["success"] is True
    assert out["geojson"]["feature_count"] == 0


def test_mask_to_geojson_jpg_rejected(valid_jpg_path):
    ids = _setup_session("agent_vec_jpg", [valid_jpg_path])
    out = mask_to_geojson_tool("agent_vec_jpg", ids[0])
    assert out["success"] is False


def test_calculate_spatial_statistics_full(valid_geotiff_path):
    ids = _setup_session("agent_zonal_full", [valid_geotiff_path])
    out = calculate_spatial_statistics_tool("agent_zonal_full", ids[0])
    assert out["success"] is True
    assert len(out["zonal_stats"]["bands"]) == 2


def test_calculate_spatial_statistics_with_mask(valid_geotiff_path, geotiff_binary_mask_path):
    ids = _setup_session("agent_zonal_mask", [valid_geotiff_path, geotiff_binary_mask_path])
    out = calculate_spatial_statistics_tool("agent_zonal_mask", ids[0], mask_image_id=ids[1])
    assert out["success"] is True
    assert out["zonal_stats"]["used_mask"] is True


def test_calculate_spatial_statistics_jpg(valid_jpg_path):
    ids = _setup_session("agent_zonal_jpg", [valid_jpg_path])
    out = calculate_spatial_statistics_tool("agent_zonal_jpg", ids[0])
    assert out["success"] is False


def test_calculate_spatial_statistics_misaligned(valid_geotiff_path, geotiff_date2_path):
    ids = _setup_session("agent_zonal_bad", [valid_geotiff_path, geotiff_date2_path])
    out = calculate_spatial_statistics_tool("agent_zonal_bad", ids[0], mask_image_id=ids[1])
    assert out["success"] is False


def test_calculate_area_empty_collection():
    out = calculate_area_tool({"type": "FeatureCollection", "features": []})
    assert out["success"] is True
    assert out["area"]["area_m2"] == 0.0


def test_calculate_area_polygon():
    poly = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
    }
    out = calculate_area_tool(poly)
    assert out["success"] is True
    assert out["area"]["area_sqkm"] > 10000


def test_invoke_tool_missing_arguments():
    result = invoke_agent_tool(AgentToolCall(tool_name="get_image_metadata", arguments={}))
    assert result.status.value == "failure"


def test_invoke_tool_invalid_session_id(valid_geotiff_path):
    _setup_session("agent_inv_sess", [valid_geotiff_path])
    result = invoke_agent_tool(AgentToolCall(tool_name="get_image_metadata", arguments={"session_id": "missing", "image_id": "abc"}))
    assert result.status.value == "failure"
    assert result.error is not None or len(result.warnings) > 0


def test_tool_registry_schemas_are_dicts():
    for t in get_tool_registry():
        assert isinstance(t.input_schema, dict)
        assert isinstance(t.output_schema, dict)
        assert "type" in t.input_schema
        assert t.input_schema["type"] == "object"

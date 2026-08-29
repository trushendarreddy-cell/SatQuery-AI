import pytest
import numpy as np
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.change_detection import run_change_detection
from app.schemas.change_detection_schema import ChangeDetectionRequest, ChangeDetectionMethod


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


def test_rejects_visual_jpg(valid_jpg_path):
    """Test change detection rejects visual JPG images."""
    ids = _setup("cd_vis_jpg", [valid_jpg_path])
    payload = ChangeDetectionRequest(
        session_id="cd_vis_jpg",
        image_id_1=ids[0],
        image_id_2=ids[0],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "unreferenced" in res.message.lower() or "geospatial" in res.message.lower()


def test_rejects_visual_png(valid_png_path):
    """Test change detection rejects visual PNG images."""
    ids = _setup("cd_vis_png", [valid_png_path])
    payload = ChangeDetectionRequest(
        session_id="cd_vis_png",
        image_id_1=ids[0],
        image_id_2=ids[0],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "unreferenced" in res.message.lower() or "geospatial" in res.message.lower()


def test_invalid_session():
    payload = ChangeDetectionRequest(
        session_id="nonexistent",
        image_id_1="a",
        image_id_2="b",
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "session" in res.message.lower()


def test_no_spatial_overlap(geotiff_date1_path, geotiff_no_overlap_path):
    """Test change detection fails when scenes don't overlap."""
    ids = _setup("cd_no_overlap", [geotiff_date1_path, geotiff_no_overlap_path])
    payload = ChangeDetectionRequest(
        session_id="cd_no_overlap",
        image_id_1=ids[0],
        image_id_2=ids[1],
        threshold=0.1,
        threshold_method=ChangeDetectionMethod.RELATIVE_NORMALIZED,
    )
    res = run_change_detection(payload)
    assert res.success is False
    assert "no spatial overlap" in res.message.lower() or "empty" in res.message.lower()

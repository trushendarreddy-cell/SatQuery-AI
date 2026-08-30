from pathlib import Path

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.config import settings
from app.services.persistence_service import (
    create_analysis_record,
    create_image_record,
    create_or_update_session,
    get_artifact,
    get_artifact_by_session_and_name,
    get_images_for_session,
    get_session,
    save_artifact_record,
    save_evidence_record,
    save_report_record,
    resolve_storage_path,
)


def test_database_connection():
    with SessionLocal() as db:
        assert db.execute(text("SELECT 1")).scalar() == 1


def test_session_creation_and_retrieval():
    session = create_or_update_session("persist-session-1")
    assert session.id == "persist-session-1"
    same = get_session("persist-session-1")
    assert same is not None
    assert same.id == session.id


def test_image_persistence_and_lookup():
    image = create_image_record(
        session_id="persist-session-1",
        original_filename="scene.tif",
        safe_filename="scene.tif",
        storage_key="sessions/persist-session-1/original/scene.tif",
        file_type="image/tiff",
        file_size=1234,
        checksum="abc123",
        metadata={"category": "geospatial_geotiff", "modality": "optical", "crs": "EPSG:32643", "width": 10, "height": 10, "band_count": 2},
        image_id="img-0001",
    )
    assert image.id == "img-0001"
    lookup = get_images_for_session("persist-session-1")
    assert any(item.id == "img-0001" for item in lookup)


def test_multiple_images_in_one_session():
    i1 = create_image_record(
        session_id="persist-session-2",
        original_filename="a.tif",
        safe_filename="a.tif",
        storage_key="sessions/persist-session-2/a.tif",
        file_type="image/tiff",
        file_size=10,
        checksum="a",
        metadata={"category": "geospatial_geotiff"},
        image_id="img-a",
    )
    i2 = create_image_record(
        session_id="persist-session-2",
        original_filename="b.tif",
        safe_filename="b.tif",
        storage_key="sessions/persist-session-2/b.tif",
        file_type="image/tiff",
        file_size=11,
        checksum="b",
        metadata={"category": "geospatial_geotiff"},
        image_id="img-b",
    )
    items = get_images_for_session("persist-session-2")
    assert {i1.id, i2.id} <= {item.id for item in items}


def test_artifact_persistence_and_retrieval():
    artifact = save_artifact_record(
        session_id="persist-session-1",
        artifact_type="ndvi",
        filename="ndvi.tif",
        storage_key="sessions/persist-session-1/artifacts/ndvi.tif",
        mime_type="image/tiff",
        file_size=64,
        checksum="checksum-ndvi",
        analysis_id="analysis-1",
    )
    found = get_artifact(artifact.id)
    assert found is not None and found.filename == "ndvi.tif"
    by_name = get_artifact_by_session_and_name("persist-session-1", "ndvi.tif")
    assert by_name is not None


def test_analysis_execution_evidence_and_report_persistence():
    analysis = create_analysis_record("persist-session-1", "calculate NDVI", "vegetation_analysis", status="success")
    assert analysis.id
    save_evidence_record(
        analysis_id=analysis.id,
        evidence_type="computed",
        source="compute_spectral_index",
        payload={"metric": "mean_value", "value": 0.61},
        confidence=0.98,
    )
    save_report_record(
        analysis_id=analysis.id,
        title="NDVI analysis",
        summary="Complete.",
        report_payload={"analysis_type": "ndvi"},
        confidence="high",
    )


def test_path_traversal_protection():
    path_root = settings.STORAGE_ROOT.resolve()
    candidate = path_root / "../outside.txt"
    try:
        resolve_storage_path("../outside.txt")
        assert False, "Path traversal should be rejected"
    except ValueError:
        pass


def test_invalid_ids_return_none():
    assert get_session("missing-session") is None
    assert get_artifact("missing-artifact") is None

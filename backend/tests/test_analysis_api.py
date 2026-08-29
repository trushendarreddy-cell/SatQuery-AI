from fastapi.testclient import TestClient
from app.main import app
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor

client = TestClient(app)


def _upload(path, name="scene.tif"):
    session_manager.clear_all()
    with open(path, "rb") as f:
        res = client.post("/api/v1/ingest/upload", files=[("files", (name, f, "image/tiff"))])
    assert res.status_code == 200
    data = res.json()
    return data["session_id"], data["classification"]["image_ids"][0]


def test_api_cloud_mask_and_vectorize(geotiff_scl_path):
    sid, image_id = _upload(geotiff_scl_path, "scl.tif")
    res = client.post("/api/v1/analysis/cloud-mask", json={"session_id": sid, "image_id": image_id})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert isinstance(data["cloud_pixel_count"], int)
    assert isinstance(data["cloud_fraction"], float)

    mask_id = data["mask_image_id"]
    vec = client.post(
        "/api/v1/analysis/mask-to-geojson",
        json={"session_id": sid, "image_id": mask_id, "band_index": 1, "min_value": 1},
    )
    assert vec.status_code == 200
    body = vec.json()
    assert body["success"] is True
    assert body["feature_count"] >= 1
    assert body["geojson"]["type"] == "FeatureCollection"
    assert isinstance(body["area_sqkm"], float)

    area = client.post("/api/v1/analysis/area", json={"geojson": body["geojson"]})
    assert area.status_code == 200
    assert area.json()["success"] is True
    assert area.json()["area_ha"] > 0


def test_api_zonal_and_seasonal(geotiff_date1_path, geotiff_date2_path, geotiff_binary_mask_path):
    session_manager.clear_all()
    files = []
    for path, name in (
        (geotiff_date1_path, "t1.tif"),
        (geotiff_date2_path, "t2.tif"),
        (geotiff_binary_mask_path, "mask.tif"),
    ):
        files.append(("files", (name, open(path, "rb"), "image/tiff")))
    try:
        res = client.post("/api/v1/ingest/upload", files=files)
    finally:
        for _, (_, fh, _) in files:
            fh.close()
    assert res.status_code == 200
    data = res.json()
    sid = data["session_id"]
    ids = data["classification"]["image_ids"]

    zonal = client.post(
        "/api/v1/analysis/zonal-stats",
        json={"session_id": sid, "image_id": ids[0], "mask_image_id": ids[2]},
    )
    assert zonal.status_code == 200
    z = zonal.json()
    assert z["success"] is True
    assert isinstance(z["bands"][0]["valid_pixel_count"], int)
    assert isinstance(z["bands"][0]["mean_value"], float)

    seas = client.post(
        "/api/v1/analysis/seasonal-filter",
        json={"session_id": sid, "image_id_1": ids[0], "image_id_2": ids[1], "mask_image_id": ids[2]},
    )
    assert seas.status_code == 200
    s = seas.json()
    assert s["event_confirmed"] is False
    assert s["mask_modified"] is False
    assert s["seasonal_risk"] == "high"

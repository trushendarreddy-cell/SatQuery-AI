# SatQuery AI Backend - As-Built System And Data-Flow Audit

Audit date: 2026-08-28  
Repository root inspected: `D:\SIH 2026\SatQuery AI`  
Backend root inspected: `D:\SIH 2026\SatQuery AI\backend`  
Source of truth: current Python source, mounted FastAPI routes, Pydantic schemas, tests, requirements, local execution results, and current Git state.  
Important note: the working tree is dirty. This report includes the uncommitted current code state because that is what runs locally.

---

## 1. Executive Summary

SatQuery AI currently has a working FastAPI backend for image ingestion, validation, metadata extraction, scene/session classification, spatial overlap, raster grid alignment, and compatibility checks.

Implemented today:

- JPG/JPEG/PNG/BMP/WEBP-style visual-image validation through Pillow.
- GeoTIFF/TIFF validation through Rasterio when `.tif` or `.tiff` is uploaded.
- Fallback Rasterio probing for unknown extensions, which can accept other Rasterio-readable georeferenced rasters but labels them as `geospatial_geotiff`.
- Metadata extraction for visual images and georeferenced rasters.
- In-memory session management with per-session disk cache folders.
- Deterministic scene classification for single images, visual pairs, GeoTIFF pairs, optical/SAR pairs, heterogeneous pairs, and multi-image collections.
- REST APIs for inspection, upload, explicit pair upload, session retrieval, scene retrieval, session deletion, spatial overlap, compatibility, and alignment.
- Deterministic Python functions for `check_spatial_overlap()`, `check_compatibility()`, and `align_images()`.
- Test suite: 46 tests passed, 0 failed, 0 skipped, 5 warnings, in 1.25s.

Not implemented today:

- AI/VLM model calls.
- Cloud and shadow masking.
- Seasonal false positive filtering.
- Raster mask to GeoJSON vectorization.
- Standalone geodesic area tools for arbitrary masks/features.
- Zonal/spatial statistics beyond simple per-band raster metadata summaries.
- Persistent session database.
- Automatic temp/cache cleanup after server restart.

Key risks:

- `/api/v1/ingest/upload` and `/api/v1/ingest/upload-pair` silently skip invalid files and still return HTTP 200.
- Uploaded filenames and supplied `session_id` are not strongly sanitized.
- No upload size limits or MIME enforcement exist.
- `/inspect` stores files under `backend/temp/uploads` and does not delete them after inspection.
- Sessions exist only in process memory; cached files remain on disk after restart but are no longer retrievable through the session manager.

---

## 2. Project Identity

Project name: SatQuery AI  
Current backend owner: Rushendar  
Backend responsibility: provide the API, ingestion pipeline, metadata extraction, deterministic scene/session state, geospatial compatibility tools, and cached raster artifacts for frontend and AI-agent consumers.

Overall backend purpose:

SatQuery AI is a backend service for multimodal remote-sensing image analysis. Its current role is to accept uploaded images, determine whether they are ordinary visual images or georeferenced rasters, extract safe metadata, register images into sessions, classify how images relate, and expose deterministic geospatial tools that future AI-agent workflows can call.

Team relationship:

- Shankar/frontend sends files and session IDs to FastAPI and renders returned metadata, preview IDs, scene classification, map bounds, validation errors, and geospatial tool results.
- Bhanu/AI agent can consume the structured metadata/session/classification/tool outputs. No LLM agent runtime is implemented in this repo yet.
- Rushendar/backend owns validation, metadata, sessions, schemas, deterministic APIs, and future geospatial processing.
- Future remote-sensing modules should call the backend's existing session metadata and file-path mapping rather than reparsing uploads independently.

As-built architecture role:

```text
Frontend file picker
  -> FastAPI REST API
  -> ingestion endpoint
  -> temp/cache file storage
  -> validator
  -> metadata extractor
  -> session manager
  -> scene classifier
  -> optional spatial engines
  -> JSON response for frontend and future AI agent
```

---

## 3. Actual Project Directory

Tracked files from `git ls-files`:

```text
.gitignore
backend/README.md
backend/requirements.txt
backend/app/__init__.py
backend/app/main.py
backend/app/api/__init__.py
backend/app/api/v1/__init__.py
backend/app/api/v1/router.py
backend/app/api/v1/endpoints/__init__.py
backend/app/api/v1/endpoints/ingest.py
backend/app/api/v1/endpoints/session.py
backend/app/api/v1/endpoints/spatial.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/session_cache.py
backend/app/geospatial/__init__.py
backend/app/pipeline/__init__.py
backend/app/pipeline/alignment.py
backend/app/pipeline/compatibility.py
backend/app/pipeline/metadata.py
backend/app/pipeline/overlap.py
backend/app/pipeline/scene_classifier.py
backend/app/pipeline/validator.py
backend/app/schemas/__init__.py
backend/app/schemas/metadata_schema.py
backend/app/schemas/scene_schema.py
backend/app/schemas/spatial_schema.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/test_alignment.py
backend/tests/test_api.py
backend/tests/test_compatibility.py
backend/tests/test_metadata.py
backend/tests/test_overlap.py
backend/tests/test_scene_classifier.py
backend/tests/test_session_api.py
backend/tests/test_spatial_api.py
backend/tests/test_validator.py
```

Generated/local directories exist but are not tracked: `backend/venv`, `backend/temp`, `.pytest_cache`, and `__pycache__` folders. `backend/temp/uploads` and `backend/temp/cache` contain old local uploaded/test artifacts.

### File Inventory

| File | Purpose | Implemented | Actively used | Main classes/functions | Main dependencies | Task area |
|---|---:|---:|---:|---|---|---|
| `backend/app/main.py` | FastAPI app, CORS, router mounting, root/health, custom OpenAPI | Yes | Yes | `app`, `custom_openapi()`, `root()`, `health_check()` | FastAPI, CORS, OpenAPI | API foundation |
| `backend/app/api/v1/router.py` | Aggregates API v1 routers | Yes | Yes | `api_router` | FastAPI router | API foundation |
| `backend/app/api/v1/endpoints/ingest.py` | `/inspect`, `/upload`, `/upload-pair` | Yes | Yes | `inspect_image()`, `upload_images_to_session()`, `upload_image_pair()` | FastAPI, Starlette response, validator, metadata, session, classifier | Tasks 1-3, 7 |
| `backend/app/api/v1/endpoints/session.py` | session state, scene, delete endpoints | Yes | Yes | `get_session_state()`, `get_scene_classification()`, `delete_session()` | FastAPI, session manager, classifier | Tasks 3, 7 |
| `backend/app/api/v1/endpoints/spatial.py` | spatial overlap/compatibility/alignment endpoints | Yes | Yes | `get_spatial_overlap()`, `get_compatibility()`, `align_spatial_rasters()` | FastAPI, spatial schemas, spatial engines | Tasks 4-6 |
| `backend/app/core/config.py` | project constants and temp/cache dirs | Yes | Yes | `Settings`, `settings` | pathlib | Foundation |
| `backend/app/core/session_cache.py` | in-memory sessions and disk cache folders | Yes | Yes | `SessionData`, `SessionManager`, `session_manager` | dataclasses, uuid, shutil, datetime | Task 7 |
| `backend/app/pipeline/validator.py` | dual-path image validation | Yes | Yes | `UniversalImageValidator.validate()`, `_validate_geotiff()`, `_validate_visual_image()` | Pillow, Rasterio | Task 1 |
| `backend/app/pipeline/metadata.py` | visual/geospatial metadata extraction | Yes | Yes | `UniversalMetadataExtractor.extract()`, `_extract_visual_metadata()`, `_extract_geotiff_metadata()`, `_classify_geotiff_modality()` | Pillow, Rasterio, NumPy | Task 2 |
| `backend/app/pipeline/scene_classifier.py` | deterministic scene/modality/temporal/spatial overview | Yes | Yes | `SceneClassifier.classify()` and helper methods | datetime, regex, schemas | Task 3 |
| `backend/app/pipeline/overlap.py` | bounding-box spatial overlap and geodesic intersection area | Yes | Yes | `SpatialOverlapEngine.calculate_overlap()`, `check_spatial_overlap()` | Shapely, PyProj | Task 5, partial Task 24 |
| `backend/app/pipeline/alignment.py` | Rasterio reprojection/alignment artifact creation | Yes | Yes | `GridAlignmentEngine.align_rasters()`, `align_images()` | Rasterio warp | Task 4 |
| `backend/app/pipeline/compatibility.py` | temporal/resolution/CRS/overlap/grid compatibility | Yes | Yes | `CompatibilityEngine.evaluate()`, `check_compatibility()` | Rasterio, overlap engine, classifier | Task 6 |
| `backend/app/schemas/metadata_schema.py` | metadata and inspect schemas/enums | Yes | Yes | `ImageCategory`, `SensorModality`, `UnifiedImageMetadata`, `InspectResponse`, etc. | Pydantic | Tasks 1-3 |
| `backend/app/schemas/scene_schema.py` | scene/session schemas/enums | Yes | Yes | `SceneConfiguration`, `SceneClassificationResult`, `SessionStateResponse`, etc. | Pydantic | Tasks 3, 7 |
| `backend/app/schemas/spatial_schema.py` | spatial request/result schemas | Yes | Yes | overlap, alignment, compatibility request/result models | Pydantic | Tasks 4-6 |
| `backend/app/geospatial/__init__.py` | placeholder package docstring | Placeholder only | No meaningful import found | none | none | Future Tasks 21-25 |
| `backend/README.md` | setup docs and old Milestone 1 description | Stale documentation | Not runtime | none | none | Documentation |
| `backend/tests/*.py` | pytest coverage and synthetic fixtures | Yes | Test-only | fixtures and tests | pytest, TestClient, Pillow, Rasterio | Verification |
| `__init__.py` files | package markers | Minimal | Import/package loading | none | none | Foundation |

---

## 4. Complete User-To-Backend Data Flow

### `/api/v1/ingest/inspect`

```text
USER
  -> FRONTEND FILE PICKER
  -> HTTP multipart/form-data field: file
  -> FastAPI inspect_image()
  -> backend/temp/uploads/{8hex}_{original_filename}
  -> UniversalImageValidator.validate()
  -> UniversalMetadataExtractor.extract()
  -> InspectResponse JSON
  -> FRONTEND / AI AGENT
```

Stage details:

| Stage | Input | Code | Output | Failure behavior | File behavior |
|---|---|---|---|---|---|
| File picker | one user file | frontend outside repo | browser `File` object | frontend-side only | no backend file yet |
| Multipart request | field `file` | FastAPI `UploadFile` | stream-like upload object | missing field: FastAPI validation error | no backend file yet |
| Temporary storage | uploaded stream | `inspect_image()` writes with `shutil.copyfileobj()` | `backend/temp/uploads/{uuid}_{filename}` | unexpected write/process error returns 500 | file remains on disk |
| Validation | local path | `UniversalImageValidator.validate()` | `ValidationResult` | invalid returns HTTP 422 with structured JSON | invalid file remains on disk |
| Metadata | valid category/path | `UniversalMetadataExtractor.extract()` | `UnifiedImageMetadata` | exception returns HTTP 500 | file remains on disk |
| Response | validation + metadata | `InspectResponse` | `success`, `message`, `validation`, `metadata` | n/a | no session created |

`/inspect` does not create a session, does not register state, and does not delete the inspected file.

### `/api/v1/ingest/upload`

```text
USER
  -> FRONTEND FILE PICKER(S)
  -> HTTP multipart/form-data fields: files, files, ...
  -> FastAPI upload_images_to_session()
  -> get_or_create_session(session_id)
  -> backend/temp/cache/{session_id}/{8hex}_{original_filename}
  -> validate each file
  -> extract metadata for valid files
  -> session_manager.add_image()
  -> SceneClassifier.classify()
  -> SessionStateResponse JSON
  -> FRONTEND / AI AGENT
```

Stage details:

| Stage | Input | Code | Output | Failure behavior | File behavior |
|---|---|---|---|---|---|
| Session selection | optional `session_id` form field | `SessionManager.get_or_create_session()` | existing/new `SessionData` | arbitrary strings accepted after `.strip()` | creates `backend/temp/cache/{session_id}` |
| File storage | one or more `files` | loop in `upload_images_to_session()` | per-file cache path | write exception can abort request | written files remain |
| Validation | each local file | `UniversalImageValidator.validate()` | per-file validation | invalid file is silently skipped; response still 200 | invalid skipped file remains in cache dir |
| Metadata | valid file | `UniversalMetadataExtractor.extract()` | `UnifiedImageMetadata` | extraction exception aborts request | file remains |
| Registration | metadata/path | `session_manager.add_image()` | `session.images[image_id]`, `session.file_paths[image_id]` | no per-image duplicate check beyond ID key | registered file persists |
| Classification | current session images | `SceneClassifier.classify()` | `SceneClassificationResult` | empty session classified `unknown` | no cleanup |
| Response | session + classification | `SessionStateResponse` | session id/timestamps/count/classification | n/a | session remains in memory |

### `/api/v1/ingest/upload-pair`

Same as `/upload`, but multipart fields are exactly `file_1` and `file_2`. It is a convenience UI/API endpoint for two explicit slots. It still does not prove before/after ordering by slot name; chronology comes only from parsed metadata timestamps.

---

## 5. Supported File Types

### Visual Path

Explicit extension set in code:

- `.jpg`
- `.jpeg`
- `.png`
- `.bmp`
- `.webp`

Validation uses Pillow:

- `Image.open(path)` opens the image.
- `img.verify()` checks structural integrity.
- The image is reopened after verify.
- Width and height must be greater than zero.
- Accepted/recognized modes: `RGB`, `RGBA`, `L`, `P`, `CMYK`.
- Other modes are valid with warning: `Non-standard color mode detected: '{mode}'.`
- Channel count is `len(img.getbands())`.
- Format is `img.format` or file extension fallback.
- Bit depth is currently hard-coded as `8`, not truly detected.
- EXIF date is read from `DateTime`, `DateTimeOriginal`, or `DateTimeDigitized` if present.
- Geospatial data is deliberately not invented: `has_geospatial_metadata=False`, `geospatial=None`.

### Geospatial Path

Explicit extension set in code:

- `.tif`
- `.tiff`

Validation uses Rasterio:

- `rasterio.open(path)` opens the raster.
- Width and height must be greater than zero.
- Band count must be greater than zero.
- CRS is required for true `geospatial_geotiff`.
- Transform must be present and must not have both `transform.a == 0` and `transform.e == 0`.
- If CRS is missing, the TIFF is returned as valid `visual_standard` with warning: `TIFF file lacks embedded Coordinate Reference System (CRS). Fallback to standard visual path.`
- If Rasterio cannot open the TIFF, validation fails with `Corrupted or unreadable TIFF file: ...`.
- COG is not explicitly detected, but a COG readable by Rasterio with `.tif`/`.tiff`, CRS, transform, dimensions, and bands follows the GeoTIFF path.

Important actual-code nuance:

For unknown extensions, the validator first calls `_validate_geotiff()`. Because `_validate_geotiff()` catches Rasterio errors and returns an invalid `ValidationResult` instead of raising, unsupported files commonly return a geospatial/TIFF-style validation error without ever attempting Pillow fallback. A Rasterio-readable georeferenced file with an unknown extension can be accepted and labeled `geospatial_geotiff`, even if its driver is not actually `GTiff`.

---

## 6. What A Normal User Should Upload

| User upload | Current backend understanding | Geographic coordinates? | Spatial comparison? | VLM/visual reasoning candidate? |
|---|---|---:|---:|---:|
| `photo.jpg` | `visual_standard`, usually modality `visual_standard` | No | No | Yes, future agent/VLM only |
| `graphic.png` | `visual_standard`, usually modality `visual_standard` | No | No | Yes, future agent/VLM only |
| one satellite GeoTIFF | `geospatial_geotiff`; modality from tags/bands | Yes if CRS/bounds valid | Single scene only; comparison needs another scene | Yes, plus geospatial tools |
| two satellite GeoTIFFs | classified by metadata as bi-temporal, optical/SAR, or candidate pair | Yes | Yes through `/spatial/*` if overlapping/georeferenced | Yes, future agent |
| two ordinary JPG/PNG images | `visual_pair_unreferenced` | No | No | Yes, future visual pair reasoning only |
| optical + SAR GeoTIFFs | `optical_sar_pair` if exactly one optical and one SAR detected | Yes | Yes if geospatially compatible | Yes, future multimodal agent |
| mixed GeoTIFF + JPG/PNG | `heterogeneous_collection` | Only GeoTIFF has coordinates | Direct spatial comparison rejected | Future agent may reason separately |

The backend never invents coordinates for normal JPG/PNG images.

---

## 7. Endpoint Inventory

OpenAPI inspection showed these mounted paths:

| Method | Path | Purpose | Request | Main response | Consumer | Tests |
|---|---|---|---|---|---|---|
| GET | `/` | API info | none | project/version/status/docs/API prefix | dev/frontend health | `test_root_endpoint` |
| GET | `/health` | health probe | none | `{"status":"healthy"}` | deployments/monitoring | `test_health_endpoint` |
| POST | `/api/v1/ingest/inspect` | validate/profile one file | multipart `file` | `InspectResponse` | frontend, agent context builder | `test_inspect_*` |
| POST | `/api/v1/ingest/upload` | upload one or more files into session | multipart repeated `files`, optional form `session_id` | `SessionStateResponse` | frontend primary upload | `test_session_*` |
| POST | `/api/v1/ingest/upload-pair` | upload exactly two explicit file slots | multipart `file_1`, `file_2`, optional `session_id` | `SessionStateResponse` | frontend pair UI/Swagger convenience | `test_session_upload_pair_explicit_slots` |
| GET | `/api/v1/session/{session_id}` | retrieve session state and classification | path `session_id` | `SessionStateResponse` or 404 | frontend, agent | `test_get_session_state_and_scene` |
| GET | `/api/v1/session/{session_id}/scene` | retrieve classification only | path `session_id` | `SceneClassificationResult` or 404 | frontend, agent | `test_get_session_state_and_scene` |
| DELETE | `/api/v1/session/{session_id}` | delete in-memory session and cache dir | path `session_id` | message or 404 | frontend cleanup | `test_delete_session` |
| POST | `/api/v1/spatial/overlap` | compute WGS84 bbox intersection and overlap metrics | JSON `SpatialOverlapRequest` | `SpatialOverlapResult` | frontend map/agent tool | `test_api_spatial_overlap` |
| POST | `/api/v1/spatial/compatibility` | temporal/resolution/CRS/overlap/grid suitability | JSON `CompatibilityRequest` | `CompatibilityResult` | agent/frontend workflow gate | `test_api_spatial_compatibility` |
| POST | `/api/v1/spatial/align` | reproject/warp target raster to reference grid | JSON `AlignmentRequest` | `AlignmentResult` | agent/backend pipeline | `test_api_spatial_align` |

Auto docs are configured at `/docs` and `/redoc`, but they are documentation UI routes, not domain APIs.

Example requests:

```bash
curl -F "file=@photo.jpg" http://127.0.0.1:8000/api/v1/ingest/inspect
curl -F "files=@t1.tif" -F "files=@t2.tif" http://127.0.0.1:8000/api/v1/ingest/upload
curl -F "session_id=abc123" -F "files=@new.png" http://127.0.0.1:8000/api/v1/ingest/upload
curl -F "file_1=@before.tif" -F "file_2=@after.tif" http://127.0.0.1:8000/api/v1/ingest/upload-pair
curl -X POST http://127.0.0.1:8000/api/v1/spatial/overlap -H "Content-Type: application/json" -d "{\"session_id\":\"...\",\"image_id_1\":\"...\",\"image_id_2\":\"...\"}"
```

---

## 8. `/api/v1/ingest/inspect`

Request:

- Method: POST
- Path: `/api/v1/ingest/inspect`
- Content type: `multipart/form-data`
- File field: `file`
- Accepts: one file only
- Creates session: no
- Modifies session state: no

Process:

1. Generate `image_uuid = uuid.uuid4().hex[:8]`.
2. Build filename `{image_uuid}_{file.filename}`.
3. Store file at `settings.UPLOAD_DIR`, which is `backend/temp/uploads`.
4. Run `UniversalImageValidator.validate(temp_file_path)`.
5. If invalid, return HTTP 422 with `success=false`, validation details, and `metadata=null`.
6. If valid, run `UniversalMetadataExtractor.extract(..., compute_stats=True)`.
7. Return HTTP 200 `InspectResponse`.
8. Always closes `UploadFile`; does not delete temp file.

Difference from `/upload`:

- `/inspect` profiles one file and does not create/register a session.
- `/upload` accepts one or more files, creates or appends to a session, stores files under `backend/temp/cache/{session_id}`, and returns classification.

Observed JPG inspect response shape:

```json
{
  "success": true,
  "message": "Successfully processed visual standard image.",
  "validation": {
    "is_valid": true,
    "category": "visual_standard",
    "errors": [],
    "warnings": []
  },
  "metadata": {
    "image_id": "dynamic-8hex",
    "filename": "dynamic-8hex_photo.jpg",
    "format": "JPEG",
    "category": "visual_standard",
    "modality": "visual_standard",
    "has_geospatial_metadata": false,
    "width": 64,
    "height": 64,
    "channels": 3,
    "file_size_bytes": 692,
    "acquisition_date": null,
    "geospatial": null,
    "visual": {
      "color_mode": "RGB",
      "channel_count": 3,
      "bit_depth": 8
    }
  }
}
```

---

## 9. `/api/v1/ingest/upload`

Request:

- Method: POST
- Path: `/api/v1/ingest/upload`
- Content type: `multipart/form-data`
- File field: repeated `files`
- Optional form field: `session_id`
- Accepts: one or more files

Lifecycle: first request

```text
files
  -> get_or_create_session(None)
  -> new 12-hex session_id
  -> write each file to backend/temp/cache/{session_id}
  -> validate each file
  -> extract metadata for valid files
  -> add metadata/path to session
  -> classify all current session images
  -> return SessionStateResponse
```

Lifecycle: second request with same `session_id`

```text
same session_id
  -> existing session loaded from in-memory dict
  -> new file(s) written to same cache folder
  -> valid image(s) appended to session
  -> classifier reruns on all images in insertion order
  -> updated SessionStateResponse
```

Important behavior:

- If `session_id` is omitted or blank, a new 12-character hex session ID is created.
- If an existing in-memory `session_id` is supplied, images are appended.
- If a non-existing `session_id` is supplied, a new session with that exact string is created.
- Invalid files are skipped silently and are not represented in response errors.
- If all files are invalid, the endpoint can return HTTP 200 with `image_count=0` and `scene_config=unknown`.
- Image IDs are 8-character hex strings generated independently from filenames.

Observed single upload:

```json
{
  "session_id": "1bbcbc4de9fb",
  "created_at": "2026-08-28T...+00:00",
  "updated_at": "2026-08-28T...+00:00",
  "image_count": 1,
  "classification": {
    "scene_config": "single_image",
    "image_count": 1,
    "image_ids": ["22c189dd"],
    "confidence": "high",
    "messages": ["Single standard visual image loaded (unreferenced)."],
    "warnings": []
  }
}
```

Observed repeated upload into same session:

```json
{
  "session_id": "1bbcbc4de9fb",
  "image_count": 2,
  "classification": {
    "scene_config": "visual_pair_unreferenced",
    "image_ids": ["22c189dd", "c165e02b"],
    "confidence": "medium",
    "messages": [
      "Two standard visual images loaded without embedded geospatial coordinates. Spatial overlap and physical alignment cannot be determined without geospatial reference."
    ],
    "warnings": []
  }
}
```

---

## 10. `/api/v1/ingest/upload-pair`

Current status: implemented in uncommitted working tree.

Request:

- Method: POST
- Path: `/api/v1/ingest/upload-pair`
- Content type: `multipart/form-data`
- File fields: `file_1`, `file_2`
- Optional form field: `session_id`

Behavior:

- Creates or appends to a session.
- Processes exactly two supplied file slots.
- Stores each file under `backend/temp/cache/{session_id}`.
- Uses same validator, metadata extractor, session registration, and classifier as `/upload`.
- Does not mark `file_1` as "before" or `file_2` as "after" in data structures.
- Does not assign roles like reference/target/optical/SAR based on slot names.
- Invalid files are silently skipped.

Use this endpoint for frontend UIs with two separate file pickers. Use `/upload` for arbitrary multi-file arrays.

---

## 11. Two-Image / Two-File Workflow

There are two current paths:

- General path: `POST /api/v1/ingest/upload` with two repeated `files` fields.
- Dedicated convenience path: `POST /api/v1/ingest/upload-pair` with `file_1` and `file_2`.

How relationship is identified:

- The classifier uses metadata evidence, not the user's words.
- Before/after order is inferred only from parsed acquisition dates.
- Optical/SAR relationship is inferred from GeoTIFF modality:
  - SAR if tags/descriptions include `VV`, `VH`, `HH`, `HV`, `SAR`, `SENTINEL-1`, or `POLARIZATION`.
  - Optical RGB if 3-band GeoTIFF.
  - Optical multispectral if 4+ bands.
- Spatial compatibility uses geospatial metadata presence, CRS list, and resolution ratio.
- Filename patterns are ignored for classification.

Current cases:

| Input pair | Classification |
|---|---|
| two JPG/PNG visual files | `visual_pair_unreferenced` |
| two GeoTIFFs with different valid timestamps | `bi_temporal_pair`, high confidence |
| two GeoTIFFs without timestamps | `bi_temporal_pair`, medium confidence, warning |
| one optical GeoTIFF + one SAR GeoTIFF | `optical_sar_pair`, high confidence |
| one GeoTIFF + one visual image | `heterogeneous_collection`, low confidence |

---

## 12. Image Validation Pipeline

`UniversalImageValidator.validate(file_path)`:

1. Converts input to `Path`.
2. Fails if file does not exist:
   - `is_valid=false`
   - `category=visual_standard`
   - error `File does not exist at path: ...`
3. Fails if file is 0 bytes:
   - `is_valid=false`
   - `category=visual_standard`
   - error `Uploaded file is empty (0 bytes).`
4. Routes `.tif`/`.tiff` to `_validate_geotiff()`.
5. Routes `.jpg`/`.jpeg`/`.png`/`.bmp`/`.webp` to `_validate_visual_image()`.
6. For unknown extensions, attempts `_validate_geotiff()` first; because invalid Rasterio opens are caught internally, this often returns invalid immediately.

`_validate_geotiff(path)`:

- Opens with `rasterio.open()`.
- Checks positive dimensions.
- Checks band count greater than zero.
- If CRS missing, returns valid `visual_standard` with warning.
- Checks transform is not missing and not zero-resolution.
- Returns valid `geospatial_geotiff` only if no errors.
- Catches `RasterioIOError`, `CRSError`, and generic exception into invalid results.

`_validate_visual_image(path)`:

- Opens with Pillow and calls `img.verify()`.
- Reopens to read size and mode.
- Fails on invalid dimensions.
- Warns on unusual color mode.
- Catches `UnidentifiedImageError`, `IOError`, `SyntaxError`, and generic exceptions.

Distinctions:

| State | `ValidationResult` | API behavior in `/inspect` | API behavior in `/upload` |
|---|---|---|---|
| Valid | `is_valid=true`, no errors | HTTP 200 with metadata | registered and returned in session |
| Invalid | `is_valid=false`, errors present | HTTP 422 with `metadata=null` | skipped silently; endpoint still returns 200 |
| Valid with warning | `is_valid=true`, warnings present | HTTP 200 with warnings and metadata if extraction succeeds | registered and warnings are not preserved separately in session response except inside inspect response |

---

## 13. Metadata Extraction Pipeline

Entry point:

```python
UniversalMetadataExtractor.extract(file_path, category, image_id=None, compute_stats=True)
```

If `category == ImageCategory.GEOSPATIAL_GEOTIFF`, `_extract_geotiff_metadata()` runs. Otherwise `_extract_visual_metadata()` runs.

### Visual Metadata

Extracted properties:

| Field | Source |
|---|---|
| `image_id` | supplied UUID or generated 8-hex |
| `filename` | `path.name`, which includes the UUID prefix after upload/inspect |
| `format` | Pillow `img.format` or extension fallback |
| `category` | always `visual_standard` |
| `modality` | `grayscale_single_band` for mode `L` or `1`; else `visual_standard` |
| `has_geospatial_metadata` | hard-coded `False` |
| `width`, `height` | Pillow `img.size` |
| `channels` | `len(img.getbands())` |
| `file_size_bytes` | `path.stat().st_size` |
| `acquisition_date` | EXIF `DateTime`, `DateTimeOriginal`, or `DateTimeDigitized`, if present |
| `geospatial` | hard-coded `None` |
| `visual.color_mode` | Pillow `img.mode` |
| `visual.channel_count` | Pillow bands count |
| `visual.bit_depth` | hard-coded `8` |

### GeoTIFF / Geospatial Metadata

Extracted properties:

| Field | Source |
|---|---|
| `format` | Rasterio `src.driver` |
| `category` | `geospatial_geotiff` |
| `width`, `height` | Rasterio `src.width`, `src.height` |
| `channels` | Rasterio `src.count` |
| `file_size_bytes` | filesystem stat |
| `geospatial.crs` | `src.crs.to_string()` |
| `geospatial.is_projected` | `src.crs.is_projected` |
| `bounds_native` | `src.bounds` |
| `bounds_wgs84` | `rasterio.warp.transform_bounds(src.crs, "EPSG:4326", *src.bounds)` |
| `resolution` | absolute `src.res`; unit from CRS linear units or `degree` |
| `bands[].band_index` | 1-based loop index |
| `bands[].data_type` | `src.dtypes[idx - 1]` |
| `bands[].nodata_value` | `src.nodatavals[idx - 1]` |
| `bands[].min/max/mean` | `src.read(idx, masked=True)` with NumPy stats |
| `acquisition_date` | Rasterio tags |
| `modality` | `_classify_geotiff_modality()` |

Acquisition date tag search:

- Dataset tags: `TIFFTAG_DATETIME`, `DATETIME`, `ACQUISITION_DATETIME`, `ACQUISITION_DATE`, `PROCESSING_DATETIME`, `IMAGE_DATE`, `SCENE_ACQUISITION_TIME`.
- Case-insensitive equivalent keys in dataset tags.
- Namespaces attempted: `TIFF`, `IMAGE_STRUCTURE`, `ENVI`.
- Filename is not used.
- User input is not used.

---

## 14. Zero-Fabrication / Non-Geospatial Safety

For JPG/PNG/BMP/WEBP visual images:

- `category = visual_standard`
- `modality = visual_standard` for RGB/RGBA/P/CMYK-style images
- `has_geospatial_metadata = false`
- `geospatial = null`
- no CRS
- no bounds
- no WGS84 bounds
- no resolution
- no spatial overlap eligibility

For `test3.jpg`, current behavior is:

- Valid JPG if Pillow can open it.
- Treated as ordinary `visual_standard`.
- Dimensions/channels/format extracted from Pillow.
- EXIF date may be extracted if present.
- No geographic coordinates are invented.
- Spatial APIs reject it with warnings that it lacks geospatial metadata.

---

## 15. Scene Classifier

Entry point:

```python
SceneClassifier.classify(images: List[UnifiedImageMetadata], session_id: str)
```

Outputs:

- `scene_config`
- `image_count`
- `image_ids`
- full image metadata list
- `temporal_relationship`
- `modality_relationship`
- `spatial_overview`
- `confidence`
- `messages`
- `warnings`

Rules:

| Input | Current result |
|---|---|
| empty collection | `unknown`, confidence `unverified`, message `No active images in session.` |
| one JPG | `single_image`, confidence `high`, message standard visual image loaded |
| one PNG | same as one JPG |
| one GeoTIFF | `single_image`, confidence `high`, message single georeferenced scene loaded |
| two JPG/PNG | `visual_pair_unreferenced`, confidence `medium` |
| two GeoTIFFs, one optical and one SAR | `optical_sar_pair`, confidence `high` |
| two GeoTIFFs with parsed timestamps and delta > 0.01 days | `bi_temporal_pair`, confidence `high` |
| two GeoTIFFs with same/near timestamp | `bi_temporal_pair`, confidence `medium` |
| two GeoTIFFs missing timestamps | `bi_temporal_pair`, confidence `medium`, timestamp warning |
| one GeoTIFF + one JPG/PNG | `heterogeneous_collection`, confidence `low` |
| three or more images | `multi_image`, confidence `medium`; warning if mixed georeferencing |

Filename patterns:

- Ignored for temporal classification.
- Ignored for modality classification.
- Used only indirectly in metadata `filename`, messages, storage names, and errors.

Evidence:

- Category: from validator/extractor.
- Modality: from band count and GeoTIFF tags/descriptions.
- Temporal: from metadata acquisition date fields only.
- Spatial overview: from `has_geospatial_metadata`, CRS strings, and x-resolution ratio.

---

## 16. Temporal Relationship Logic

Timestamp sources:

- Visual images: EXIF `DateTime`, `DateTimeOriginal`, `DateTimeDigitized`.
- GeoTIFFs: Rasterio metadata tags listed above.
- Not used: filename, file picker slot, user labels, upload order as a date source.

Parsing:

- TIFF standard `YYYY:MM:DD ...` is converted to `YYYY-MM-DD ...`.
- `Z` is converted to `+00:00`.
- `datetime.fromisoformat()` is attempted.
- Fallback formats include `%Y-%m-%d %H:%M:%S`, `%Y-%m-%dT%H:%M:%S`, `%Y-%m-%d`, `%Y/%m/%d %H:%M:%S`, `%Y/%m/%d`, `%d-%m-%Y`, `%d/%m/%Y`.

Behavior:

- For exactly two images with two parsed dates:
  - sets `earlier_image_id`
  - sets `later_image_id`
  - computes `time_delta_days`
  - stores raw timestamp strings in `timestamps`
- For non-two-image collections or fewer than two parsed dates:
  - `has_temporal_information=true` if at least one parseable date exists
  - earlier/later/delta are null

---

## 17. Modality Classification

Enum values in code:

- `optical_rgb`
- `optical_multispectral`
- `sar_radar`
- `grayscale_single_band`
- `visual_standard`
- `unknown`

Visual path:

- Modes `L` or `1` -> `grayscale_single_band`.
- All other standard visual modes -> `visual_standard`.
- Ordinary RGB JPG/PNG is not labeled as satellite optical imagery.

GeoTIFF path:

- SAR if tags or band descriptions contain any of:
  - `VV`
  - `VH`
  - `HH`
  - `HV`
  - `SAR`
  - `SENTINEL-1`
  - `POLARIZATION`
- Else band count >= 4 -> `optical_multispectral`.
- Else band count == 3 -> `optical_rgb`.
- Else band count == 1 -> `grayscale_single_band`.
- Else -> `unknown`.

SAR detection is heuristic and metadata-string based. It is not a full sensor-product parser.

---

## 18. Session Manager

Session data structure:

```text
SessionData
  session_id: str
  created_at: datetime UTC
  updated_at: datetime UTC
  images: Dict[str, UnifiedImageMetadata]
  file_paths: Dict[str, Path]
  session_dir: Path = backend/temp/cache/{session_id}
```

Manager state:

```text
SessionManager
  _sessions: Dict[str, SessionData]
```

Functions:

- `get_or_create_session(session_id=None)`: trims supplied ID or generates `uuid.uuid4().hex[:12]`; creates session if missing.
- `get_session(session_id)`: returns in-memory session or `None`.
- `add_image(session_id, file_path, metadata)`: registers metadata and file path; updates timestamp.
- `get_images(session_id)`: returns metadata list in insertion order.
- `get_image_file_path(session_id, image_id)`: returns cached file path.
- `delete_session(session_id)`: removes in-memory session and deletes session dir with `shutil.rmtree()`.
- `clear_all()`: clears in-memory session dict only; does not remove disk cache folders.

Disk storage:

- `/inspect`: `backend/temp/uploads`.
- `/upload` and `/upload-pair`: `backend/temp/cache/{session_id}`.
- `/spatial/align`: aligned artifact stored in same session cache dir and registered as another image.

After server restart:

- `_sessions` is empty.
- Existing cache/upload files remain on disk.
- Old sessions cannot be retrieved through `/api/v1/session/{session_id}`.
- Deleting an old disk-only session through API will return 404 because the session is not in memory.

---

## 19. Current JSON Contracts

### Metadata Schemas

- `ImageCategory`: `visual_standard`, `geospatial_geotiff`
- `SensorModality`: `optical_rgb`, `optical_multispectral`, `sar_radar`, `grayscale_single_band`, `visual_standard`, `unknown`
- `BoundingBoxNative`: `min_x`, `min_y`, `max_x`, `max_y` as floats
- `BoundingBoxWGS84`: `min_lon`, `min_lat`, `max_lon`, `max_lat` as floats
- `Resolution`: `x_resolution`, `y_resolution` floats; `unit` string
- `BandSummary`: `band_index` int, `data_type` string, optional numeric `nodata_value`, `min_value`, `max_value`, `mean_value`
- `GeospatialProfile`: CRS string, projected bool, native/WGS84 bounds, resolution, bands list, optional acquisition date
- `VisualProfile`: `color_mode` string, `channel_count` int, optional `bit_depth` int
- `UnifiedImageMetadata`: ID, filename, format, category, modality, geospatial flag, dimensions, channels, size, optional acquisition date, optional geospatial profile, optional visual profile
- `ValidationResult`: bool validity, category, error list, warning list
- `InspectResponse`: success bool, message string, validation object, optional metadata object

### Scene Schemas

- `SceneConfiguration`: `single_image`, `bi_temporal_pair`, `optical_sar_pair`, `visual_pair_unreferenced`, `multi_image`, `heterogeneous_collection`, `unknown`
- `TemporalRelationship`: temporal bool, optional earlier/later IDs, optional delta, timestamp map
- `ModalityRelationship`: multimodal bool, optical IDs, SAR IDs, visual IDs
- `SpatialCompatibilityOverview`: all-georeferenced bool, optional shared CRS bool, CRS list, optional resolution ratio, notes
- `SceneClassificationResult`: session ID, config, count, IDs, images, temporal, modality, spatial overview, confidence, messages, warnings
- `SessionStateResponse`: session ID, creation/update ISO strings, image count, classification

### Spatial Schemas

- `SpatialOverlapRequest`: session ID, image 1 ID, image 2 ID
- `SpatialOverlapResult`: overlap booleans/percentages, optional GeoJSON geometry, optional WGS84 bounds, optional sq km area, messages, warnings
- `AlignmentRequest`: session ID, reference image ID, target image ID, optional resampling method
- `AlignmentResult`: success, IDs, artifact filename, CRS strings, resolution list, dimensions, bands, dtype, resampling, message, optional aligned metadata
- `CompatibilityRequest`: session ID and two image IDs
- `CompatibilityResult`: overall compatible bool plus temporal, resolution, CRS, spatial, grid, recommendations, messages, warnings

Representative invalid file response:

```json
{
  "success": false,
  "message": "The uploaded file failed validation checks.",
  "validation": {
    "is_valid": false,
    "category": "visual_standard",
    "errors": ["Corrupted or unreadable visual image: ..."],
    "warnings": []
  },
  "metadata": null
}
```

Representative scene retrieval:

```json
{
  "session_id": "1bbcbc4de9fb",
  "scene_config": "visual_pair_unreferenced",
  "image_count": 2,
  "image_ids": ["22c189dd", "c165e02b"],
  "images": [],
  "temporal_relationship": {
    "has_temporal_information": false,
    "earlier_image_id": null,
    "later_image_id": null,
    "time_delta_days": null,
    "timestamps": {"22c189dd": null, "c165e02b": null}
  },
  "modality_relationship": {
    "is_multimodal": false,
    "optical_image_ids": [],
    "sar_image_ids": [],
    "visual_image_ids": ["22c189dd", "c165e02b"]
  },
  "spatial_overview": {
    "all_georeferenced": false,
    "shared_crs": null,
    "crs_list": [],
    "resolution_ratio": null,
    "notes": ["No geospatial CRS metadata available."]
  },
  "confidence": "medium",
  "messages": ["Two standard visual images loaded without embedded geospatial coordinates. Spatial overlap and physical alignment cannot be determined without geospatial reference."],
  "warnings": []
}
```

Note: the `images` array is populated in actual responses; it is omitted above only to keep the example readable.

---

## 20. Data Types

Numeric values remain numeric:

- widths, heights, channel counts, band indexes, and file sizes are integers.
- bounds, resolutions, percentages, area, min/max/mean, and deltas are floats.
- boolean flags are booleans.
- nullable missing values are JSON `null`.
- IDs, filenames, CRS strings, labels, enum values, units, timestamps, and messages are strings.
- image lists, error lists, warning lists, and recommendations are arrays.
- metadata, geospatial profile, visual profile, and classification payloads are objects.

This is correct because identifiers and labels are symbolic values, while dimensions/statistics/areas are arithmetic values consumed by maps, charts, tools, and future agents.

---

## 21. Frontend Contract - Shankar

Upload one or many files:

- Use `POST /api/v1/ingest/upload`.
- Send `multipart/form-data`.
- Repeat field name `files` for each selected image.
- Store returned `session_id` client-side.
- To append more files, send the same `session_id` as a form field.

Two-slot upload UI:

- Use `POST /api/v1/ingest/upload-pair`.
- Send `file_1` and `file_2`.
- Keep in mind slots do not create before/after semantics.

Image preview:

- Use `classification.images[]`.
- `image_id` identifies the backend image.
- `filename`, `width`, `height`, `format`, `category`, `modality`, and `visual` profile support UI labels.
- No endpoint currently serves file bytes/previews by image ID.

Map usage:

- Use only `image.geospatial.bounds_wgs84` for map `fitBounds`.
- Use `min_lon`, `min_lat`, `max_lon`, `max_lat`.
- Do not use visual images on a map unless `has_geospatial_metadata=true`.
- `intersection_geojson` from `/api/v1/spatial/overlap` can be drawn as a GeoJSON geometry.

Session:

- Persist `session_id` in frontend state.
- Re-fetch `/api/v1/session/{session_id}` after uploads or spatial operations.
- Alignment creates a new registered image/artifact in the same session.

Errors:

- `/inspect` invalid file -> HTTP 422 with structured `validation.errors`.
- `/upload` invalid file -> current behavior is silent skip and HTTP 200; frontend should compare selected count to returned `image_count` delta until backend adds per-file errors.
- session not found -> HTTP 404 with `detail`.

GeoJSON:

- Implemented today only for spatial overlap intersection polygon.
- Raster mask to GeoJSON is future work.

---

## 22. AI Agent Contract - Bhanu

Implemented and consumable today:

- Full `UnifiedImageMetadata` for every registered valid image.
- Scene classification including config, confidence, messages, warnings.
- Temporal relationship derived from metadata timestamps.
- Modality relationship with optical/SAR/visual image IDs.
- Spatial overview with CRS list and resolution ratio.
- Deterministic tool functions:
  - `check_spatial_overlap(session_id, image_id_1, image_id_2)`
  - `check_compatibility(session_id, image_id_1, image_id_2)`
  - `align_images(session_id, reference_image_id, target_image_id, resampling_method="bilinear")`
- REST equivalents for those tools under `/api/v1/spatial/*`.

Partial:

- Spatial overlap is bounding-box based, not true raster footprint/mask overlap.
- Geodesic area exists only for the overlap intersection polygon.
- Compatibility gives recommendations but does not execute a full analysis pipeline.
- Alignment creates artifacts but there is no separate artifact registry schema.

Not implemented:

- AI-agent orchestration.
- LLM/VLM tool-calling runtime.
- Cloud masking, seasonal filtering, mask vectorization, zonal statistics.
- Image-byte retrieval endpoint.
- Persistent session storage for multi-process/multi-restart agents.

Future agent workflow, clearly future:

```text
user query
  -> agent reads session classification + metadata
  -> agent chooses deterministic backend tools
  -> backend computes alignment/overlap/compatibility/cloud/mask/stat outputs
  -> agent explains results in natural language
```

---

## 23. Current Python Tool Interface

| Function | Exists? | Location | Signature | Implemented | Tested | REST equivalent | Limitation |
|---|---:|---|---|---:|---:|---|---|
| `validate_and_ingest_image()` | No | none | n/a | No | No | closest: `/ingest/inspect`, `/ingest/upload` | not a single exported function |
| `classify_scene_payload()` | No | none | n/a | No | No | closest: `/session/{id}/scene` | use `SceneClassifier.classify()` |
| `check_spatial_overlap()` | Yes | `backend/app/pipeline/overlap.py` | `(session_id: str, image_id_1: str, image_id_2: str) -> SpatialOverlapResult` | Yes | Yes | `/api/v1/spatial/overlap` | bbox overlap only |
| `check_compatibility()` | Yes | `backend/app/pipeline/compatibility.py` | `(session_id: str, image_id_1: str, image_id_2: str) -> CompatibilityResult` | Yes | Yes | `/api/v1/spatial/compatibility` | requires registered session images |
| `align_images()` | Yes | `backend/app/pipeline/alignment.py` | `(session_id: str, reference_image_id: str, target_image_id: str, resampling_method: str = "bilinear") -> AlignmentResult` | Yes | Yes | `/api/v1/spatial/align` | raster-only; registers aligned artifact as image |
| `detect_clouds_and_shadows()` | No | none | n/a | No | No | none | Task 21 absent |
| `mask_to_geojson()` | No | none | n/a | No | No | none | Task 23 absent |
| `calculate_spatial_statistics()` | No | none | n/a | No | No | none | Task 25 absent |

---

## 24. Current REST API Vs Planned REST API

| Capability | Current endpoint | Current status |
|---|---|---|
| Image inspection | `POST /api/v1/ingest/inspect` | Implemented |
| Session upload | `POST /api/v1/ingest/upload` | Implemented |
| Explicit pair upload | `POST /api/v1/ingest/upload-pair` | Implemented in dirty working tree |
| Session retrieval | `GET /api/v1/session/{session_id}` | Implemented |
| Scene retrieval | `GET /api/v1/session/{session_id}/scene` | Implemented |
| Session deletion | `DELETE /api/v1/session/{session_id}` | Implemented |
| Spatial overlap | `POST /api/v1/spatial/overlap` | Implemented; bbox-level |
| CRS/grid alignment | `POST /api/v1/spatial/align` | Implemented |
| Compatibility | `POST /api/v1/spatial/compatibility` | Implemented |
| Cloud masking | none | Not implemented |
| Seasonal filtering | none | Not implemented |
| Raster mask vectorization | none | Not implemented |
| Standalone geodesic area | none | Partial only inside overlap |
| Zonal/spatial statistics | none | Not implemented |

---

## 25. Task 1-7 Audit

| Task | Requirement | Actual implementation | Files/functions | Tests | Status | Missing pieces |
|---|---|---|---|---|---|---|
| Task 1 - Dual-path ingestion | accept visual and geospatial imagery safely | Pillow path and Rasterio path implemented | `validator.py`, `ingest.py` | validator/API tests | IMPLEMENTED | upload per-file error reporting, stronger extension/MIME policy |
| Task 2 - Metadata extraction | structured image/raster metadata | visual and GeoTIFF metadata implemented | `metadata.py`, schemas | metadata/API tests | IMPLEMENTED | true visual bit-depth detection, large-raster stats strategy |
| Task 3 - Scene/modality classification | classify single/pair/multi/modality/temporal state | deterministic classifier implemented | `scene_classifier.py` | scene/session tests | IMPLEMENTED | richer product metadata parsing |
| Task 4 - CRS alignment/reprojection | align target raster to reference CRS/grid | Rasterio `reproject()` artifact creation implemented | `alignment.py`, `/spatial/align` | alignment/spatial API tests | IMPLEMENTED | no crop-to-overlap option, no separate artifact model |
| Task 5 - Spatial overlap/intersection | determine spatial overlap | WGS84 bounding-box intersection and GeoJSON implemented | `overlap.py`, `/spatial/overlap` | overlap/spatial API tests | PARTIAL | not true raster footprint/pixel mask overlap |
| Task 6 - Resolution/temporal compatibility | evaluate if scenes can be compared | temporal, resolution, CRS, overlap, grid synthesis implemented | `compatibility.py` | compatibility/spatial API tests | IMPLEMENTED | heuristic thresholds only |
| Task 7 - Session/artifact cache | maintain images and artifacts | in-memory sessions + disk cache + deletion implemented | `session_cache.py` | session/alignment tests | PARTIAL | no persistence, no restart recovery, artifacts are just images, no cleanup scheduler |

---

## 26. Task 21-25 Audit

| Task | Requirement | Actual implementation | Files/functions | Tests | Status | Missing pieces |
|---|---|---|---|---|---|---|
| Task 21 - Cloud & Shadow Masking | detect cloud/shadow pixels | none | none | none | NOT IMPLEMENTED | module, schema, endpoint, tests |
| Task 22 - Seasonal False Positive Filtering | reduce seasonal noise | none | none | none | NOT IMPLEMENTED | temporal/seasonal logic, inputs, tests |
| Task 23 - Raster Mask -> GeoJSON | vectorize masks | none | none | none | NOT IMPLEMENTED | `mask_to_geojson()`, endpoint, schema, tests |
| Task 24 - Geodesic Area Calculation | calculate geodesic areas | only overlap intersection area via `pyproj.Geod.geometry_area_perimeter()` | `overlap.py` | overlap tests indirectly | PARTIAL | no standalone arbitrary polygon/mask area API |
| Task 25 - Zonal & Spatial Statistics | statistics over zones/masks | metadata per-band min/max/mean only | `metadata.py` | metadata tests | NOT IMPLEMENTED | zonal stats engine, schemas, endpoints, tests |

Metadata band statistics are not full spatial/zonal statistics.

---

## 27. Test Suite Audit

Command run:

```text
D:\SIH 2026\SatQuery AI\backend\venv\Scripts\python.exe -m pytest -v
```

Observed result:

- Collected: 46 tests
- Passed: 46
- Failed: 0
- Skipped: 0
- Warnings: 5
- Time: 1.25s
- Platform: Windows, Python 3.14.3, pytest 9.1.1

Warnings:

- Starlette/FastAPI TestClient warning about `httpx` deprecation and `httpx2`.
- Starlette deprecation warning for `HTTP_422_UNPROCESSABLE_ENTITY`.
- Rasterio `NotGeoreferencedWarning` in no-CRS TIFF fixture.

Test groups:

- `test_validator.py`: valid GeoTIFF/JPEG/PNG, no-CRS TIFF fallback, nonexistent file, corrupted file.
- `test_metadata.py`: GeoTIFF metadata, JPG metadata, PNG metadata, zero geospatial fabrication.
- `test_api.py`: root, health, inspect GeoTIFF/JPEG/PNG, invalid text, corrupted image.
- `test_scene_classifier.py`: single JPG/PNG/GeoTIFF, bitemporal pair, optical/SAR, two visual images, heterogeneous pair, multi-image, empty session.
- `test_session_api.py`: upload single, upload bitemporal pair, explicit pair endpoint, session retrieval, scene retrieval, delete.
- `test_overlap.py`: identical, partial, zero, different CRS overlap, visual rejection.
- `test_alignment.py`: same CRS, different CRS, different resolution alignment, visual rejection.
- `test_compatibility.py`: valid pair, different CRS, no overlap, JPG rejection.
- `test_spatial_api.py`: REST overlap, compatibility, align endpoints.

---

## 28. Real End-To-End API Testing

A TestClient E2E script generated real JPG, PNG, GeoTIFF, corrupted image, and text file inputs, then exercised the API.

| Test | Request | Observed status | Observed behavior |
|---|---|---:|---|
| JPG inspect | `POST /api/v1/ingest/inspect` field `file=photo.jpg` | 200 | `success=true`, `category=visual_standard`, `modality=visual_standard`, no geospatial metadata |
| PNG inspect | `POST /api/v1/ingest/inspect` field `file=graphic.png` | 200 | `success=true`, `channels=4`, no geospatial metadata |
| GeoTIFF inspect | `POST /api/v1/ingest/inspect` field `file=scene1.tif` | 200 | `category=geospatial_geotiff`, `modality=optical_multispectral`, geospatial metadata present |
| corrupted image | `POST /api/v1/ingest/inspect` field `file=corrupt.jpg` | 422 | validation error from Pillow |
| unsupported file | `POST /api/v1/ingest/inspect` field `file=notes.txt` | 422 | validation error from Rasterio fallback |
| single upload | `POST /api/v1/ingest/upload` one `files` part | 200 | new session, `image_count=1`, `single_image` |
| multiple upload | `POST /api/v1/ingest/upload` two GeoTIFF `files` parts | 200 | new session, `image_count=2`, `bi_temporal_pair`, 184-day interval |
| repeated upload same session | `POST /api/v1/ingest/upload` with prior `session_id` | 200 | appended image, reclassified as `visual_pair_unreferenced` |
| session retrieval | `GET /api/v1/session/{session_id}` | 200 | session state returned |
| scene retrieval | `GET /api/v1/session/{session_id}/scene` | 200 | classification-only payload returned |
| session deletion | `DELETE /api/v1/session/{session_id}` | 200 | success message |
| retrieval after deletion | `GET /api/v1/session/{session_id}` | 404 | session not found |

---

## 29. Dependency Audit

Requirements file uses lower bounds, not exact pins:

| Requirement | Installed version observed | Purpose | Used by |
|---|---:|---|---|
| `fastapi>=0.110.0` | 0.141.1 | API framework, routing, UploadFile, schemas | `main.py`, endpoints, tests |
| `uvicorn[standard]>=0.28.0` | 0.52.4 | ASGI dev/prod server | runtime command; not imported by app |
| `pydantic>=2.6.0` | 2.13.4 | response/request models and validation | all schema modules |
| `python-multipart>=0.0.9` | 0.0.32 | multipart form/file parsing | FastAPI upload endpoints |
| `Pillow>=10.2.0` | 12.3.0 | visual image validation/metadata/test images | `validator.py`, `metadata.py`, fixtures |
| `rasterio>=1.3.9` | 1.5.1 | raster validation, metadata, reprojection | validator, metadata, alignment, compatibility, fixtures |
| `pyproj>=3.6.1` | 3.7.2 | geodesic area | `overlap.py` |
| `shapely>=2.0.0` | 2.1.2 | bbox polygons/intersection/GeoJSON mapping | `overlap.py` |
| `numpy>=1.26.0` | 2.5.2 | band stats and synthetic raster fixtures | `metadata.py`, tests |
| `pytest>=8.0.0` | 9.1.1 | test runner | tests |
| `httpx>=0.27.0` | 0.28.1 | FastAPI TestClient dependency | tests |

Not present in `requirements.txt`: GeoPandas.

---

## 30. Performance / Limitations

Actual limitations:

- GeoTIFF band statistics read full bands into memory (`src.read(idx, masked=True)`), which can be expensive for large rasters.
- `/inspect` and `/upload` write files synchronously inside async endpoints.
- No max file size setting.
- No streaming stats/windowed overview strategy.
- Session state is in-memory only.
- Disk temp/cache files can accumulate.
- `clear_all()` used in tests clears memory only, not disk.
- Spatial overlap uses WGS84 bounding boxes, not true valid-data footprint or pixel masks.
- Alignment outputs full reference-grid raster and does not clip to overlap.
- No concurrency locks around global `session_manager`.
- Multi-user isolation is only by session ID; no authentication.
- No production CORS restriction; `allow_origins=["*"]`.

---

## 31. Security / Robustness Audit

Implemented protections:

- File existence and empty-file checks.
- Pillow integrity verification for visual images.
- Rasterio open/CRS/transform/dimension/band checks for rasters.
- No geospatial fabrication for JPG/PNG.
- Corrupted images return structured validation errors in `/inspect`.
- Session delete removes cache directory for known in-memory sessions.
- Image IDs are generated server-side.

Not yet protected:

- No upload size limit.
- MIME type is not trusted or enforced; behavior is extension/content-reader based.
- Original filename is used inside generated filename without robust basename/path sanitization.
- Supplied `session_id` is accepted as a path segment for cache directory creation without strict character validation.
- Invalid files in `/upload` are silently skipped and left on disk.
- `/inspect` temp files are never cleaned up.
- No authentication/authorization.
- No rate limiting.
- No virus/malware scanning.
- No protection against oversized rasters consuming memory during stats extraction.
- No explicit multi-process/session persistence story.

---

## 32. Git Status

Commands inspected:

- `git status --short --branch`
- `git log -1 --decorate --oneline`
- `git log -1 --pretty=format:%H%n%s%n%ci`
- `git remote -v`
- `git rev-parse --abbrev-ref --symbolic-full-name '@{u}'`
- `git rev-list --left-right --count 'HEAD...@{u}'`

Current branch:

- `main`
- Upstream: `origin/main`
- Ahead/behind: `0 0`

Latest commit:

- Hash: `f76eef752d4c57601cf8c7715c565ade3c8febae`
- Short: `f76eef7`
- Message: `feat(spatial): implement spatial overlap, CRS grid alignment, and compatibility engines`
- Date: `2026-08-28 19:53:04 +0530`

Remote:

- `origin https://github.com/trushendarreddy-cell/SatQuery-AI.git`

Working tree:

```text
 M backend/app/api/v1/endpoints/ingest.py
 M backend/app/main.py
 M backend/tests/test_session_api.py
```

Meaning:

- HEAD is pushed/even with `origin/main`.
- The current working tree has uncommitted local modifications.
- Those modifications include the current `/upload-pair` endpoint, OpenAPI file-picker patch, and new explicit pair test.
- No commit or push was performed for this audit.

---

## 33. Current Architecture Diagram

Implemented today:

```text
Frontend
  -> FastAPI app (`app/main.py`)
    -> API v1 router
      -> Ingest endpoints
        -> UniversalImageValidator
        -> UniversalMetadataExtractor
        -> SessionManager
        -> SceneClassifier
      -> Session endpoints
        -> SessionManager
        -> SceneClassifier
      -> Spatial endpoints
        -> SpatialOverlapEngine
        -> CompatibilityEngine
        -> GridAlignmentEngine
  -> JSON responses
```

Current storage:

```text
backend/temp/uploads
  -> inspected files, not session-registered

backend/temp/cache/{session_id}
  -> uploaded session images
  -> aligned raster artifacts
```

Future/not implemented:

```text
Task 21 Cloud/shadow masking
Task 22 Seasonal filtering
Task 23 Mask -> GeoJSON
Task 24 Standalone geodesic area
Task 25 Zonal/spatial statistics
```

---

## 34. Complete User Journeys

### Scenario A - Normal JPG

User uploads `photo.jpg`. Backend writes it to temp/cache or uploads folder, validates with Pillow, extracts dimensions/channels/format/EXIF date if present, sets `category=visual_standard`, sets `has_geospatial_metadata=false`, returns metadata. In session upload, classifier returns `single_image` if it is the only image.

### Scenario B - PNG

Same visual path as JPG. RGBA PNG reports 4 channels and visual profile `color_mode=RGBA`. No coordinates are created.

### Scenario C - Satellite GeoTIFF

Backend routes `.tif`/`.tiff` to Rasterio, validates CRS, transform, dimensions, and bands, extracts native/WGS84 bounds, resolution, bands, optional date tags, and modality. Single upload is `single_image`; maps can use `bounds_wgs84`.

### Scenario D - Two ordinary JPGs

Both become `visual_standard`. Classifier returns `visual_pair_unreferenced`. The backend does not assume before/after, spatial overlap, or physical alignment.

### Scenario E - Two GeoTIFF satellite scenes

Both are registered with geospatial profiles. Classifier can return `bi_temporal_pair` if timestamps support it. `/spatial/overlap` can compute bbox intersection. `/spatial/compatibility` can recommend alignment. `/spatial/align` can produce a registered aligned raster.

### Scenario F - Optical + SAR

Optical is inferred from 3 or 4+ bands. SAR is inferred from SAR/polarization tags/descriptions. If exactly one optical and one SAR image are present, classifier returns `optical_sar_pair`. Detection remains heuristic.

### Scenario G - Additional Image Added To Existing Session

Frontend sends `session_id` with another `/upload`. Backend appends valid images to the existing in-memory session, updates `updated_at`, reruns classification across all images, and returns the updated state.

---

## 35. What Is Actually Ready For The Team

### Ready For Shankar

- `/api/v1/ingest/inspect` for one-file preflight inspection.
- `/api/v1/ingest/upload` for real session uploads.
- `/api/v1/ingest/upload-pair` for two-slot UI, noting it is currently uncommitted.
- `/api/v1/session/{session_id}` for session reload.
- `/api/v1/session/{session_id}/scene` for classification-only state.
- `/api/v1/spatial/overlap` for overlap polygon/bounds/percentages.
- `/api/v1/spatial/compatibility` for "can these scenes be compared?" UI.
- `/api/v1/spatial/align` for backend-generated aligned artifact.
- Use `bounds_wgs84` only when `has_geospatial_metadata=true`.

### Ready For Bhanu

- Session metadata and classification payloads.
- Deterministic function calls for overlap, compatibility, and alignment.
- A safe rule that visual images are not geospatial.
- A clear distinction between implemented deterministic tools and future AI/VLM tools.

### Still Being Built By Rushendar

- Per-file upload error contract.
- Session persistence/restart recovery.
- Temp/cache cleanup strategy.
- Cloud/shadow masking.
- Seasonal filtering.
- Mask vectorization.
- Standalone geodesic area APIs.
- Zonal/spatial statistics.
- Agent-facing orchestration layer.

---

## 36. Duplication / Architecture Risks

Potential duplication traps:

- Frontend should not parse GeoTIFF CRS/bounds; backend already does it.
- AI agent should not independently parse raster metadata; use session metadata and deterministic tools.
- Do not build separate upload logic for pair workflows; `/upload` and `/upload-pair` already share behavior.
- Do not duplicate scene classification in frontend; use `classification.scene_config`.
- Do not duplicate spatial overlap logic in agent; call `/spatial/overlap` or `check_spatial_overlap()`.
- Do not treat visual JPG/PNG as satellite geospatial imagery without a future georeferencing process.
- Do not confuse metadata band min/max/mean with Task 25 zonal statistics.

Recommendation:

Keep `metadata_schema.py`, `scene_schema.py`, and `spatial_schema.py` as the contract source of truth. Shankar and Bhanu should consume these JSON shapes instead of inventing parallel models.

---

## 37. Exact Next Milestone

Highest-value next milestone: make session upload validation and cache behavior production-safe before adding Tasks 21-25.

Why:

- Current ingestion works, but `/upload` silently skips invalid files.
- Shankar needs reliable per-file UI errors.
- Bhanu needs trustworthy session state with no hidden missing inputs.
- Future cloud/mask/stat tools will depend on stable image/session contracts.

Recommended scope:

Files to modify:

- `backend/app/api/v1/endpoints/ingest.py`
- `backend/app/core/session_cache.py`
- `backend/app/schemas/scene_schema.py` or a new upload response schema
- `backend/tests/test_session_api.py`

Possible files to create:

- `backend/app/schemas/ingest_schema.py` for per-file upload results
- `backend/tests/test_upload_validation_contract.py`

APIs to add or adjust:

- Preserve `/api/v1/ingest/upload`.
- Add per-file results such as accepted/skipped/error reason.
- Consider rejecting all-invalid uploads with HTTP 422.
- Add strict `session_id` validation.
- Sanitize filenames with basename/slug logic.

Tests to add:

- one valid + one invalid upload returns accepted valid file and reports invalid file.
- all-invalid upload returns explicit failure.
- malicious filename cannot escape cache/upload dirs.
- bad `session_id` is rejected.
- append-to-session keeps old images and reports only new per-file results.

Connection to Shankar:

- UI can show exactly which file failed and why.
- Upload progress/results become predictable.

Connection to Bhanu:

- Agent can trust `image_count` and per-file ingestion outcomes.
- Future tools will not operate on accidentally skipped inputs.

Do not start Tasks 21-25 until this ingestion/session contract is hardened.

---

## 38. Final Status Dashboard

| Area | Status |
|---|---|
| JPG/PNG ingestion | GREEN - implemented |
| BMP/WEBP visual ingestion | GREEN - code-supported through Pillow extensions, lightly tested indirectly/not specifically covered |
| GeoTIFF ingestion | GREEN - implemented and tested |
| COG ingestion | YELLOW - likely supported as Rasterio-readable TIFF, not explicitly detected/tested |
| Metadata extraction | GREEN - implemented |
| Scene classification | GREEN - implemented |
| Sessions | YELLOW - implemented in memory, no persistence/restart recovery |
| Frontend contract | GREEN - usable today with noted upload error caveat |
| AI-agent contract | YELLOW - deterministic tools ready, no agent runtime |
| CRS alignment | GREEN - implemented |
| Spatial overlap | YELLOW - implemented as WGS84 bbox overlap, not true raster footprint |
| Resolution/temporal compatibility | GREEN - implemented |
| Cloud masking | RED - not implemented |
| Seasonal filtering | RED - not implemented |
| Raster mask GeoJSON | RED - not implemented |
| Geodesic area | YELLOW - overlap area only, no standalone task tool |
| Zonal statistics | RED - not implemented |
| Upload security hardening | YELLOW - basic validation exists, size/name/session protections missing |

---

## 39. Accuracy Notes

- This report does not treat README claims as authoritative where code has moved ahead.
- `/upload-pair` is real in the current working tree but not committed.
- All endpoints listed above are mounted in the inspected OpenAPI paths.
- Tests were actually run and passed.
- API behavior was exercised with TestClient and generated real files.
- No production code was changed for this audit; this Markdown file is the audit artifact.

import uuid
from typing import Any, Dict, List, Optional

from app.agent.schemas import AgentToolCall, AgentToolResult, ToolDefinition, ToolStatus
from app.core.session_cache import session_manager
from app.pipeline.validator import UniversalImageValidator
from app.pipeline.metadata import UniversalMetadataExtractor
from app.pipeline.scene_classifier import SceneClassifier
from app.pipeline.overlap import check_spatial_overlap
from app.pipeline.compatibility import check_compatibility
from app.pipeline.alignment import align_images
from app.pipeline.clip import clip_to_common_extent
from app.pipeline.analysis import (
    compute_spectral_index,
    detect_clouds_and_shadows,
    filter_seasonal_false_positives,
    mask_to_geojson,
    calculate_spatial_area,
    calculate_spatial_statistics,
)
from app.pipeline.change_detection import run_change_detection
from app.schemas.metadata_schema import ImageCategory


_TOOL_DEFINITIONS: List[ToolDefinition] = []


def _register(name: str, description: str, purpose: str, input_schema: Dict[str, Any],
              output_schema: Dict[str, Any], required: List[str], failures: List[str]):
    _TOOL_DEFINITIONS.append(ToolDefinition(
        name=name, description=description, purpose=purpose,
        input_schema=input_schema, output_schema=output_schema,
        required_parameters=required, failure_conditions=failures,
    ))


def get_tool_registry() -> List[ToolDefinition]:
    return list(_TOOL_DEFINITIONS)


def find_tool_definition(name: str) -> Optional[ToolDefinition]:
    for t in _TOOL_DEFINITIONS:
        if t.name == name:
            return t
    return None


def validate_and_ingest_image(session_id: str, file_path: str) -> Dict[str, Any]:
    session = session_manager.get_or_create_session(session_id)
    path = __import__("pathlib").Path(file_path)
    if not path.exists():
        return {"success": False, "session_id": session_id, "image_id": "", "message": f"File not found: {file_path}", "warnings": []}
    validation = UniversalImageValidator.validate(path)
    if not validation.is_valid:
        return {"success": False, "session_id": session_id, "image_id": "", "message": "Validation failed", "warnings": validation.errors, "validation": validation.model_dump()}
    image_id = uuid.uuid4().hex[:8]
    metadata = UniversalMetadataExtractor.extract(path, category=validation.category, image_id=image_id, compute_stats=True)
    session_manager.add_image(session_id, path, metadata)
    return {"success": True, "session_id": session_id, "image_id": image_id, "message": "Image validated and ingested.", "warnings": validation.warnings, "metadata": metadata.model_dump(), "validation": validation.model_dump()}


def get_image_metadata(session_id: str, image_id: str) -> Dict[str, Any]:
    session = session_manager.get_session(session_id)
    if not session:
        return {"success": False, "session_id": session_id, "image_id": image_id, "message": f"Session '{session_id}' not found.", "metadata": None, "warnings": []}
    meta = session.images.get(image_id)
    if not meta:
        return {"success": False, "session_id": session_id, "image_id": image_id, "message": f"Image '{image_id}' not found.", "metadata": None, "warnings": []}
    return {"success": True, "session_id": session_id, "image_id": image_id, "message": "Metadata retrieved.", "metadata": meta.model_dump(), "warnings": []}


def classify_scene(session_id: str) -> Dict[str, Any]:
    session = session_manager.get_session(session_id)
    if not session:
        return {"success": False, "session_id": session_id, "message": f"Session '{session_id}' not found.", "classification": None, "warnings": []}
    images = session_manager.get_images(session_id)
    result = SceneClassifier.classify(images, session_id)
    return {"success": True, "session_id": session_id, "message": "Scene classified.", "classification": result.model_dump(), "warnings": []}


def check_spatial_overlap_tool(session_id: str, image_id_1: str, image_id_2: str) -> Dict[str, Any]:
    result = check_spatial_overlap(session_id, image_id_1, image_id_2)
    return {"success": result.overlap_exists, "session_id": session_id, "message": result.messages[0] if result.messages else result.warnings[0] if result.warnings else "", "overlap": result.model_dump(), "warnings": result.warnings}


def check_compatibility_tool(session_id: str, image_id_1: str, image_id_2: str) -> Dict[str, Any]:
    result = check_compatibility(session_id, image_id_1, image_id_2)
    return {"success": result.compatible, "session_id": session_id, "message": result.messages[0] if result.messages else result.warnings[0] if result.warnings else "", "compatibility": result.model_dump(), "warnings": result.warnings}


def align_images_tool(session_id: str, reference_image_id: str, target_image_id: str, resampling_method: str = "bilinear") -> Dict[str, Any]:
    result = align_images(session_id, reference_image_id, target_image_id, resampling_method)
    return {"success": result.success, "session_id": session_id, "message": result.message, "alignment": result.model_dump(), "warnings": []}


def clip_images_tool(session_id: str, image_id_1: str, image_id_2: str, resampling_method: str = "bilinear") -> Dict[str, Any]:
    result = clip_to_common_extent(session_id, image_id_1, image_id_2, resampling_method)
    return {"success": result.success, "session_id": session_id, "message": result.message, "clip": result.model_dump(), "warnings": result.warnings}


def detect_clouds_and_shadows_tool(session_id: str, image_id: str) -> Dict[str, Any]:
    result = detect_clouds_and_shadows(session_id, image_id)
    return {"success": result.success, "session_id": session_id, "message": result.message, "cloud_mask": result.model_dump(), "warnings": result.warnings}


def apply_seasonal_filter_tool(session_id: str, image_id_1: str, image_id_2: str, mask_image_id: Optional[str] = None) -> Dict[str, Any]:
    result = filter_seasonal_false_positives(session_id, image_id_1, image_id_2, mask_image_id)
    return {"success": result.success, "session_id": session_id, "message": result.message, "seasonal_filter": result.model_dump(), "warnings": result.warnings}


def mask_to_geojson_tool(session_id: str, image_id: str, band_index: int = 1, min_value: float = 1.0) -> Dict[str, Any]:
    result = mask_to_geojson(session_id, image_id, band_index, min_value)
    return {"success": result.success, "session_id": session_id, "message": result.message, "geojson": result.model_dump(), "warnings": result.warnings}


def calculate_spatial_statistics_tool(session_id: str, image_id: str, mask_image_id: Optional[str] = None, geometry: Optional[Dict[str, Any]] = None, band_index: Optional[int] = None) -> Dict[str, Any]:
    result = calculate_spatial_statistics(session_id, image_id, mask_image_id, geometry, band_index)
    return {"success": result.success, "session_id": session_id, "message": result.message, "zonal_stats": result.model_dump(), "warnings": result.warnings}


def calculate_area_tool(geojson: Dict[str, Any]) -> Dict[str, Any]:
    result = calculate_spatial_area(geojson)
    return {"success": result.success, "message": result.message, "area": result.model_dump(), "warnings": result.warnings}


def compute_spectral_index_tool(session_id: str, image_id: str, index_type: str = "ndvi", red_band: int = 3, nir_band: int = 4, blue_band: Optional[int] = None, green_band: Optional[int] = None, swir_band: Optional[int] = None, savi_l_factor: Optional[float] = 0.5) -> Dict[str, Any]:
    from app.schemas.analysis_schema import SpectralIndexType
    itype = SpectralIndexType(index_type.lower())
    result = compute_spectral_index(session_id, image_id, itype, red_band, nir_band, blue_band, green_band, swir_band, savi_l_factor)
    return {"success": result.success, "session_id": session_id, "message": result.message, "spectral_index": result.model_dump(), "warnings": result.warnings}


def run_change_detection_tool(session_id: str, image_id_1: str, image_id_2: str, threshold: float = 0.1, threshold_method: str = "relative_normalized", band_index: Optional[int] = None, resampling_method: str = "bilinear") -> Dict[str, Any]:
    from app.schemas.change_detection_schema import ChangeDetectionRequest, ChangeDetectionMethod
    method = ChangeDetectionMethod(threshold_method.lower())
    payload = ChangeDetectionRequest(
        session_id=session_id,
        image_id_1=image_id_1,
        image_id_2=image_id_2,
        threshold=threshold,
        threshold_method=method,
        band_index=band_index,
        resampling_method=resampling_method,
    )
    result = run_change_detection(payload)
    return {"success": result.success, "session_id": session_id, "message": result.message, "change_detection": result.model_dump(), "warnings": result.warnings}


def invoke_agent_tool(payload: AgentToolCall) -> AgentToolResult:
    name = payload.tool_name
    args = dict(payload.arguments)
    tool_map = {
        "validate_and_ingest_image": lambda: validate_and_ingest_image(args.get("session_id", ""), args.get("file_path", "")),
        "get_image_metadata": lambda: get_image_metadata(args.get("session_id", ""), args.get("image_id", "")),
        "classify_scene": lambda: classify_scene(args.get("session_id", "")),
        "check_spatial_overlap": lambda: check_spatial_overlap_tool(args.get("session_id", ""), args.get("image_id_1", ""), args.get("image_id_2", "")),
        "check_compatibility": lambda: check_compatibility_tool(args.get("session_id", ""), args.get("image_id_1", ""), args.get("image_id_2", "")),
        "align_images": lambda: align_images_tool(args.get("session_id", ""), args.get("reference_image_id", ""), args.get("target_image_id", ""), args.get("resampling_method", "bilinear")),
        "clip_images": lambda: clip_images_tool(args.get("session_id", ""), args.get("image_id_1", ""), args.get("image_id_2", ""), args.get("resampling_method", "bilinear")),
        "detect_clouds_and_shadows": lambda: detect_clouds_and_shadows_tool(args.get("session_id", ""), args.get("image_id", "")),
        "apply_seasonal_filter": lambda: apply_seasonal_filter_tool(args.get("session_id", ""), args.get("image_id_1", ""), args.get("image_id_2", ""), args.get("mask_image_id")),
        "mask_to_geojson": lambda: mask_to_geojson_tool(args.get("session_id", ""), args.get("image_id", ""), int(args.get("band_index", 1)), float(args.get("min_value", 1.0))),
        "calculate_spatial_statistics": lambda: calculate_spatial_statistics_tool(args.get("session_id", ""), args.get("image_id", ""), args.get("mask_image_id"), args.get("geometry"), args.get("band_index")),
        "calculate_area": lambda: calculate_area_tool(args.get("geojson", {})),
        "compute_spectral_index": lambda: compute_spectral_index_tool(args.get("session_id", ""), args.get("image_id", ""), args.get("index_type", "ndvi"), int(args.get("red_band", 3)), int(args.get("nir_band", 4))),
        "run_change_detection": lambda: run_change_detection_tool(args.get("session_id", ""), args.get("image_id_1", ""), args.get("image_id_2", ""), float(args.get("threshold", 0.1)), args.get("threshold_method", "relative_normalized"), args.get("band_index"), args.get("resampling_method", "bilinear")),
    }
    func = tool_map.get(name)
    if not func:
        return AgentToolResult(tool_name=name, status=ToolStatus.FAILURE, result={}, message=f"Unknown tool: {name}", warnings=[], error=f"Tool '{name}' is not registered.")
    try:
        output = func()
        status = ToolStatus.SUCCESS if output.get("success") else ToolStatus.FAILURE
        error = output.get("error") if not output.get("success") else None
        if status == ToolStatus.FAILURE and error is None:
            error = output.get("message", "Tool execution failed.")
        return AgentToolResult(
            tool_name=name,
            status=status,
            result=output,
            message=output.get("message", ""),
            warnings=output.get("warnings", []),
            error=error,
        )
    except Exception as exc:
        return AgentToolResult(tool_name=name, status=ToolStatus.FAILURE, result={}, message=f"Tool execution failed: {exc}", warnings=[], error=str(exc))


_register(
    name="validate_and_ingest_image",
    description="Validates an image file and ingests it into a session.",
    purpose="Entry point for adding new images to the session workspace before any analysis.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "file_path": {"type": "string", "description": "Absolute path to the image file to ingest"},
        },
        "required": ["session_id", "file_path"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "image_id": {"type": "string"},
            "message": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
            "validation": {"type": "object"},
        },
        "required": ["success", "session_id", "image_id", "message"],
    },
    required=["session_id", "file_path"],
    failures=["File not found", "Unsupported format", "Validation errors", "Metadata extraction failure"],
)

_register(
    name="get_image_metadata",
    description="Retrieves structured metadata for an image in a session.",
    purpose="Allows the agent to inspect image properties such as CRS, resolution, acquisition date, and modality.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id": {"type": "string", "description": "Image identifier returned by ingestion"},
        },
        "required": ["session_id", "image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "image_id": {"type": "string"},
            "message": {"type": "string"},
            "metadata": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "image_id", "message"],
    },
    required=["session_id", "image_id"],
    failures=["Session not found", "Image not found in session"],
)

_register(
    name="classify_scene",
    description="Classifies the relationship between images in a session.",
    purpose="Enables the agent to determine whether the session holds a single image, bi-temporal pair, optical+SAR pair, or multi-image collection.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
        },
        "required": ["session_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "classification": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id"],
    failures=["Session not found", "No images in session"],
)

_register(
    name="check_spatial_overlap",
    description="Computes geometric intersection and overlap percentage between two georeferenced images.",
    purpose="Determines whether two scenes cover the same geographic area and by how much, using geodesic area calculations.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id_1": {"type": "string", "description": "First image identifier"},
            "image_id_2": {"type": "string", "description": "Second image identifier"},
        },
        "required": ["session_id", "image_id_1", "image_id_2"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "overlap": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id_1", "image_id_2"],
    failures=["Session not found", "Image missing", "Images lack geospatial metadata", "No overlap"],
)

_register(
    name="check_compatibility",
    description="Evaluates multi-factor compatibility between two images for comparison.",
    purpose="Assesses temporal, resolution, CRS, spatial overlap, and grid-alignment factors to determine if images are suitable for change detection.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id_1": {"type": "string", "description": "First image identifier"},
            "image_id_2": {"type": "string", "description": "Second image identifier"},
        },
        "required": ["session_id", "image_id_1", "image_id_2"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "compatibility": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id_1", "image_id_2"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "No spatial overlap"],
)

_register(
    name="align_images",
    description="Warps and reprojects a target image onto a reference image's pixel grid.",
    purpose="Prepares two rasters for pixel-by-pixel comparison by aligning CRS, transform, width, and height.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "reference_image_id": {"type": "string", "description": "Image defining the target grid"},
            "target_image_id": {"type": "string", "description": "Image to warp and align"},
            "resampling_method": {"type": "string", "description": "Resampling algorithm: nearest, bilinear, cubic, lanczos, average, mode"},
        },
        "required": ["session_id", "reference_image_id", "target_image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "alignment": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "reference_image_id", "target_image_id"],
    failures=["Session not found", "Image missing", "Missing CRS", "Reprojection failure"],
)

_register(
    name="clip_images",
    description="Clips two rasters to their shared spatial extent on a common pixel grid.",
    purpose="Produces clipped artifacts covering only the overlapping region, ready for direct comparison.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id_1": {"type": "string", "description": "First image defining reference CRS and alignment"},
            "image_id_2": {"type": "string", "description": "Second image to clip"},
            "resampling_method": {"type": "string", "description": "Resampling algorithm"},
        },
        "required": ["session_id", "image_id_1", "image_id_2"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "clip": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id_1", "image_id_2"],
    failures=["Session not found", "Image missing", "Missing CRS", "No common extent"],
)

_register(
    name="detect_clouds_and_shadows",
    description="Builds a cloud/shadow class mask from QA/SCL/cloud-product bands.",
    purpose="Identifies cloud and shadow pixels using only available raster evidence; never invents cloud cover from brightness.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id": {"type": "string", "description": "Georeferenced image to mask"},
        },
        "required": ["session_id", "image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "cloud_mask": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "Insufficient QA/cloud evidence"],
)

_register(
    name="apply_seasonal_filter",
    description="Evaluates seasonal false-positive risk between two acquisition dates.",
    purpose="Provides a deterministic, explainable risk assessment without claiming real events; does not modify masks without phenology evidence.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id_1": {"type": "string", "description": "First image identifier"},
            "image_id_2": {"type": "string", "description": "Second image identifier"},
            "mask_image_id": {"type": "string", "description": "Optional mask image identifier"},
        },
        "required": ["session_id", "image_id_1", "image_id_2"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "seasonal_filter": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id_1", "image_id_2"],
    failures=["Session not found", "Image missing", "Missing acquisition dates"],
)

_register(
    name="mask_to_geojson",
    description="Polygonizes a binary or classified mask raster into EPSG:4326 GeoJSON.",
    purpose="Converts raster masks into frontend-ready vector features with correct CRS transformation and geodesic area per feature.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id": {"type": "string", "description": "Mask raster identifier"},
            "band_index": {"type": "integer", "description": "1-based band index to polygonize"},
            "min_value": {"type": "number", "description": "Pixels >= this value are treated as valid mask"},
        },
        "required": ["session_id", "image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "geojson": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "No valid mask pixels"],
)

_register(
    name="calculate_spatial_statistics",
    description="Computes per-band statistics over valid pixels, optionally constrained by a mask or geometry.",
    purpose="Extends raster statistics to support zonal analysis while preserving existing full-raster behavior.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id": {"type": "string", "description": "Raster to summarize"},
            "mask_image_id": {"type": "string", "description": "Optional binary mask raster"},
            "geometry": {"type": "object", "description": "Optional GeoJSON geometry in EPSG:4326"},
            "band_index": {"type": "integer", "description": "Optional 1-based band index to summarize"},
        },
        "required": ["session_id", "image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "zonal_stats": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "Mask/grid mismatch"],
)

_register(
    name="calculate_area",
    description="Calculates geodesic area for a GeoJSON geometry.",
    purpose="Returns accurate polygon area in m2, hectares, and km2 using WGS84 ellipsoid geodesy rather than planar approximations.",
    input_schema={
        "type": "object",
        "properties": {
            "geojson": {"type": "object", "description": "GeoJSON Feature, FeatureCollection, Polygon, or MultiPolygon"},
        },
        "required": ["geojson"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "area": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "message"],
    },
    required=["geojson"],
    failures=["Invalid GeoJSON", "No polygon geometries found"],
)

_register(
    name="compute_spectral_index",
    description="Computes a spectral index raster (e.g., NDVI) from a multispectral GeoTIFF.",
    purpose="Produces a georeferenced index raster and quantitative statistics for a single image. Band mapping is explicit and does not guess spectral identities.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id": {"type": "string", "description": "Multispectral GeoTIFF identifier"},
            "index_type": {"type": "string", "description": "Index to compute (currently ndvi)"},
            "red_band": {"type": "integer", "description": "1-based red band index"},
            "nir_band": {"type": "integer", "description": "1-based NIR band index"},
        },
        "required": ["session_id", "image_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "spectral_index": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "Band index out of range", "CRS/grid mismatch"],
)

_register(
    name="run_change_detection",
    description="Detects pixel/spectral change between two georeferenced scenes on a common grid.",
    purpose="Produces a georeferenced binary change-mask raster and quantitative statistics. Does not infer land-cover classes or real-world object changes.",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Active session identifier"},
            "image_id_1": {"type": "string", "description": "First georeferenced image identifier"},
            "image_id_2": {"type": "string", "description": "Second georeferenced image identifier"},
            "threshold": {"type": "number", "description": "Change detection threshold"},
            "threshold_method": {"type": "string", "description": "absolute_difference or relative_normalized"},
            "band_index": {"type": "integer", "description": "Optional 1-based band index"},
            "resampling_method": {"type": "string", "description": "Resampling algorithm for alignment"},
        },
        "required": ["session_id", "image_id_1", "image_id_2"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "message": {"type": "string"},
            "change_detection": {"type": "object"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["success", "session_id", "message"],
    },
    required=["session_id", "image_id_1", "image_id_2"],
    failures=["Session not found", "Image missing", "Missing geospatial metadata", "No spatial overlap", "No valid pixels", "CRS/grid mismatch"],
)

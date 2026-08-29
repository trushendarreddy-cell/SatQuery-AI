import re
from typing import List, Optional, Dict, Any, Tuple

from app.core.session_cache import session_manager
from app.schemas.query_schema import QueryIntent, QueryStatus, QueryPlan, QueryResponse
from app.schemas.metadata_schema import ImageCategory


class QueryPlanner:
    """Deterministic natural-language query analyzer producing structured analysis plans."""

    _INTENT_PRIORITY = [
        QueryIntent.CLOUD_SHADOW_ASSESSMENT,
        QueryIntent.AREA_CALCULATION,
        QueryIntent.SPATIAL_OVERLAP,
        QueryIntent.BEFORE_AFTER_ANALYSIS,
        QueryIntent.CHANGE_DETECTION,
        QueryIntent.VEGETATION_ANALYSIS,
        QueryIntent.IMAGE_COMPARISON,
        QueryIntent.MULTI_IMAGE_ANALYSIS,
        QueryIntent.METADATA_QUESTION,
        QueryIntent.IMAGE_INSPECTION,
    ]

    _UNSUPPORTED_INTENTS = {
        QueryIntent.UNSUPPORTED,
    }

    @classmethod
    def analyze(cls, session_id: str, query: str) -> QueryResponse:
        session = session_manager.get_session(session_id)
        if not session:
            return QueryResponse(
                session_id=session_id,
                query=query,
                intent=QueryIntent.UNSUPPORTED,
                required_images=[],
                required_tools=[],
                reasoning="Session not found. Please upload images first.",
                status=QueryStatus.ERROR,
                unsupported_reason="Session not found.",
            )

        images = session_manager.get_images(session_id)
        if not images:
            return QueryResponse(
                session_id=session_id,
                query=query,
                intent=QueryIntent.UNSUPPORTED,
                required_images=[],
                required_tools=[],
                reasoning="No images in session. Please upload images before querying.",
                status=QueryStatus.NEEDS_MORE_IMAGES,
                unsupported_reason="No images available in session.",
            )

        intent = cls._detect_intent(query, images)
        plan, required_images, reasoning = cls._build_plan(intent, query, images)

        if intent in cls._UNSUPPORTED_INTENTS:
            reason = cls._unsupported_reason(intent)
            return QueryResponse(
                session_id=session_id,
                query=query,
                intent=intent,
                required_images=required_images,
                required_tools=[p.tool_name for p in plan],
                reasoning=reasoning,
                status=QueryStatus.UNSUPPORTED,
                unsupported_reason=reason,
                plan=plan,
            )

        return QueryResponse(
            session_id=session_id,
            query=query,
            intent=intent,
            required_images=required_images,
            required_tools=[p.tool_name for p in plan],
            reasoning=reasoning,
            status=QueryStatus.READY,
            plan=plan,
        )

    @classmethod
    def _detect_intent(cls, query: str, images: List[Any]) -> QueryIntent:
        q = query.lower()
        has_two = len(images) >= 2
        has_any = len(images) >= 1

        if re.search(r'\b(clouds?\b|shadows?\b|masks?\b)', q) and has_any:
            return QueryIntent.CLOUD_SHADOW_ASSESSMENT
        if re.search(r'\b(area|hectares?\b|km2|sq\s*km|square\s*kilomet|size)\b', q) and has_any:
            return QueryIntent.AREA_CALCULATION
        if re.search(r'\b(overlap|intersect|cover|common)\b', q) and has_two:
            return QueryIntent.SPATIAL_OVERLAP
        if re.search(r'\b(before.{0,10}after|after.{0,10}before|temporal|time)\b', q) and has_two:
            return QueryIntent.BEFORE_AFTER_ANALYSIS
        if re.search(r'\b(change|detect|difference|differ|changed)\b', q) and has_two:
            return QueryIntent.CHANGE_DETECTION
        if re.search(r'\b(vegetation|ndvi|green|biomass|crop|health)\b', q) and has_any:
            return QueryIntent.VEGETATION_ANALYSIS
        if re.search(r'\b(compare|comparison|versus|vs)\b', q) and has_two:
            return QueryIntent.IMAGE_COMPARISON
        if re.search(r'\b(metadata|info|details|properties|bands|resolution|crs|date)\b', q) and has_any:
            return QueryIntent.METADATA_QUESTION
        if re.search(r'\b(multi|multiple|all|batch|collection)\b', q) and len(images) >= 3:
            return QueryIntent.MULTI_IMAGE_ANALYSIS
        if re.search(r'\b(inspect|look|show|display|view|what|check)\b', q) and has_any:
            return QueryIntent.IMAGE_INSPECTION
        if has_two:
            return QueryIntent.IMAGE_COMPARISON
        if has_any:
            return QueryIntent.IMAGE_INSPECTION
        return QueryIntent.UNSUPPORTED

    @classmethod
    def _build_plan(cls, intent: QueryIntent, query: str, images: List[Any]) -> Tuple[List[QueryPlan], List[str], str]:
        geos = [img for img in images if img.has_geospatial_metadata]
        non_geos = [img for img in images if not img.has_geospatial_metadata]
        image_ids = [img.image_id for img in images]
        geo_ids = [img.image_id for img in geos]

        if intent == QueryIntent.IMAGE_INSPECTION:
            target = image_ids[0]
            plan = [QueryPlan(tool_name="get_image_metadata", arguments={"session_id": "", "image_id": target})]
            return plan, [target], f"Inspecting image '{target}' metadata."

        if intent == QueryIntent.METADATA_QUESTION:
            target = image_ids[0]
            plan = [QueryPlan(tool_name="get_image_metadata", arguments={"session_id": "", "image_id": target})]
            return plan, [target], f"Retrieving metadata for image '{target}'."

        if intent == QueryIntent.MULTI_IMAGE_ANALYSIS:
            plan = [QueryPlan(tool_name="classify_scene", arguments={"session_id": ""})]
            return plan, image_ids, "Classifying scene configuration across all session images."

        if intent == QueryIntent.CLOUD_SHADOW_ASSESSMENT:
            if not geo_ids:
                plan = []
                return plan, [], "No georeferenced images available for cloud/shadow assessment."
            target = geo_ids[0]
            plan = [QueryPlan(tool_name="detect_clouds_and_shadows", arguments={"session_id": "", "image_id": target})]
            return plan, [target], f"Assessing cloud/shadow coverage for georeferenced image '{target}'."

        if intent == QueryIntent.SPATIAL_OVERLAP:
            if len(geo_ids) < 2:
                plan = []
                return plan, geo_ids, "Need at least two georeferenced images to assess overlap."
            plan = [
                QueryPlan(tool_name="check_spatial_overlap", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
            ]
            return plan, geo_ids[:2], "Computing spatial overlap and intersection between two georeferenced scenes."

        if intent == QueryIntent.IMAGE_COMPARISON:
            if len(geo_ids) < 2:
                plan = []
                return plan, geo_ids, "Need at least two georeferenced images for comparison."
            plan = [
                QueryPlan(tool_name="check_spatial_overlap", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
                QueryPlan(tool_name="check_compatibility", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
            ]
            return plan, geo_ids[:2], "Comparing two georeferenced scenes for overlap and compatibility."

        if intent == QueryIntent.BEFORE_AFTER_ANALYSIS:
            if len(geo_ids) < 2:
                plan = []
                return plan, geo_ids, "Need at least two georeferenced images for before/after analysis."
            plan = [
                QueryPlan(tool_name="check_spatial_overlap", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
                QueryPlan(tool_name="check_compatibility", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
                QueryPlan(tool_name="apply_seasonal_filter", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
            ]
            return plan, geo_ids[:2], "Running before/after analysis: overlap, compatibility, and seasonal risk assessment."

        if intent == QueryIntent.AREA_CALCULATION:
            if not geo_ids:
                plan = []
                return plan, [], "No georeferenced images available for area calculation."
            plan = [
                QueryPlan(tool_name="mask_to_geojson", arguments={"session_id": "", "image_id": geo_ids[0], "band_index": 1, "min_value": 1.0}),
                QueryPlan(tool_name="calculate_area", arguments={"geojson": {}}),
            ]
            return plan, [geo_ids[0]], "Vectorizing mask and calculating geodesic area for the first georeferenced image."

        if intent == QueryIntent.CHANGE_DETECTION:
            if len(geo_ids) < 2:
                plan = []
                return plan, geo_ids, "Need at least two georeferenced images for change detection."
            plan = [
                QueryPlan(tool_name="check_spatial_overlap", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
                QueryPlan(tool_name="check_compatibility", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1]}),
                QueryPlan(tool_name="run_change_detection", arguments={"session_id": "", "image_id_1": geo_ids[0], "image_id_2": geo_ids[1], "threshold": 0.1, "threshold_method": "relative_normalized"}),
            ]
            return plan, geo_ids[:2], "Running pixel/spectral change detection between two georeferenced scenes on a common grid."

        if intent == QueryIntent.VEGETATION_ANALYSIS:
            if not geo_ids:
                plan = []
                return plan, [], "No georeferenced images available for vegetation analysis."
            target = geo_ids[0]
            plan = [
                QueryPlan(tool_name="compute_spectral_index", arguments={"session_id": "", "image_id": target, "index_type": "ndvi", "red_band": 3, "nir_band": 4}),
            ]
            return plan, [target], "Computing NDVI vegetation index for the first georeferenced image."

        plan = []
        return plan, image_ids, "Unable to determine a specific analysis plan for this query."

    @classmethod
    def _unsupported_reason(cls, intent: QueryIntent) -> str:
        return "This query type is not supported."

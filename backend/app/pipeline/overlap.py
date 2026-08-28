import math
from typing import Optional, Dict, Any, Tuple
from shapely.geometry import box, mapping, Polygon
from pyproj import Geod
import rasterio
from rasterio.warp import transform_bounds

from app.core.session_cache import session_manager
from app.schemas.metadata_schema import ImageCategory, UnifiedImageMetadata
from app.schemas.spatial_schema import SpatialOverlapResult


class SpatialOverlapEngine:
    """Calculates geometric intersection and spatial overlap percentage between scenes."""

    _geod = Geod(ellps="WGS84")

    @classmethod
    def calculate_overlap(
        cls,
        meta1: UnifiedImageMetadata,
        meta2: UnifiedImageMetadata,
    ) -> SpatialOverlapResult:
        """
        Calculates spatial overlap between two georeferenced image metadata objects.
        """
        # 1. Verify both are georeferenced
        if not meta1.has_geospatial_metadata or not meta1.geospatial:
            return SpatialOverlapResult(
                overlap_exists=False,
                overlap_percentage=0.0,
                overlap_percentage_image_1=0.0,
                overlap_percentage_image_2=0.0,
                intersection_geojson=None,
                messages=[],
                warnings=[f"Image '{meta1.filename}' (ID: {meta1.image_id}) lacks geospatial metadata. Spatial overlap requires georeferenced GeoTIFFs."],
            )

        if not meta2.has_geospatial_metadata or not meta2.geospatial:
            return SpatialOverlapResult(
                overlap_exists=False,
                overlap_percentage=0.0,
                overlap_percentage_image_1=0.0,
                overlap_percentage_image_2=0.0,
                intersection_geojson=None,
                messages=[],
                warnings=[f"Image '{meta2.filename}' (ID: {meta2.image_id}) lacks geospatial metadata. Spatial overlap requires georeferenced GeoTIFFs."],
            )

        # 2. Extract WGS84 bounding coordinates
        b1 = meta1.geospatial.bounds_wgs84
        b2 = meta2.geospatial.bounds_wgs84

        if not b1 or not b2:
            return SpatialOverlapResult(
                overlap_exists=False,
                overlap_percentage=0.0,
                overlap_percentage_image_1=0.0,
                overlap_percentage_image_2=0.0,
                intersection_geojson=None,
                messages=[],
                warnings=["Could not determine WGS84 bounding coordinates for one or both images."],
            )

        # 3. Construct Shapely bounding box polygons in EPSG:4326
        poly1 = box(b1.min_lon, b1.min_lat, b1.max_lon, b1.max_lat)
        poly2 = box(b2.min_lon, b2.min_lat, b2.max_lon, b2.max_lat)

        # 4. Calculate geometric intersection
        try:
            intersection = poly1.intersection(poly2)
        except Exception as exc:
            return SpatialOverlapResult(
                overlap_exists=False,
                overlap_percentage=0.0,
                overlap_percentage_image_1=0.0,
                overlap_percentage_image_2=0.0,
                intersection_geojson=None,
                messages=[],
                warnings=[f"Error calculating geometric intersection: {str(exc)}"],
            )

        if intersection.is_empty or intersection.area <= 1e-12:
            return SpatialOverlapResult(
                overlap_exists=False,
                overlap_percentage=0.0,
                overlap_percentage_image_1=0.0,
                overlap_percentage_image_2=0.0,
                intersection_geojson=None,
                intersection_bounds_wgs84=None,
                intersection_area_sqkm=0.0,
                messages=["The two scenes do not geographically intersect."],
                warnings=["No spatial overlap found between the selected scenes."],
            )

        # 5. Calculate Overlap Metrics
        area1 = poly1.area
        area2 = poly2.area
        inter_area = intersection.area
        union_area = area1 + area2 - inter_area

        pct1 = round(float((inter_area / area1) * 100.0), 2)
        pct2 = round(float((inter_area / area2) * 100.0), 2)
        iou_pct = round(float((inter_area / union_area) * 100.0), 2)

        # 6. Calculate geodesic intersection area in sq. km using WGS84 ellipsoid
        area_sqkm = None
        try:
            geodesic_area_m2, _ = cls._geod.geometry_area_perimeter(intersection)
            area_sqkm = round(float(abs(geodesic_area_m2) / 1_000_000.0), 4)
        except Exception:
            pass

        # 7. Extract intersection bounding coordinates
        ib = intersection.bounds  # (minx, miny, maxx, maxy)
        intersection_bounds = {
            "min_lon": float(ib[0]),
            "min_lat": float(ib[1]),
            "max_lon": float(ib[2]),
            "max_lat": float(ib[3]),
        }

        geojson_geometry = mapping(intersection)

        messages = [
            f"Scenes overlap geographically with {iou_pct}% IoU.",
            f"Intersection covers {pct1}% of Image 1 and {pct2}% of Image 2.",
        ]
        if area_sqkm is not None:
            messages.append(f"Geodesic overlap area: {area_sqkm} sq. km.")

        warnings = []
        if iou_pct < 20.0:
            warnings.append(
                f"Low spatial overlap detected ({iou_pct}% IoU). Downstream change detection may only cover a small common sub-region."
            )

        return SpatialOverlapResult(
            overlap_exists=True,
            overlap_percentage=iou_pct,
            overlap_percentage_image_1=pct1,
            overlap_percentage_image_2=pct2,
            intersection_geojson=geojson_geometry,
            intersection_bounds_wgs84=intersection_bounds,
            intersection_area_sqkm=area_sqkm,
            messages=messages,
            warnings=warnings,
        )


def check_spatial_overlap(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
) -> SpatialOverlapResult:
    """
    Deterministic tool function to check spatial overlap between two images in a session.
    Callable by AI Agent, services, or API endpoints.
    """
    session = session_manager.get_session(session_id)
    if not session:
        return SpatialOverlapResult(
            overlap_exists=False,
            overlap_percentage=0.0,
            overlap_percentage_image_1=0.0,
            overlap_percentage_image_2=0.0,
            intersection_geojson=None,
            messages=[],
            warnings=[f"Session '{session_id}' not found."],
        )

    meta1 = session.images.get(image_id_1)
    meta2 = session.images.get(image_id_2)

    if not meta1:
        return SpatialOverlapResult(
            overlap_exists=False,
            overlap_percentage=0.0,
            overlap_percentage_image_1=0.0,
            overlap_percentage_image_2=0.0,
            intersection_geojson=None,
            messages=[],
            warnings=[f"Image '{image_id_1}' not found in session '{session_id}'."],
        )

    if not meta2:
        return SpatialOverlapResult(
            overlap_exists=False,
            overlap_percentage=0.0,
            overlap_percentage_image_1=0.0,
            overlap_percentage_image_2=0.0,
            intersection_geojson=None,
            messages=[],
            warnings=[f"Image '{image_id_2}' not found in session '{session_id}'."],
        )

    return SpatialOverlapEngine.calculate_overlap(meta1, meta2)

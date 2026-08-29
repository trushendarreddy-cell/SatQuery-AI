"""Geodesic polygon area on the WGS84 ellipsoid."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pyproj import Geod
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

_GEOD = Geod(ellps="WGS84")


def _iter_geometries(geojson: Dict[str, Any]) -> List[BaseGeometry]:
    if not geojson or not isinstance(geojson, dict):
        return []
    gtype = geojson.get("type")
    geoms: List[BaseGeometry] = []
    if gtype == "FeatureCollection":
        for feat in geojson.get("features") or []:
            geom = feat.get("geometry") if isinstance(feat, dict) else None
            if geom:
                geoms.append(shape(geom))
    elif gtype == "Feature":
        geom = geojson.get("geometry")
        if geom:
            geoms.append(shape(geom))
    elif gtype in {"Polygon", "MultiPolygon", "GeometryCollection"}:
        geoms.append(shape(geojson))
    return [g for g in geoms if g is not None and not g.is_empty]


def geodesic_area_m2(geometry: BaseGeometry) -> float:
    if geometry.is_empty:
        return 0.0
    area_m2, _ = _GEOD.geometry_area_perimeter(geometry)
    return float(abs(area_m2))


def calculate_geojson_area(geojson: Dict[str, Any]) -> Tuple[float, int]:
    """Return (area_m2, feature_count) for WGS84 GeoJSON. Empty input is 0 area."""
    geoms = _iter_geometries(geojson)
    if not geoms:
        return 0.0, 0
    merged = unary_union(geoms)
    return geodesic_area_m2(merged), len(geoms)


def area_breakdown(area_m2: float) -> Dict[str, float]:
    return {
        "area_m2": round(float(area_m2), 4),
        "area_ha": round(float(area_m2) / 10_000.0, 6),
        "area_sqkm": round(float(area_m2) / 1_000_000.0, 8),
    }

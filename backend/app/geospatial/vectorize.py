"""Polygonize a binary/classified raster mask into WGS84 GeoJSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom

from app.geospatial.area import area_breakdown, geodesic_area_m2
from shapely.geometry import shape


def mask_array_to_geojson(
    mask: np.ndarray,
    transform,
    src_crs,
    min_value: float = 1.0,
) -> Dict[str, Any]:
    """Convert a 2D mask array to an EPSG:4326 FeatureCollection. Empty masks yield zero features."""
    if mask.ndim != 2:
        raise ValueError("Mask must be a 2D array.")
    if src_crs is None:
        raise ValueError("Mask raster has no CRS; coordinates will not be invented.")

    valid = np.isfinite(mask) & (mask >= min_value)
    features = []
    if not valid.any():
        return {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": [],
        }

    class_arr = np.where(valid, mask, 0).astype(np.int32)
    for geom, value in shapes(class_arr, mask=valid, transform=transform):
        if int(value) == 0:
            continue
        geom_wgs = transform_geom(src_crs, "EPSG:4326", geom, precision=7)
        poly = shape(geom_wgs)
        if poly.is_empty:
            continue
        area_m2 = geodesic_area_m2(poly)
        breakdown = area_breakdown(area_m2)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "value": int(value),
                    "area_m2": breakdown["area_m2"],
                    "area_ha": breakdown["area_ha"],
                    "area_sqkm": breakdown["area_sqkm"],
                },
                "geometry": geom_wgs,
            }
        )

    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features,
    }


def polygonize_mask_file(
    path: Path,
    band_index: int = 1,
    min_value: float = 1.0,
) -> Dict[str, Any]:
    with rasterio.open(path) as src:
        if not src.crs:
            raise ValueError("Mask raster has no CRS; coordinates will not be invented.")
        if band_index < 1 or band_index > src.count:
            raise ValueError(f"Band {band_index} is not present on this raster.")
        data = src.read(band_index)
        nodata = src.nodatavals[band_index - 1]
        if nodata is not None:
            data = np.where(data == nodata, 0, data)
        fc = mask_array_to_geojson(data, src.transform, src.crs, min_value=min_value)
        return {
            "geojson": fc,
            "source_crs": src.crs.to_string(),
        }

"""Zonal / masked raster statistics without assuming visual images are geospatial."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.warp import transform_geom


def _stats_from_array(arr: np.ndarray, nodata) -> dict:
    data = np.ma.masked_invalid(arr.astype(np.float64))
    if nodata is not None:
        data = np.ma.masked_where(data == nodata, data)
    valid_count = int(data.count())
    nodata_count = int(data.size - valid_count)
    if valid_count == 0:
        return {
            "valid_pixel_count": 0,
            "nodata_pixel_count": nodata_count,
            "min_value": None,
            "max_value": None,
            "mean_value": None,
            "std_value": None,
            "sum_value": None,
        }
    return {
        "valid_pixel_count": valid_count,
        "nodata_pixel_count": nodata_count,
        "min_value": float(data.min()),
        "max_value": float(data.max()),
        "mean_value": float(data.mean()),
        "std_value": float(data.std()),
        "sum_value": float(data.sum()),
    }


def _geometry_list(geojson: Dict[str, Any]) -> List[dict]:
    if not geojson:
        return []
    gtype = geojson.get("type")
    if gtype == "FeatureCollection":
        return [f["geometry"] for f in geojson.get("features") or [] if f.get("geometry")]
    if gtype == "Feature":
        geom = geojson.get("geometry")
        return [geom] if geom else []
    if gtype in {"Polygon", "MultiPolygon"}:
        return [geojson]
    return []


def compute_zonal_statistics(
    raster_path: Path,
    mask_path: Optional[Path] = None,
    geometry: Optional[Dict[str, Any]] = None,
    band_index: Optional[int] = None,
) -> List[dict]:
    """
    Per-band stats over valid pixels. Optional binary mask (same grid preferred)
    and/or GeoJSON geometry further restrict the sample.
    """
    with rasterio.open(raster_path) as src:
        if not src.crs:
            raise ValueError("Raster has no CRS; zonal spatial statistics require a georeferenced raster.")

        bands = [band_index] if band_index else list(range(1, src.count + 1))
        if band_index is not None and (band_index < 1 or band_index > src.count):
            raise ValueError(f"Band {band_index} is not present on this raster.")

        geom_mask = None
        geoms = _geometry_list(geometry) if geometry else []
        if geoms:
            projected = [transform_geom("EPSG:4326", src.crs, g) for g in geoms]
            masked, _ = rio_mask(src, projected, crop=False, filled=False)
            geom_mask = ~np.ma.getmaskarray(masked)[0]

        raster_mask = None
        if mask_path is not None:
            with rasterio.open(mask_path) as msrc:
                if msrc.width != src.width or msrc.height != src.height or msrc.transform != src.transform:
                    raise ValueError("Mask raster must share the source raster pixel grid. Align or clip first.")
                m = msrc.read(1)
                mn = msrc.nodatavals[0]
                raster_mask = m > 0
                if mn is not None:
                    raster_mask &= m != mn

        results = []
        for b in bands:
            arr = src.read(b)
            nodata = src.nodatavals[b - 1]
            select = np.ones(arr.shape, dtype=bool)
            if geom_mask is not None:
                select &= geom_mask
            if raster_mask is not None:
                select &= raster_mask
            sampled = np.where(select, arr, np.nan)
            stats = _stats_from_array(sampled, nodata)
            stats["band_index"] = int(b)
            results.append(stats)
        return results

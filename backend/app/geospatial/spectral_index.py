"""Spectral index computations for georeferenced rasters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.warp import transform_geom


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray, nodata_mask: np.ndarray) -> np.ndarray:
    """Element-wise division that yields NaN where denominator is 0 or nodata."""
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.true_divide(numerator, denominator)
    result[denominator == 0] = np.nan
    result[~nodata_mask] = np.nan
    return result


def compute_ndvi(
    red_path: Path,
    nir_path: Path,
    output_path: Path,
    red_band: int = 3,
    nir_band: int = 4,
) -> dict:
    """
    Computes NDVI = (NIR - Red) / (NIR + Red) for aligned georeferenced rasters.

    Requirements:
    - Both inputs must be georeferenced rasters with the same pixel grid (CRS, transform, width, height).
    - red_band and nir_band are 1-based band indices.

    Returns a dict with:
      - output_path: Path to the written NDVI GeoTIFF
      - crs: output CRS string
      - transform: affine transform as list
      - width, height: dimensions
      - valid_pixel_count, nodata_pixel_count
      - min_value, max_value, mean_value
      - red_band, nir_band: band indices used
      - message: status summary
    """
    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        if not red_src.crs or not nir_src.crs:
            raise ValueError("Both rasters must have valid CRS metadata.")
        if red_src.crs != nir_src.crs:
            raise ValueError(
                f"CRS mismatch: {red_src.crs} vs {nir_src.crs}. Align rasters before computing spectral index."
            )
        if red_src.transform != nir_src.transform:
            raise ValueError(
                "Pixel grid transform mismatch. Align or clip rasters to a common grid before computing spectral index."
            )
        if red_src.width != nir_src.width or red_src.height != nir_src.height:
            raise ValueError(
                f"Dimension mismatch: {red_src.width}x{red_src.height} vs {nir_src.width}x{nir_src.height}. Align rasters first."
            )
        if red_band < 1 or red_band > red_src.count:
            raise ValueError(f"Red band {red_band} is out of range for raster with {red_src.count} bands.")
        if nir_band < 1 or nir_band > nir_src.count:
            raise ValueError(f"NIR band {nir_band} is out of range for raster with {nir_src.count} bands.")

        red = red_src.read(red_band).astype(np.float64)
        nir = nir_src.read(nir_band).astype(np.float64)

        nodata_red = red_src.nodatavals[red_band - 1]
        nodata_nir = nir_src.nodatavals[nir_band - 1]

        valid = np.ones(red.shape, dtype=bool)
        if nodata_red is not None:
            valid &= red != nodata_red
        if nodata_nir is not None:
            valid &= nir != nodata_nir

        ndvi = _safe_divide(nir - red, nir + red, valid)
        valid_pixels = int(np.count_nonzero(valid))
        nodata_pixels = int(red.size - valid_pixels)

        stats = {
            "valid_pixel_count": valid_pixels,
            "nodata_pixel_count": nodata_pixels,
            "min_value": float(np.nanmin(ndvi)) if valid_pixels > 0 else None,
            "max_value": float(np.nanmax(ndvi)) if valid_pixels > 0 else None,
            "mean_value": float(np.nanmean(ndvi)) if valid_pixels > 0 else None,
        }

        profile = red_src.profile.copy()
        profile.update({
            "count": 1,
            "dtype": "float32",
            "nodata": np.nan,
            "compress": "deflate",
            "tiled": False,
            "interleave": "pixel",
        })
        for key in ("blockxsize", "blockysize", "tiled"):
            profile.pop(key, None)

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(ndvi.astype(np.float32), 1)

        return {
            "output_path": str(output_path),
            "crs": red_src.crs.to_string() if red_src.crs else "",
            "transform": [
                float(red_src.transform.c),
                float(red_src.transform.a),
                float(red_src.transform.b),
                float(red_src.transform.d),
                float(red_src.transform.e),
                float(red_src.transform.f),
            ],
            "width": int(red_src.width),
            "height": int(red_src.height),
            "red_band": red_band,
            "nir_band": nir_band,
            **stats,
            "message": f"NDVI computed using red band {red_band} and NIR band {nir_band}.",
        }

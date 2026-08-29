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


def _validate_grid(red_src, nir_src, blue_src=None, green_src=None) -> None:
    if not red_src.crs or not nir_src.crs:
        raise ValueError("All rasters must have valid CRS metadata.")
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
    if blue_src is not None:
        if blue_src.crs != red_src.crs or blue_src.transform != red_src.transform or blue_src.width != red_src.width or blue_src.height != red_src.height:
            raise ValueError("Blue raster does not match the red/NIR grid.")
    if green_src is not None:
        if green_src.crs != red_src.crs or green_src.transform != red_src.transform or green_src.width != red_src.width or green_src.height != red_src.height:
            raise ValueError("Green raster does not match the red/NIR grid.")


def _read_band(src, band_index, label):
    if band_index < 1 or band_index > src.count:
        raise ValueError(f"{label} band {band_index} is out of range for raster with {src.count} bands.")
    return src.read(band_index).astype(np.float64)


def _compute_stats(index, valid_mask):
    valid_pixels = int(np.count_nonzero(valid_mask))
    nodata_pixels = int(index.size - valid_pixels)
    if valid_pixels == 0:
        return {
            "valid_pixel_count": 0,
            "nodata_pixel_count": nodata_pixels,
            "min_value": None,
            "max_value": None,
            "mean_value": None,
        }
    masked = np.where(valid_mask, index, np.nan)
    return {
        "valid_pixel_count": valid_pixels,
        "nodata_pixel_count": nodata_pixels,
        "min_value": float(np.nanmin(masked)),
        "max_value": float(np.nanmax(masked)),
        "mean_value": float(np.nanmean(masked)),
    }


def _write_float32_geotiff(output_path, index, profile_template):
    profile = profile_template.copy()
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
        dst.write(index.astype(np.float32), 1)


def compute_ndvi(
    red_path: Path,
    nir_path: Path,
    output_path: Path,
    red_band: int = 3,
    nir_band: int = 4,
) -> dict:
    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        _validate_grid(red_src, nir_src)
        red = _read_band(red_src, red_band, "Red")
        nir = _read_band(nir_src, nir_band, "NIR")
        nodata_red = red_src.nodatavals[red_band - 1]
        nodata_nir = nir_src.nodatavals[nir_band - 1]
        valid = np.ones(red.shape, dtype=bool)
        if nodata_red is not None:
            valid &= red != nodata_red
        if nodata_nir is not None:
            valid &= nir != nodata_nir
        ndvi = _safe_divide(nir - red, nir + red, valid)
        stats = _compute_stats(ndvi, valid)
        _write_float32_geotiff(output_path, ndvi, red_src.profile)
        return {
            "output_path": str(output_path),
            "crs": red_src.crs.to_string() if red_src.crs else "",
            "transform": [
                float(red_src.transform.c), float(red_src.transform.a), float(red_src.transform.b),
                float(red_src.transform.d), float(red_src.transform.e), float(red_src.transform.f),
            ],
            "width": int(red_src.width), "height": int(red_src.height),
            "red_band": red_band, "nir_band": nir_band,
            **stats,
            "message": f"NDVI computed using red band {red_band} and NIR band {nir_band}.",
        }


def compute_evi(
    red_path: Path,
    nir_path: Path,
    blue_path: Path,
    output_path: Path,
    red_band: int = 3,
    nir_band: int = 4,
    blue_band: int = 2,
) -> dict:
    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src, rasterio.open(blue_path) as blue_src:
        _validate_grid(red_src, nir_src, blue_src)
        red = _read_band(red_src, red_band, "Red")
        nir = _read_band(nir_src, nir_band, "NIR")
        blue = _read_band(blue_src, blue_band, "Blue")
        nodata_red = red_src.nodatavals[red_band - 1]
        nodata_nir = nir_src.nodatavals[nir_band - 1]
        nodata_blue = blue_src.nodatavals[blue_band - 1]
        valid = np.ones(red.shape, dtype=bool)
        if nodata_red is not None:
            valid &= red != nodata_red
        if nodata_nir is not None:
            valid &= nir != nodata_nir
        if nodata_blue is not None:
            valid &= blue != nodata_blue
        denom = nir + 6.0 * red - 7.5 * blue + 1.0
        evi = _safe_divide(2.5 * (nir - red), denom, valid)
        stats = _compute_stats(evi, valid)
        _write_float32_geotiff(output_path, evi, red_src.profile)
        return {
            "output_path": str(output_path),
            "crs": red_src.crs.to_string() if red_src.crs else "",
            "transform": [
                float(red_src.transform.c), float(red_src.transform.a), float(red_src.transform.b),
                float(red_src.transform.d), float(red_src.transform.e), float(red_src.transform.f),
            ],
            "width": int(red_src.width), "height": int(red_src.height),
            "red_band": red_band, "nir_band": nir_band, "blue_band": blue_band,
            **stats,
            "message": f"EVI computed using red band {red_band}, NIR band {nir_band}, and blue band {blue_band}.",
        }


def compute_ndwi(
    green_path: Path,
    nir_path: Path,
    output_path: Path,
    green_band: int = 3,
    nir_band: int = 4,
) -> dict:
    with rasterio.open(green_path) as green_src, rasterio.open(nir_path) as nir_src:
        _validate_grid(green_src, nir_src)
        green = _read_band(green_src, green_band, "Green")
        nir = _read_band(nir_src, nir_band, "NIR")
        nodata_green = green_src.nodatavals[green_band - 1]
        nodata_nir = nir_src.nodatavals[nir_band - 1]
        valid = np.ones(green.shape, dtype=bool)
        if nodata_green is not None:
            valid &= green != nodata_green
        if nodata_nir is not None:
            valid &= nir != nodata_nir
        ndwi = _safe_divide(green - nir, green + nir, valid)
        stats = _compute_stats(ndwi, valid)
        _write_float32_geotiff(output_path, ndwi, green_src.profile)
        return {
            "output_path": str(output_path),
            "crs": green_src.crs.to_string() if green_src.crs else "",
            "transform": [
                float(green_src.transform.c), float(green_src.transform.a), float(green_src.transform.b),
                float(green_src.transform.d), float(green_src.transform.e), float(green_src.transform.f),
            ],
            "width": int(green_src.width), "height": int(green_src.height),
            "green_band": green_band, "nir_band": nir_band,
            **stats,
            "message": f"NDWI computed using green band {green_band} and NIR band {nir_band}.",
        }

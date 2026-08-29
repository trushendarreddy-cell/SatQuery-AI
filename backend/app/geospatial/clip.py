"""Compute a shared pixel grid covering the spatial intersection of two rasters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import rasterio
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, transform as window_transform


@dataclass(frozen=True)
class CommonPixelGrid:
    """Integer pixel grid covering the intersection of two georeferenced rasters."""

    crs: object
    transform: Affine
    width: int
    height: int
    bounds_native: dict
    bounds_wgs84: dict


def compute_common_pixel_grid(
    ref_ds: rasterio.DatasetReader,
    src_ds: rasterio.DatasetReader,
) -> Optional[CommonPixelGrid]:
    """
    Snap the intersection of two raster footprints onto the reference pixel grid.

    Uses raster bounds (not in-memory pixel arrays). Returns None when the
    footprints do not share a positive-area intersection.
    """
    if not ref_ds.crs or not src_ds.crs:
        raise ValueError("Both rasters must possess valid CRS metadata.")

    b1 = transform_bounds(ref_ds.crs, ref_ds.crs, *ref_ds.bounds, densify_pts=21)
    b2 = transform_bounds(src_ds.crs, ref_ds.crs, *src_ds.bounds, densify_pts=21)

    minx = max(b1[0], b2[0])
    miny = max(b1[1], b2[1])
    maxx = min(b1[2], b2[2])
    maxy = min(b1[3], b2[3])

    if minx >= maxx or miny >= maxy:
        return None

    # Convert geographic intersection to reference-grid pixel window, then snap
    # to integer columns/rows that fully cover the overlapping region.
    inv = ~ref_ds.transform
    col_a, row_a = inv * (minx, maxy)
    col_b, row_b = inv * (maxx, miny)

    col_off = int(math.floor(min(col_a, col_b)))
    row_off = int(math.floor(min(row_a, row_b)))
    col_max = int(math.ceil(max(col_a, col_b)))
    row_max = int(math.ceil(max(row_a, row_b)))

    width = col_max - col_off
    height = row_max - row_off
    if width < 1 or height < 1:
        return None

    snapped = Window(col_off, row_off, width, height)
    dst_transform = window_transform(snapped, ref_ds.transform)

    native_bounds = {
        "min_x": float(minx),
        "min_y": float(miny),
        "max_x": float(maxx),
        "max_y": float(maxy),
    }

    wgs = transform_bounds(ref_ds.crs, "EPSG:4326", minx, miny, maxx, maxy, densify_pts=21)
    bounds_wgs84 = {
        "min_lon": float(wgs[0]),
        "min_lat": float(wgs[1]),
        "max_lon": float(wgs[2]),
        "max_lat": float(wgs[3]),
    }

    return CommonPixelGrid(
        crs=ref_ds.crs,
        transform=dst_transform,
        width=int(width),
        height=int(height),
        bounds_native=native_bounds,
        bounds_wgs84=bounds_wgs84,
    )

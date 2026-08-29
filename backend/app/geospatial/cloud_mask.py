"""Cloud and cloud-shadow masks from explicit QA/SCL/cloud-product bands only."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import rasterio

SCL_CLOUD = {8, 9, 10}
SCL_SHADOW = {3}
LANDSAT_QA_CLOUD_BITS = (1, 2, 3)  # dilated cloud, cirrus, cloud
LANDSAT_QA_SHADOW_BIT = 4


def _band_label(src: rasterio.DatasetReader, index: int) -> str:
    desc = ""
    if src.descriptions and len(src.descriptions) >= index:
        desc = src.descriptions[index - 1] or ""
    tags = src.tags(index)
    name = tags.get("BANDNAME") or tags.get("NAME") or tags.get("DESCRIPTION") or ""
    return f"{desc} {name}".strip().lower()


def detect_qa_band(src: rasterio.DatasetReader) -> Optional[Tuple[int, str, str]]:
    """
    Return (band_index, kind, label) where kind is scl | qa_pixel | cloud_prob | cloud_mask.
    Requires a named QA/SCL/cloud product. Spectral brightness is never used.
    """
    for idx in range(1, src.count + 1):
        label = _band_label(src, idx)
        compact = label.replace(" ", "_").replace("-", "_")
        if "scl" in compact.split("_") or "scene_classification" in compact:
            return idx, "scl", label or "scl"
        if "qa_pixel" in compact or compact in {"bqa", "qa"} or "quality_assessment" in compact:
            return idx, "qa_pixel", label or "qa_pixel"
        if "cldprb" in compact or "cloud_prob" in compact or "cloud_probability" in compact:
            return idx, "cloud_prob", label or "cloud_probability"
        if compact in {"cloud", "cloud_mask", "clouds"} or "cloud_mask" in compact:
            return idx, "cloud_mask", label or "cloud_mask"
        if "cloud_shadow" in compact or compact in {"shadow", "shadow_mask"}:
            return idx, "shadow_mask", label or "cloud_shadow"
    return None


def classify_cloud_shadow(src: rasterio.DatasetReader) -> Optional[dict]:
    """
    Build uint8 class map: 0 clear, 1 cloud, 2 shadow.
    Returns None when no QA/SCL/cloud product band is present.
    """
    detected = detect_qa_band(src)
    if detected is None:
        return None

    band_index, kind, label = detected
    data = src.read(band_index)
    nodata = src.nodatavals[band_index - 1]
    valid = np.ones(data.shape, dtype=bool)
    if nodata is not None:
        valid &= data != nodata

    cloud = np.zeros(data.shape, dtype=bool)
    shadow = np.zeros(data.shape, dtype=bool)

    if kind == "scl":
        cloud = np.isin(data, list(SCL_CLOUD)) & valid
        shadow = np.isin(data, list(SCL_SHADOW)) & valid
    elif kind == "qa_pixel":
        qa = data.astype(np.uint32)
        for bit in LANDSAT_QA_CLOUD_BITS:
            cloud |= ((qa >> bit) & 1).astype(bool)
        shadow = ((qa >> LANDSAT_QA_SHADOW_BIT) & 1).astype(bool)
        cloud &= valid
        shadow &= valid
        fill = (qa & 1).astype(bool)
        valid &= ~fill
        cloud &= valid
        shadow &= valid
    elif kind == "cloud_prob":
        cloud = (data >= 50) & valid
    elif kind == "cloud_mask":
        cloud = (data > 0) & valid
    elif kind == "shadow_mask":
        shadow = (data > 0) & valid

    classified = np.zeros(data.shape, dtype=np.uint8)
    classified[cloud] = 1
    classified[shadow & ~cloud] = 2

    total_valid = int(valid.sum())
    cloud_count = int(cloud.sum())
    shadow_count = int(shadow.sum())
    clear_count = int(total_valid - cloud_count - shadow_count) if total_valid else 0

    return {
        "classified": classified,
        "band_index": band_index,
        "kind": kind,
        "label": label,
        "cloud_pixel_count": cloud_count,
        "shadow_pixel_count": shadow_count,
        "clear_pixel_count": max(clear_count, 0),
        "valid_pixel_count": total_valid,
        "cloud_fraction": float(cloud_count / total_valid) if total_valid else 0.0,
        "shadow_fraction": float(shadow_count / total_valid) if total_valid else 0.0,
    }


def write_class_mask(src: rasterio.DatasetReader, classified: np.ndarray, output_path: Path) -> None:
    profile = src.profile.copy()
    profile.update(driver="GTiff", count=1, dtype="uint8", nodata=255)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(classified, 1)
        dst.set_band_description(1, "cloud_shadow_class")
        dst.update_tags(MASK_TYPE="cloud_shadow", CLASS_0="clear", CLASS_1="cloud", CLASS_2="shadow")

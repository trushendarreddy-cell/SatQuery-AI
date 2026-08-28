import uuid
from pathlib import Path
from typing import Union, List, Optional, Dict, Any
import numpy as np
from PIL import Image, ExifTags
import rasterio
from rasterio.warp import transform_bounds

from app.schemas.metadata_schema import (
    ImageCategory,
    SensorModality,
    UnifiedImageMetadata,
    GeospatialProfile,
    VisualProfile,
    BoundingBoxNative,
    BoundingBoxWGS84,
    Resolution,
    BandSummary,
)


class UniversalMetadataExtractor:
    """Extracts metadata from visual imagery (JPG/PNG) or georeferenced rasters (GeoTIFF)."""

    @classmethod
    def extract(
        cls,
        file_path: Union[str, Path],
        category: ImageCategory,
        image_id: Optional[str] = None,
        compute_stats: bool = True,
    ) -> UnifiedImageMetadata:
        """
        Extracts structured metadata according to the detected category.
        
        Guarantees:
        - JPG/PNG will NEVER fabricate CRS, coordinates, or spatial resolution.
        - Arbitrary RGB JPG/PNG is classified as 'visual_standard', not assumed to be satellite imagery.
        - GeoTIFF will extract full geospatial profiles with WGS84 coordinates and acquisition timestamps.
        """
        path = Path(file_path)
        img_id = image_id or uuid.uuid4().hex[:8]

        if category == ImageCategory.GEOSPATIAL_GEOTIFF:
            return cls._extract_geotiff_metadata(path, img_id, compute_stats)
        else:
            return cls._extract_visual_metadata(path, img_id)

    @classmethod
    def _extract_visual_metadata(cls, path: Path, image_id: str) -> UnifiedImageMetadata:
        """Extracts properties from standard visual images (JPG, PNG, etc.)."""
        with Image.open(path) as img:
            w, h = img.size
            mode = img.mode
            channels = len(img.getbands())
            fmt = img.format or path.suffix.lstrip(".").upper()

            # Rule: Do not assume arbitrary JPG/PNG is satellite optical imagery.
            # Label as VISUAL_STANDARD (or GRAYSCALE_SINGLE_BAND for 1-channel).
            if mode in ["L", "1"]:
                modality = SensorModality.GRAYSCALE_SINGLE_BAND
            else:
                modality = SensorModality.VISUAL_STANDARD

            visual_profile = VisualProfile(
                color_mode=mode,
                channel_count=channels,
                bit_depth=8,  # Standard 8-bit per channel
            )

            # Optional: Extract EXIF DateTime if available in JPG/PNG
            acquisition_date = cls._extract_exif_datetime(img)

            return UnifiedImageMetadata(
                image_id=image_id,
                filename=path.name,
                format=fmt,
                category=ImageCategory.VISUAL_STANDARD,
                modality=modality,
                has_geospatial_metadata=False,  # Explicitly False
                width=w,
                height=h,
                channels=channels,
                file_size_bytes=int(path.stat().st_size),
                acquisition_date=acquisition_date,
                geospatial=None,  # NEVER fabricate geospatial metadata
                visual=visual_profile,
            )

    @classmethod
    def _extract_geotiff_metadata(
        cls, path: Path, image_id: str, compute_stats: bool = True
    ) -> UnifiedImageMetadata:
        """Extracts complete geospatial and spectral profile from a GeoTIFF."""
        with rasterio.open(path) as src:
            # 1. Native bounds
            bounds_native = BoundingBoxNative(
                min_x=float(src.bounds.left),
                min_y=float(src.bounds.bottom),
                max_x=float(src.bounds.right),
                max_y=float(src.bounds.top),
            )

            # 2. Bounding Box in WGS84 Lat/Lon (EPSG:4326)
            bounds_wgs84: Optional[BoundingBoxWGS84] = None
            if src.crs:
                try:
                    wgs84_bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                    bounds_wgs84 = BoundingBoxWGS84(
                        min_lon=float(wgs84_bounds[0]),
                        min_lat=float(wgs84_bounds[1]),
                        max_lon=float(wgs84_bounds[2]),
                        max_lat=float(wgs84_bounds[3]),
                    )
                except Exception:
                    bounds_wgs84 = None

            # 3. Spatial resolution
            unit = "unknown"
            if src.crs:
                if src.crs.is_projected:
                    unit = getattr(src.crs, "linear_units", "metre")
                elif src.crs.is_geographic:
                    unit = "degree"

            res_x, res_y = src.res
            resolution = Resolution(
                x_resolution=float(abs(res_x)),
                y_resolution=float(abs(res_y)),
                unit=unit,
            )

            # 4. Band profiles and stats
            bands: List[BandSummary] = []
            for idx in range(1, src.count + 1):
                dtype_name = str(src.dtypes[idx - 1])
                nodata = src.nodatavals[idx - 1]
                nodata_float = float(nodata) if nodata is not None else None

                min_val, max_val, mean_val = None, None, None
                if compute_stats:
                    try:
                        band_data = src.read(idx, masked=True)
                        if band_data.count() > 0:
                            min_val = float(np.nanmin(band_data))
                            max_val = float(np.nanmax(band_data))
                            mean_val = float(np.nanmean(band_data))
                    except Exception:
                        pass

                bands.append(
                    BandSummary(
                        band_index=idx,
                        data_type=dtype_name,
                        nodata_value=nodata_float,
                        min_value=min_val,
                        max_value=max_val,
                        mean_value=mean_val,
                    )
                )

            # 5. Extract Acquisition Date from tags
            acquisition_date = cls._extract_geotiff_acquisition_date(src)

            # 6. Evidence-based modality classification
            modality = cls._classify_geotiff_modality(src)

            geospatial_profile = GeospatialProfile(
                crs=src.crs.to_string() if src.crs else "UNKNOWN",
                is_projected=src.crs.is_projected if src.crs else False,
                bounds_native=bounds_native,
                bounds_wgs84=bounds_wgs84,
                resolution=resolution,
                bands=bands,
                acquisition_date=acquisition_date,
            )

            return UnifiedImageMetadata(
                image_id=image_id,
                filename=path.name,
                format=src.driver,
                category=ImageCategory.GEOSPATIAL_GEOTIFF,
                modality=modality,
                has_geospatial_metadata=True,  # Explicitly True
                width=int(src.width),
                height=int(src.height),
                channels=int(src.count),
                file_size_bytes=int(path.stat().st_size),
                acquisition_date=acquisition_date,
                geospatial=geospatial_profile,
                visual=None,
            )

    @classmethod
    def _extract_geotiff_acquisition_date(cls, src: rasterio.DatasetReader) -> Optional[str]:
        """Searches raster tags for acquisition timestamp metadata."""
        tags = src.tags()
        # Check standard raster tags
        candidate_keys = [
            "TIFFTAG_DATETIME",
            "DATETIME",
            "ACQUISITION_DATETIME",
            "ACQUISITION_DATE",
            "PROCESSING_DATETIME",
            "IMAGE_DATE",
            "SCENE_ACQUISITION_TIME",
        ]
        for key in candidate_keys:
            if key in tags:
                return str(tags[key]).strip()
            # Also check lowercase or capitalized
            for tag_k, tag_v in tags.items():
                if tag_k.upper() == key:
                    return str(tag_v).strip()

        # Check subdataset or namespaces if available
        try:
            for ns in ["TIFF", "IMAGE_STRUCTURE", "ENVI"]:
                ns_tags = src.tags(ns=ns)
                for key in candidate_keys:
                    if key in ns_tags:
                        return str(ns_tags[key]).strip()
        except Exception:
            pass

        return None

    @classmethod
    def _extract_exif_datetime(cls, img: Image.Image) -> Optional[str]:
        """Extracts DateTime from EXIF tags in photographic images if present."""
        try:
            exif = img.getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    if tag_name in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
                        return str(value).strip()
        except Exception:
            pass
        return None

    @classmethod
    def _classify_geotiff_modality(cls, src: rasterio.DatasetReader) -> SensorModality:
        """Classifies sensor modality based on band count, descriptions, and tags."""
        tags = src.tags()
        tags_str = str(tags).upper()
        descriptions = [str(d).upper() for d in (src.descriptions or []) if d]

        # Check for SAR / Radar indicators (polarization channels VV, VH, HH, HV)
        sar_keywords = ["VV", "VH", "HH", "HV", "SAR", "SENTINEL-1", "POLARIZATION"]
        if any(kw in tags_str for kw in sar_keywords) or any(
            any(kw in d for kw in sar_keywords) for d in descriptions
        ):
            return SensorModality.SAR_RADAR

        # Multispectral (4+ spectral bands, e.g. Sentinel-2 L2A / Landsat)
        if src.count >= 4:
            return SensorModality.OPTICAL_MULTISPECTRAL

        # 3-band Optical (RGB or false color)
        if src.count == 3:
            return SensorModality.OPTICAL_RGB

        # 1-band Grayscale / Elevation / Single band
        if src.count == 1:
            return SensorModality.GRAYSCALE_SINGLE_BAND

        return SensorModality.UNKNOWN

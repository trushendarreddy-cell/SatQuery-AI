import uuid
from typing import Optional, Dict, Any

import rasterio

from app.core.session_cache import session_manager
from app.geospatial.area import area_breakdown, calculate_geojson_area
from app.geospatial.cloud_mask import classify_cloud_shadow, write_class_mask
from app.geospatial.seasonal import evaluate_seasonal_risk
from app.geospatial.vectorize import polygonize_mask_file
from app.geospatial.zonal import compute_zonal_statistics
from app.geospatial.spectral_index import compute_ndvi, compute_evi, compute_ndwi
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.analysis_schema import (
    AreaResult,
    CloudMaskResult,
    CloudMaskStatus,
    MaskToGeoJSONResult,
    SeasonalFilterResult,
    SeasonalRisk,
    SpectralIndexResult,
    SpectralIndexType,
    ZonalBandStats,
    ZonalStatsResult,
)
from app.schemas.metadata_schema import ImageCategory


def _session_image(session_id: str, image_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        return None, None, None, f"Session '{session_id}' not found."
    meta = session.images.get(image_id)
    if not meta:
        return session, None, None, f"Image '{image_id}' not found in session '{session_id}'."
    path = session_manager.get_image_file_path(session_id, image_id)
    if not path or not path.exists():
        return session, meta, None, "Underlying raster file path could not be located on disk."
    return session, meta, path, None


def detect_clouds_and_shadows(session_id: str, image_id: str) -> CloudMaskResult:
    """Build a cloud/shadow class mask from SCL/QA/cloud-product bands only."""
    session, meta, path, err = _session_image(session_id, image_id)
    if err or meta is None or path is None:
        return CloudMaskResult(
            success=False,
            status=CloudMaskStatus.NOT_PERFORMED,
            session_id=session_id,
            image_id=image_id,
            message=err or "Unable to load image.",
            warnings=[err] if err else [],
        )

    if not meta.has_geospatial_metadata or not meta.geospatial:
        return CloudMaskResult(
            success=False,
            status=CloudMaskStatus.NOT_PERFORMED,
            session_id=session_id,
            image_id=image_id,
            message="Cloud masking requires a georeferenced raster with QA/SCL evidence. Visual images are not used.",
            warnings=["Image lacks geospatial metadata. No cloud information was fabricated."],
        )

    try:
        with rasterio.open(path) as src:
            if not src.crs:
                return CloudMaskResult(
                    success=False,
                    status=CloudMaskStatus.NOT_PERFORMED,
                    session_id=session_id,
                    image_id=image_id,
                    message="Raster has no CRS. Cloud masking was not performed.",
                    warnings=["CRS is missing; no cloud mask was invented."],
                )
            classified = classify_cloud_shadow(src)
            if classified is None:
                return CloudMaskResult(
                    success=False,
                    status=CloudMaskStatus.NOT_PERFORMED,
                    session_id=session_id,
                    image_id=image_id,
                    message="No SCL, QA_PIXEL, cloud-probability, or cloud-mask band was found. Masking was not performed.",
                    warnings=["Insufficient QA/cloud evidence. Brightness-based cloud detection is not used."],
                )

            mask_id = uuid.uuid4().hex[:8]
            filename = f"cloud_mask_{image_id}_{mask_id}.tif"
            out_path = session.session_dir / filename
            write_class_mask(src, classified["classified"], out_path)

        mask_meta = UniversalMetadataExtractor.extract(
            file_path=out_path,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            image_id=mask_id,
            compute_stats=True,
        )
        session_manager.add_image(session_id, out_path, mask_meta)
        cloud_frac = round(float(classified["cloud_fraction"]), 4)
        shadow_frac = round(float(classified["shadow_fraction"]), 4)
        return CloudMaskResult(
            success=True,
            status=CloudMaskStatus.PERFORMED,
            session_id=session_id,
            image_id=image_id,
            mask_image_id=mask_id,
            artifact_filename=filename,
            qa_band_index=int(classified["band_index"]),
            qa_band_name=classified["label"],
            cloud_pixel_count=int(classified["cloud_pixel_count"]),
            shadow_pixel_count=int(classified["shadow_pixel_count"]),
            clear_pixel_count=int(classified["clear_pixel_count"]),
            cloud_fraction=cloud_frac,
            shadow_fraction=shadow_frac,
            message=f"Cloud/shadow mask produced from {classified['kind']} band {classified['band_index']}.",
            messages=[
                f"QA product kind: {classified['kind']}.",
                f"Cloud pixels: {classified['cloud_pixel_count']}; shadow pixels: {classified['shadow_pixel_count']}.",
            ],
            mask_metadata=mask_meta,
        )
    except Exception as exc:
        return CloudMaskResult(
            success=False,
            status=CloudMaskStatus.NOT_PERFORMED,
            session_id=session_id,
            image_id=image_id,
            message=f"Cloud masking failed: {str(exc)}",
            warnings=[str(exc)],
        )


def filter_seasonal_false_positives(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
    mask_image_id: Optional[str] = None,
) -> SeasonalFilterResult:
    """Evaluate seasonal risk. Does not confirm real events or invent phenology."""
    _, meta1, _, err1 = _session_image(session_id, image_id_1)
    if err1 or meta1 is None:
        return SeasonalFilterResult(
            success=False,
            session_id=session_id,
            image_id_1=image_id_1,
            image_id_2=image_id_2,
            mask_image_id=mask_image_id,
            seasonal_risk=SeasonalRisk.UNKNOWN,
            event_confirmed=False,
            message=err1 or "Image 1 unavailable.",
            warnings=[err1] if err1 else [],
        )
    _, meta2, _, err2 = _session_image(session_id, image_id_2)
    if err2 or meta2 is None:
        return SeasonalFilterResult(
            success=False,
            session_id=session_id,
            image_id_1=image_id_1,
            image_id_2=image_id_2,
            mask_image_id=mask_image_id,
            seasonal_risk=SeasonalRisk.UNKNOWN,
            event_confirmed=False,
            message=err2 or "Image 2 unavailable.",
            warnings=[err2] if err2 else [],
        )

    risk, same_window, doy_delta, time_delta, explanation = evaluate_seasonal_risk(
        meta1.acquisition_date, meta2.acquisition_date
    )

    warnings = []
    if risk == SeasonalRisk.UNKNOWN:
        warnings.append(explanation)
    if risk in {SeasonalRisk.HIGH, SeasonalRisk.MODERATE}:
        warnings.append("Change is not claimed as a real event without independent confirmation.")

    if mask_image_id:
        _, mask_meta, _, mask_err = _session_image(session_id, mask_image_id)
        if mask_err:
            return SeasonalFilterResult(
                success=False,
                session_id=session_id,
                image_id_1=image_id_1,
                image_id_2=image_id_2,
                mask_image_id=mask_image_id,
                seasonal_risk=risk,
                same_phenological_window=same_window,
                day_of_year_delta=doy_delta,
                time_delta_days=time_delta,
                event_confirmed=False,
                message=mask_err,
                warnings=[mask_err],
            )
        warnings.append(
            "Mask pixels were not removed: no identified RED/NIR phenology bands to justify filtering."
        )

    success = risk != SeasonalRisk.UNKNOWN
    return SeasonalFilterResult(
        success=success,
        session_id=session_id,
        image_id_1=image_id_1,
        image_id_2=image_id_2,
        mask_image_id=mask_image_id,
        seasonal_risk=risk,
        same_phenological_window=same_window,
        day_of_year_delta=doy_delta,
        time_delta_days=time_delta,
        event_confirmed=False,
        mask_modified=False,
        filtered_mask_image_id=mask_image_id,
        message=explanation,
        messages=[explanation],
        warnings=warnings,
    )


def mask_to_geojson(
    session_id: str,
    image_id: str,
    band_index: int = 1,
    min_value: float = 1.0,
) -> MaskToGeoJSONResult:
    """Polygonize a binary/classified mask into frontend-ready EPSG:4326 GeoJSON."""
    empty_fc = {"type": "FeatureCollection", "features": []}
    _, meta, path, err = _session_image(session_id, image_id)
    if err or meta is None or path is None:
        return MaskToGeoJSONResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            feature_count=0,
            geojson=empty_fc,
            message=err or "Unable to load mask.",
            warnings=[err] if err else [],
        )
    if not meta.has_geospatial_metadata or not meta.geospatial:
        return MaskToGeoJSONResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            feature_count=0,
            geojson=empty_fc,
            message="Mask vectorization requires a georeferenced raster. Coordinates are not invented for visual images.",
            warnings=["Image lacks geospatial metadata."],
        )
    try:
        payload = polygonize_mask_file(path, band_index=band_index, min_value=min_value)
        fc = payload["geojson"]
        features = fc.get("features") or []
        area_m2, n = calculate_geojson_area(fc)
        breakdown = area_breakdown(area_m2)
        msg = (
            "Mask contains no valid pixels; empty FeatureCollection returned."
            if n == 0
            else f"Polygonized {n} mask feature(s) to EPSG:4326 GeoJSON."
        )
        return MaskToGeoJSONResult(
            success=True,
            session_id=session_id,
            image_id=image_id,
            feature_count=int(n),
            geojson=fc,
            area_m2=breakdown["area_m2"],
            area_ha=breakdown["area_ha"],
            area_sqkm=breakdown["area_sqkm"],
            source_crs=payload["source_crs"],
            message=msg,
            messages=[msg],
        )
    except Exception as exc:
        return MaskToGeoJSONResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            feature_count=0,
            geojson=empty_fc,
            message=f"Mask vectorization failed: {str(exc)}",
            warnings=[str(exc)],
        )


def calculate_spatial_area(geojson: Dict[str, Any]) -> AreaResult:
    """Geodesic area of WGS84 GeoJSON in m², hectares, and km²."""
    try:
        area_m2, count = calculate_geojson_area(geojson)
        breakdown = area_breakdown(area_m2)
        if count == 0:
            return AreaResult(
                success=True,
                feature_count=0,
                area_m2=0.0,
                area_ha=0.0,
                area_sqkm=0.0,
                message="No polygon geometries found; area is 0.",
                messages=["Empty geometry produces zero geodesic area."],
            )
        return AreaResult(
            success=True,
            feature_count=int(count),
            area_m2=breakdown["area_m2"],
            area_ha=breakdown["area_ha"],
            area_sqkm=breakdown["area_sqkm"],
            message=f"Geodesic area: {breakdown['area_ha']} ha ({breakdown['area_sqkm']} km²).",
        )
    except Exception as exc:
        return AreaResult(
            success=False,
            message=f"Area calculation failed: {str(exc)}",
            warnings=[str(exc)],
        )


def calculate_spatial_statistics(
    session_id: str,
    image_id: str,
    mask_image_id: Optional[str] = None,
    geometry: Optional[Dict[str, Any]] = None,
    band_index: Optional[int] = None,
) -> ZonalStatsResult:
    """Per-band statistics over nodata-aware pixels, optional mask, and optional GeoJSON zone."""
    _, meta, path, err = _session_image(session_id, image_id)
    if err or meta is None or path is None:
        return ZonalStatsResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            mask_image_id=mask_image_id,
            message=err or "Unable to load raster.",
            warnings=[err] if err else [],
        )
    if not meta.has_geospatial_metadata or not meta.geospatial:
        return ZonalStatsResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            mask_image_id=mask_image_id,
            message="Zonal statistics require a georeferenced raster. Visual images are rejected.",
            warnings=["Image lacks geospatial metadata."],
        )

    mask_path = None
    if mask_image_id:
        _, mask_meta, mask_path, mask_err = _session_image(session_id, mask_image_id)
        if mask_err or mask_path is None:
            return ZonalStatsResult(
                success=False,
                session_id=session_id,
                image_id=image_id,
                mask_image_id=mask_image_id,
                message=mask_err or "Mask raster unavailable.",
                warnings=[mask_err] if mask_err else [],
            )

    try:
        rows = compute_zonal_statistics(
            raster_path=path,
            mask_path=mask_path,
            geometry=geometry,
            band_index=band_index,
        )
        bands = [ZonalBandStats(**row) for row in rows]
        return ZonalStatsResult(
            success=True,
            session_id=session_id,
            image_id=image_id,
            mask_image_id=mask_image_id,
            used_geometry=geometry is not None,
            used_mask=mask_path is not None,
            bands=bands,
            message="Zonal statistics computed over valid pixels.",
        )
    except Exception as exc:
        return ZonalStatsResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            mask_image_id=mask_image_id,
            message=f"Zonal statistics failed: {str(exc)}",
            warnings=[str(exc)],
        )


def compute_spectral_index(
    session_id: str,
    image_id: str,
    index_type: SpectralIndexType = SpectralIndexType.NDVI,
    red_band: int = 3,
    nir_band: int = 4,
    blue_band: Optional[int] = None,
    green_band: Optional[int] = None,
) -> SpectralIndexResult:
    """
    Computes a spectral index raster from a single multispectral GeoTIFF.

    Band mapping is explicit: callers supply 1-based band indices because the
    existing metadata model does not reliably identify spectral band identities
    from GeoTIFF tags alone.
    """
    session, meta, path, err = _session_image(session_id, image_id)
    if err or meta is None or path is None:
        return SpectralIndexResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            index_type=index_type.value,
            index_image_id="",
            artifact_filename="",
            width=0,
            height=0,
            band_count=1,
            crs="",
            transform=[0, 1, 0, 0, 0, 1],
            red_band=red_band,
            nir_band=nir_band,
            blue_band=blue_band,
            green_band=green_band,
            valid_pixel_count=0,
            nodata_pixel_count=0,
            min_value=None,
            max_value=None,
            mean_value=None,
            message=err or "Unable to load image.",
            warnings=[err] if err else [],
        )

    if not meta.has_geospatial_metadata or not meta.geospatial:
        return SpectralIndexResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            index_type=index_type.value,
            index_image_id="",
            artifact_filename="",
            width=0,
            height=0,
            band_count=1,
            crs="",
            transform=[0, 1, 0, 0, 0, 1],
            red_band=red_band,
            nir_band=nir_band,
            blue_band=blue_band,
            green_band=green_band,
            valid_pixel_count=0,
            nodata_pixel_count=0,
            min_value=None,
            max_value=None,
            mean_value=None,
            message="Spectral index requires a georeferenced raster. Visual images are not used.",
            warnings=["Image lacks geospatial metadata. No spectral index was fabricated."],
        )

    try:
        with rasterio.open(path) as src:
            if not src.crs:
                return SpectralIndexResult(
                    success=False,
                    session_id=session_id,
                    image_id=image_id,
                    index_type=index_type.value,
                    index_image_id="",
                    artifact_filename="",
                    width=0,
                    height=0,
                    band_count=1,
                    crs="",
                    transform=[0, 1, 0, 0, 0, 1],
                    red_band=red_band,
                    nir_band=nir_band,
                    blue_band=blue_band,
                    green_band=green_band,
                    valid_pixel_count=0,
                    nodata_pixel_count=0,
                    min_value=None,
                    max_value=None,
                    mean_value=None,
                    message="Raster has no CRS. Spectral index was not computed.",
                    warnings=["CRS is missing; no index raster was invented."],
                )
            if red_band < 1 or red_band > src.count:
                return SpectralIndexResult(
                    success=False,
                    session_id=session_id,
                    image_id=image_id,
                    index_type=index_type.value,
                    index_image_id="",
                    artifact_filename="",
                    width=0,
                    height=0,
                    band_count=1,
                    crs=src.crs.to_string() if src.crs else "",
                    transform=[float(src.transform.c), float(src.transform.a), float(src.transform.b),
                               float(src.transform.d), float(src.transform.e), float(src.transform.f)],
                    red_band=red_band,
                    nir_band=nir_band,
                    blue_band=blue_band,
                    green_band=green_band,
                    valid_pixel_count=0,
                    nodata_pixel_count=0,
                    min_value=None,
                    max_value=None,
                    mean_value=None,
                    message=f"Red band {red_band} does not exist; raster has {src.count} bands.",
                    warnings=[f"Requested red band {red_band} is out of range."],
                )
            if nir_band < 1 or nir_band > src.count:
                return SpectralIndexResult(
                    success=False,
                    session_id=session_id,
                    image_id=image_id,
                    index_type=index_type.value,
                    index_image_id="",
                    artifact_filename="",
                    width=0,
                    height=0,
                    band_count=1,
                    crs=src.crs.to_string() if src.crs else "",
                    transform=[float(src.transform.c), float(src.transform.a), float(src.transform.b),
                               float(src.transform.d), float(src.transform.e), float(src.transform.f)],
                    red_band=red_band,
                    nir_band=nir_band,
                    blue_band=blue_band,
                    green_band=green_band,
                    valid_pixel_count=0,
                    nodata_pixel_count=0,
                    min_value=None,
                    max_value=None,
                    mean_value=None,
                    message=f"NIR band {nir_band} does not exist; raster has {src.count} bands.",
                    warnings=[f"Requested NIR band {nir_band} is out of range."],
                )

        index_uuid = uuid.uuid4().hex[:8]
        if index_type == SpectralIndexType.NDVI:
            index_filename = f"ndvi_{image_id}_{index_uuid}.tif"
            index_path = session.session_dir / index_filename
            result = compute_ndvi(
                red_path=path,
                nir_path=path,
                output_path=index_path,
                red_band=red_band,
                nir_band=nir_band,
            )
        elif index_type == SpectralIndexType.EVI:
            if blue_band is None:
                return SpectralIndexResult(
                    success=False,
                    session_id=session_id,
                    image_id=image_id,
                    index_type=index_type.value,
                    index_image_id="",
                    artifact_filename="",
                    width=0,
                    height=0,
                    band_count=1,
                    crs="",
                    transform=[0, 1, 0, 0, 0, 1],
                    red_band=red_band,
                    nir_band=nir_band,
                    blue_band=blue_band,
                    green_band=green_band,
                    valid_pixel_count=0,
                    nodata_pixel_count=0,
                    min_value=None,
                    max_value=None,
                    mean_value=None,
                    message="EVI requires blue_band.",
                    warnings=["blue_band is required for EVI computation."],
                )
            index_filename = f"evi_{image_id}_{index_uuid}.tif"
            index_path = session.session_dir / index_filename
            result = compute_evi(
                red_path=path,
                nir_path=path,
                blue_path=path,
                output_path=index_path,
                red_band=red_band,
                nir_band=nir_band,
                blue_band=blue_band,
            )
        elif index_type == SpectralIndexType.NDWI:
            if green_band is None:
                return SpectralIndexResult(
                    success=False,
                    session_id=session_id,
                    image_id=image_id,
                    index_type=index_type.value,
                    index_image_id="",
                    artifact_filename="",
                    width=0,
                    height=0,
                    band_count=1,
                    crs="",
                    transform=[0, 1, 0, 0, 0, 1],
                    red_band=red_band,
                    nir_band=nir_band,
                    blue_band=blue_band,
                    green_band=green_band,
                    valid_pixel_count=0,
                    nodata_pixel_count=0,
                    min_value=None,
                    max_value=None,
                    mean_value=None,
                    message="NDWI requires green_band.",
                    warnings=["green_band is required for NDWI computation."],
                )
            index_filename = f"ndwi_{image_id}_{index_uuid}.tif"
            index_path = session.session_dir / index_filename
            result = compute_ndwi(
                green_path=path,
                nir_path=path,
                output_path=index_path,
                green_band=green_band,
                nir_band=nir_band,
            )
        else:
            return SpectralIndexResult(
                success=False,
                session_id=session_id,
                image_id=image_id,
                index_type=index_type.value,
                index_image_id="",
                artifact_filename="",
                width=0,
                height=0,
                band_count=1,
                crs="",
                transform=[0, 1, 0, 0, 0, 1],
                red_band=red_band,
                nir_band=nir_band,
                blue_band=blue_band,
                green_band=green_band,
                valid_pixel_count=0,
                nodata_pixel_count=0,
                min_value=None,
                max_value=None,
                mean_value=None,
                message=f"Spectral index '{index_type.value}' is not implemented.",
                warnings=[f"Index type '{index_type.value}' is not supported."],
            )

        index_meta = UniversalMetadataExtractor.extract(
            file_path=index_path,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            image_id=index_uuid,
            compute_stats=False,
        )
        session_manager.add_image(session_id, index_path, index_meta)

        return SpectralIndexResult(
            success=True,
            session_id=session_id,
            image_id=image_id,
            index_type=index_type.value,
            index_image_id=index_uuid,
            artifact_filename=index_filename,
            width=result["width"],
            height=result["height"],
            band_count=1,
            crs=result["crs"],
            transform=result["transform"],
            red_band=result.get("red_band", red_band),
            nir_band=result.get("nir_band", nir_band),
            blue_band=result.get("blue_band", blue_band),
            green_band=result.get("green_band", green_band),
            valid_pixel_count=result["valid_pixel_count"],
            nodata_pixel_count=result["nodata_pixel_count"],
            min_value=result["min_value"],
            max_value=result["max_value"],
            mean_value=result["mean_value"],
            message=result["message"],
            messages=[f"{index_type.value.upper()} raster written to '{index_filename}'."],
            warnings=[],
            index_metadata=index_meta,
        )
    except Exception as exc:
        return SpectralIndexResult(
            success=False,
            session_id=session_id,
            image_id=image_id,
            index_type=index_type.value,
            index_image_id="",
            artifact_filename="",
            width=0,
            height=0,
            band_count=1,
            crs="",
            transform=[0, 1, 0, 0, 0, 1],
            red_band=red_band,
            nir_band=nir_band,
            blue_band=blue_band,
            green_band=green_band,
            valid_pixel_count=0,
            nodata_pixel_count=0,
            min_value=None,
            max_value=None,
            mean_value=None,
            message=f"Spectral index computation failed: {str(exc)}",
            warnings=[str(exc)],
        )

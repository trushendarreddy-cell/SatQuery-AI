from fastapi import APIRouter, status

from app.schemas.analysis_schema import (
    AreaRequest,
    AreaResult,
    CloudMaskRequest,
    CloudMaskResult,
    MaskToGeoJSONRequest,
    MaskToGeoJSONResult,
    SeasonalFilterRequest,
    SeasonalFilterResult,
    SpectralIndexRequest,
    SpectralIndexResult,
    ZonalStatsRequest,
    ZonalStatsResult,
)
from app.pipeline.analysis import (
    calculate_spatial_area,
    calculate_spatial_statistics,
    compute_spectral_index,
    detect_clouds_and_shadows,
    filter_seasonal_false_positives,
    mask_to_geojson,
)

router = APIRouter()


@router.post("/cloud-mask", response_model=CloudMaskResult, status_code=status.HTTP_200_OK)
async def api_cloud_mask(payload: CloudMaskRequest):
    return detect_clouds_and_shadows(payload.session_id, payload.image_id)


@router.post("/seasonal-filter", response_model=SeasonalFilterResult, status_code=status.HTTP_200_OK)
async def api_seasonal_filter(payload: SeasonalFilterRequest):
    return filter_seasonal_false_positives(
        payload.session_id,
        payload.image_id_1,
        payload.image_id_2,
        payload.mask_image_id,
    )


@router.post("/mask-to-geojson", response_model=MaskToGeoJSONResult, status_code=status.HTTP_200_OK)
async def api_mask_to_geojson(payload: MaskToGeoJSONRequest):
    return mask_to_geojson(
        payload.session_id,
        payload.image_id,
        payload.band_index,
        payload.min_value,
    )


@router.post("/area", response_model=AreaResult, status_code=status.HTTP_200_OK)
async def api_area(payload: AreaRequest):
    return calculate_spatial_area(payload.geojson)


@router.post("/zonal-stats", response_model=ZonalStatsResult, status_code=status.HTTP_200_OK)
async def api_zonal_stats(payload: ZonalStatsRequest):
    return calculate_spatial_statistics(
        payload.session_id,
        payload.image_id,
        payload.mask_image_id,
        payload.geometry,
        payload.band_index,
    )


@router.post("/spectral-index", response_model=SpectralIndexResult, status_code=status.HTTP_200_OK)
async def api_spectral_index(payload: SpectralIndexRequest):
    return compute_spectral_index(
        session_id=payload.session_id,
        image_id=payload.image_id,
        index_type=payload.index_type,
        red_band=payload.red_band,
        nir_band=payload.nir_band,
        blue_band=payload.blue_band,
        green_band=payload.green_band,
    )

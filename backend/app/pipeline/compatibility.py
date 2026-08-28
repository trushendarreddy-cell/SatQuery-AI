from typing import Optional, Dict, Any, List
import rasterio

from app.core.session_cache import session_manager
from app.pipeline.scene_classifier import SceneClassifier
from app.pipeline.overlap import SpatialOverlapEngine
from app.schemas.metadata_schema import UnifiedImageMetadata, ImageCategory
from app.schemas.spatial_schema import (
    CompatibilityResult,
    TemporalCompatibility,
    ResolutionCompatibility,
    CRSCompatibility,
    SpatialOverlapOverview,
    GridAlignmentOverview,
)


class CompatibilityEngine:
    """Evaluates multi-factor compatibility (temporal, spatial, resolution, CRS, grid) for comparison."""

    # Explicit documented thresholds
    RESOLUTION_RATIO_HIGH_THRESHOLD = 2.0
    RESOLUTION_RATIO_MAX_THRESHOLD = 3.5

    @classmethod
    def evaluate(
        cls,
        meta1: UnifiedImageMetadata,
        meta2: UnifiedImageMetadata,
        session_id: str,
    ) -> CompatibilityResult:
        """
        Evaluates whether two images are suitable for multi-temporal or multi-sensor comparison.
        """
        messages = []
        warnings = []
        recommendations = []

        # 1. Check for unreferenced visual images
        if not meta1.has_geospatial_metadata or not meta1.geospatial:
            return cls._unreferenced_response(session_id, meta1, meta2)

        if not meta2.has_geospatial_metadata or not meta2.geospatial:
            return cls._unreferenced_response(session_id, meta2, meta1)

        # 2. Temporal Evaluation
        t_info = cls._evaluate_temporal(meta1, meta2)

        # 3. Resolution Evaluation
        r_info = cls._evaluate_resolution(meta1, meta2)

        # 4. CRS Evaluation
        crs_info = cls._evaluate_crs(meta1, meta2)

        # 5. Spatial Overlap Evaluation (Reusing Task 5 engine)
        overlap_result = SpatialOverlapEngine.calculate_overlap(meta1, meta2)
        spatial_info = SpatialOverlapOverview(
            overlap_exists=overlap_result.overlap_exists,
            overlap_percentage=overlap_result.overlap_percentage,
            intersection_area_sqkm=overlap_result.intersection_area_sqkm,
        )

        # 6. Grid Alignment Evaluation
        grid_info = cls._evaluate_grid(session_id, meta1.image_id, meta2.image_id)

        # 7. Synthesize Overall Compatibility & Recommendations
        is_compatible = True

        if not spatial_info.overlap_exists:
            is_compatible = False
            messages.append("Scenes do not geographically overlap.")
            warnings.append("Zero spatial overlap detected. Comparison is physically not possible.")
            recommendations.append("Select satellite scenes covering the same geographic area of interest.")

        if not r_info.compatible:
            is_compatible = False
            warnings.append(
                f"Resolution ratio ({r_info.ratio}x) exceeds recommended comparison threshold ({cls.RESOLUTION_RATIO_MAX_THRESHOLD}x)."
            )

        if spatial_info.overlap_exists:
            if not grid_info.is_aligned:
                recommendations.append(
                    f"Run 'align_images' to warp image '{meta2.image_id}' to the reference grid of '{meta1.image_id}' before pixel-by-pixel comparison."
                )
            else:
                messages.append("Images share identical CRS, spatial bounds, and pixel grid dimensions.")
                recommendations.append("Scenes are aligned and ready for change detection and spectral index calculations.")

        if t_info.has_dates and t_info.time_delta_days is not None:
            messages.append(
                f"Temporal baseline: {t_info.time_delta_days:.1f} days between earlier and later acquisitions."
            )
        elif not t_info.has_dates:
            warnings.append("Acquisition dates not found; chronological order cannot be determined automatically.")

        return CompatibilityResult(
            compatible=is_compatible,
            session_id=session_id,
            image_id_1=meta1.image_id,
            image_id_2=meta2.image_id,
            temporal=t_info,
            resolution=r_info,
            crs=crs_info,
            spatial=spatial_info,
            grid=grid_info,
            recommendations=recommendations,
            messages=messages,
            warnings=warnings,
        )

    @classmethod
    def _evaluate_temporal(
        cls, meta1: UnifiedImageMetadata, meta2: UnifiedImageMetadata
    ) -> TemporalCompatibility:
        d1_str, d2_str = meta1.acquisition_date, meta2.acquisition_date
        timestamps = {meta1.image_id: d1_str, meta2.image_id: d2_str}

        dt1 = SceneClassifier._parse_timestamp(d1_str) if d1_str else None
        dt2 = SceneClassifier._parse_timestamp(d2_str) if d2_str else None

        if dt1 and dt2:
            if dt1 <= dt2:
                earlier_id, later_id = meta1.image_id, meta2.image_id
                delta = (dt2 - dt1).total_seconds() / 86400.0
            else:
                earlier_id, later_id = meta2.image_id, meta1.image_id
                delta = (dt1 - dt2).total_seconds() / 86400.0

            return TemporalCompatibility(
                has_dates=True,
                time_delta_days=round(float(delta), 2),
                earlier_image_id=earlier_id,
                later_image_id=later_id,
                timestamps=timestamps,
            )

        return TemporalCompatibility(
            has_dates=False,
            time_delta_days=None,
            earlier_image_id=None,
            later_image_id=None,
            timestamps=timestamps,
        )

    @classmethod
    def _evaluate_resolution(
        cls, meta1: UnifiedImageMetadata, meta2: UnifiedImageMetadata
    ) -> ResolutionCompatibility:
        res1 = [meta1.geospatial.resolution.x_resolution, meta1.geospatial.resolution.y_resolution]
        res2 = [meta2.geospatial.resolution.x_resolution, meta2.geospatial.resolution.y_resolution]
        unit = meta1.geospatial.resolution.unit or meta2.geospatial.resolution.unit or "metre"

        mean_res1 = sum(res1) / len(res1)
        mean_res2 = sum(res2) / len(res2)

        min_r = min(mean_res1, mean_res2)
        max_r = max(mean_res1, mean_res2)

        ratio = round(float(max_r / min_r), 2) if min_r > 0 else 1.0

        if ratio <= cls.RESOLUTION_RATIO_HIGH_THRESHOLD:
            level = "high"
            compatible = True
        elif ratio <= cls.RESOLUTION_RATIO_MAX_THRESHOLD:
            level = "medium"
            compatible = True
        else:
            level = "low"
            compatible = False

        return ResolutionCompatibility(
            image_1_resolution=res1,
            image_2_resolution=res2,
            ratio=ratio,
            unit=unit,
            compatible=compatible,
            level=level,
        )

    @classmethod
    def _evaluate_crs(
        cls, meta1: UnifiedImageMetadata, meta2: UnifiedImageMetadata
    ) -> CRSCompatibility:
        crs1 = meta1.geospatial.crs or "UNKNOWN"
        crs2 = meta2.geospatial.crs or "UNKNOWN"
        same_crs = (crs1 == crs2) and (crs1 != "UNKNOWN")

        return CRSCompatibility(
            same_crs=same_crs,
            image_1_crs=crs1,
            image_2_crs=crs2,
            reprojection_required=not same_crs,
        )

    @classmethod
    def _evaluate_grid(
        cls, session_id: str, id1: str, id2: str
    ) -> GridAlignmentOverview:
        path1 = session_manager.get_image_file_path(session_id, id1)
        path2 = session_manager.get_image_file_path(session_id, id2)

        if not path1 or not path1.exists() or not path2 or not path2.exists():
            return GridAlignmentOverview(
                is_aligned=False, same_dimensions=False, same_transform=False
            )

        try:
            with rasterio.open(path1) as r1, rasterio.open(path2) as r2:
                same_dim = (r1.width == r2.width) and (r1.height == r2.height)
                same_t = (r1.transform == r2.transform)
                same_crs = (r1.crs == r2.crs)
                is_aligned = same_dim and same_t and same_crs
                return GridAlignmentOverview(
                    is_aligned=is_aligned,
                    same_dimensions=same_dim,
                    same_transform=same_t,
                )
        except Exception:
            return GridAlignmentOverview(
                is_aligned=False, same_dimensions=False, same_transform=False
            )

    @classmethod
    def _unreferenced_response(
        cls, session_id: str, unref_meta: UnifiedImageMetadata, other_meta: UnifiedImageMetadata
    ) -> CompatibilityResult:
        return CompatibilityResult(
            compatible=False,
            session_id=session_id,
            image_id_1=unref_meta.image_id,
            image_id_2=other_meta.image_id,
            temporal=TemporalCompatibility(has_dates=False),
            resolution=ResolutionCompatibility(
                image_1_resolution=[1.0, 1.0],
                image_2_resolution=[1.0, 1.0],
                ratio=1.0,
                unit="pixel",
                compatible=False,
                level="unreferenced",
            ),
            crs=CRSCompatibility(
                same_crs=False,
                image_1_crs="NONE",
                image_2_crs="NONE",
                reprojection_required=False,
            ),
            spatial=SpatialOverlapOverview(overlap_exists=False, overlap_percentage=0.0),
            grid=GridAlignmentOverview(is_aligned=False, same_dimensions=False, same_transform=False),
            recommendations=["Upload georeferenced GeoTIFFs to enable spatial and temporal compatibility analysis."],
            messages=[],
            warnings=[f"Image '{unref_meta.filename}' (ID: {unref_meta.image_id}) lacks geospatial metadata."],
        )


def check_compatibility(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
) -> CompatibilityResult:
    """
    Deterministic tool function to evaluate compatibility between two images in a session.
    Callable by AI Agent, services, or API endpoints.
    """
    session = session_manager.get_session(session_id)
    if not session:
        return CompatibilityResult(
            compatible=False,
            session_id=session_id,
            image_id_1=image_id_1,
            image_id_2=image_id_2,
            temporal=TemporalCompatibility(has_dates=False),
            resolution=ResolutionCompatibility(
                image_1_resolution=[], image_2_resolution=[], ratio=1.0, unit="unknown", compatible=False, level="unknown"
            ),
            crs=CRSCompatibility(same_crs=False, image_1_crs="UNKNOWN", image_2_crs="UNKNOWN", reprojection_required=False),
            spatial=SpatialOverlapOverview(overlap_exists=False, overlap_percentage=0.0),
            grid=GridAlignmentOverview(is_aligned=False, same_dimensions=False, same_transform=False),
            recommendations=[],
            messages=[],
            warnings=[f"Session '{session_id}' not found."],
        )

    meta1 = session.images.get(image_id_1)
    meta2 = session.images.get(image_id_2)

    if not meta1 or not meta2:
        missing_id = image_id_1 if not meta1 else image_id_2
        return CompatibilityResult(
            compatible=False,
            session_id=session_id,
            image_id_1=image_id_1,
            image_id_2=image_id_2,
            temporal=TemporalCompatibility(has_dates=False),
            resolution=ResolutionCompatibility(
                image_1_resolution=[], image_2_resolution=[], ratio=1.0, unit="unknown", compatible=False, level="unknown"
            ),
            crs=CRSCompatibility(same_crs=False, image_1_crs="UNKNOWN", image_2_crs="UNKNOWN", reprojection_required=False),
            spatial=SpatialOverlapOverview(overlap_exists=False, overlap_percentage=0.0),
            grid=GridAlignmentOverview(is_aligned=False, same_dimensions=False, same_transform=False),
            recommendations=[],
            messages=[],
            warnings=[f"Image '{missing_id}' not found in session '{session_id}'."],
        )

    return CompatibilityEngine.evaluate(meta1, meta2, session_id)

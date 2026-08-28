import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict

from app.schemas.metadata_schema import (
    UnifiedImageMetadata,
    ImageCategory,
    SensorModality,
)
from app.schemas.scene_schema import (
    SceneConfiguration,
    SceneClassificationResult,
    TemporalRelationship,
    ModalityRelationship,
    SpatialCompatibilityOverview,
)


class SceneClassifier:
    """Evidence-based classifier determining relationships between images in a session."""

    @classmethod
    def classify(cls, images: List[UnifiedImageMetadata], session_id: str) -> SceneClassificationResult:
        """
        Analyzes the collection of images in a session to identify scene configuration,
        sensor modalities, temporal baselines, and spatial compatibility.
        """
        image_count = len(images)
        image_ids = [img.image_id for img in images]
        messages = []
        warnings = []

        # 1. Modality Breakdown
        modality_rel = cls._analyze_modalities(images)

        # 2. Spatial Compatibility Overview
        spatial_overview = cls._analyze_spatial_overview(images)

        # 3. Temporal Relationship Analysis
        temporal_rel = cls._analyze_temporal_relationship(images)

        # 4. Classification Logic based on count, category, and evidence
        if image_count == 0:
            scene_config = SceneConfiguration.UNKNOWN
            confidence = "unverified"
            messages.append("No active images in session.")

        elif image_count == 1:
            scene_config = SceneConfiguration.SINGLE_IMAGE
            confidence = "high"
            img = images[0]
            if img.category == ImageCategory.GEOSPATIAL_GEOTIFF:
                messages.append(
                    f"Single georeferenced {img.modality.value.replace('_', ' ')} scene loaded."
                )
            else:
                messages.append("Single standard visual image loaded (unreferenced).")

        elif image_count == 2:
            scene_config, confidence, pair_messages, pair_warnings = cls._classify_pair(
                img1=images[0],
                img2=images[1],
                modality_rel=modality_rel,
                temporal_rel=temporal_rel,
                spatial_overview=spatial_overview,
            )
            messages.extend(pair_messages)
            warnings.extend(pair_warnings)

        else:
            # 3 or more images
            scene_config = SceneConfiguration.MULTI_IMAGE
            confidence = "medium"
            messages.append(
                f"Multi-image collection ({image_count} scenes) loaded in session."
            )
            if not spatial_overview.all_georeferenced:
                warnings.append("Collection contains a mix of georeferenced and non-georeferenced images.")

        return SceneClassificationResult(
            session_id=session_id,
            scene_config=scene_config,
            image_count=image_count,
            image_ids=image_ids,
            images=images,
            temporal_relationship=temporal_rel,
            modality_relationship=modality_rel,
            spatial_overview=spatial_overview,
            confidence=confidence,
            messages=messages,
            warnings=warnings,
        )

    @classmethod
    def _classify_pair(
        cls,
        img1: UnifiedImageMetadata,
        img2: UnifiedImageMetadata,
        modality_rel: ModalityRelationship,
        temporal_rel: Optional[TemporalRelationship],
        spatial_overview: SpatialCompatibilityOverview,
    ) -> Tuple[SceneConfiguration, str, List[str], List[str]]:
        """Classifies a 2-image input based on verifiable metadata."""
        messages = []
        warnings = []

        # Case 1: Both are Georeferenced GeoTIFFs
        if img1.category == ImageCategory.GEOSPATIAL_GEOTIFF and img2.category == ImageCategory.GEOSPATIAL_GEOTIFF:
            # Check for Optical + SAR multimodal pair
            if modality_rel.is_multimodal and (
                len(modality_rel.sar_image_ids) == 1 and len(modality_rel.optical_image_ids) == 1
            ):
                messages.append("Multimodal pair detected: 1 Optical/Multispectral scene and 1 SAR Radar scene.")
                return SceneConfiguration.OPTICAL_SAR_PAIR, "high", messages, warnings

            # Check for Bi-temporal optical / same modality pair
            if temporal_rel and temporal_rel.has_temporal_information and temporal_rel.time_delta_days is not None:
                if temporal_rel.time_delta_days > 0.01:  # More than ~15 mins apart
                    messages.append(
                        f"Bi-temporal pair verified with temporal interval of {temporal_rel.time_delta_days:.1f} days."
                    )
                    return SceneConfiguration.BI_TEMPORAL_PAIR, "high", messages, warnings
                else:
                    messages.append("Two georeferenced scenes acquired at approximately the same timestamp.")
                    return SceneConfiguration.BI_TEMPORAL_PAIR, "medium", messages, warnings

            # GeoTIFFs without explicit timestamps
            messages.append("Two georeferenced scenes loaded. Candidate for bi-temporal or multi-scene comparison.")
            warnings.append("Acquisition timestamps not found in GeoTIFF metadata; chronological order cannot be verified automatically.")
            return SceneConfiguration.BI_TEMPORAL_PAIR, "medium", messages, warnings

        # Case 2: Both are Visual Standard (JPG/PNG)
        if img1.category == ImageCategory.VISUAL_STANDARD and img2.category == ImageCategory.VISUAL_STANDARD:
            messages.append(
                "Two standard visual images loaded without embedded geospatial coordinates. "
                "Spatial overlap and physical alignment cannot be determined without geospatial reference."
            )
            return SceneConfiguration.VISUAL_PAIR_UNREFERENCED, "medium", messages, warnings

        # Case 3: Mixed (Heterogeneous)
        messages.append("Heterogeneous pair: 1 georeferenced satellite scene and 1 unreferenced visual image.")
        warnings.append("Cannot perform direct geospatial comparison between georeferenced and unreferenced image formats.")
        return SceneConfiguration.HETEROGENEOUS_COLLECTION, "low", messages, warnings

    @classmethod
    def _analyze_modalities(cls, images: List[UnifiedImageMetadata]) -> ModalityRelationship:
        """Categorizes images by detected sensor modality."""
        optical_ids = []
        sar_ids = []
        visual_ids = []

        for img in images:
            if img.category == ImageCategory.VISUAL_STANDARD:
                visual_ids.append(img.image_id)
            elif img.modality == SensorModality.SAR_RADAR:
                sar_ids.append(img.image_id)
            elif img.modality in [SensorModality.OPTICAL_RGB, SensorModality.OPTICAL_MULTISPECTRAL]:
                optical_ids.append(img.image_id)
            else:
                visual_ids.append(img.image_id)

        is_multimodal = len(optical_ids) > 0 and len(sar_ids) > 0

        return ModalityRelationship(
            is_multimodal=is_multimodal,
            optical_image_ids=optical_ids,
            sar_image_ids=sar_ids,
            visual_image_ids=visual_ids,
        )

    @classmethod
    def _analyze_spatial_overview(cls, images: List[UnifiedImageMetadata]) -> SpatialCompatibilityOverview:
        """Assesses spatial metadata consistency across images."""
        if not images:
            return SpatialCompatibilityOverview(
                all_georeferenced=False,
                shared_crs=None,
                crs_list=[],
                resolution_ratio=None,
                notes=["No images in session."],
            )

        all_geo = all(img.has_geospatial_metadata and img.geospatial is not None for img in images)
        crs_list = [img.geospatial.crs for img in images if img.geospatial and img.geospatial.crs]
        notes = []

        shared_crs = None
        if crs_list:
            unique_crs = set(crs_list)
            shared_crs = len(unique_crs) == 1
            if shared_crs:
                notes.append(f"All georeferenced scenes share CRS: {crs_list[0]}")
            else:
                notes.append(f"Mixed CRSs detected ({', '.join(unique_crs)}); reprojection will be required.")
        else:
            notes.append("No geospatial CRS metadata available.")

        # Compute resolution ratio if applicable
        resolutions = [
            img.geospatial.resolution.x_resolution
            for img in images
            if img.geospatial and img.geospatial.resolution
        ]
        res_ratio = None
        if len(resolutions) >= 2:
            min_r, max_r = min(resolutions), max(resolutions)
            if min_r > 0:
                res_ratio = round(float(max_r / min_r), 2)
                if res_ratio > 3.0:
                    notes.append(f"Significant spatial resolution disparity detected (ratio: {res_ratio}x).")

        return SpatialCompatibilityOverview(
            all_georeferenced=all_geo,
            shared_crs=shared_crs,
            crs_list=crs_list,
            resolution_ratio=res_ratio,
            notes=notes,
        )

    @classmethod
    def _analyze_temporal_relationship(
        cls, images: List[UnifiedImageMetadata]
    ) -> Optional[TemporalRelationship]:
        """Parses acquisition dates and determines chronology where possible."""
        timestamps: Dict[str, Optional[str]] = {}
        parsed_dates: Dict[str, datetime] = {}

        for img in images:
            raw_date = img.acquisition_date
            timestamps[img.image_id] = raw_date
            if raw_date:
                dt = cls._parse_timestamp(raw_date)
                if dt:
                    parsed_dates[img.image_id] = dt

        if len(parsed_dates) < 2 or len(images) != 2:
            has_info = len(parsed_dates) > 0
            return TemporalRelationship(
                has_temporal_information=has_info,
                earlier_image_id=None,
                later_image_id=None,
                time_delta_days=None,
                timestamps=timestamps,
            )

        # For 2 images with parsed timestamps
        img_ids = list(parsed_dates.keys())
        id1, id2 = img_ids[0], img_ids[1]
        dt1, dt2 = parsed_dates[id1], parsed_dates[id2]

        if dt1 <= dt2:
            earlier_id, later_id = id1, id2
            delta = (dt2 - dt1).total_seconds() / 86400.0
        else:
            earlier_id, later_id = id2, id1
            delta = (dt1 - dt2).total_seconds() / 86400.0

        return TemporalRelationship(
            has_temporal_information=True,
            earlier_image_id=earlier_id,
            later_image_id=later_id,
            time_delta_days=round(float(delta), 2),
            timestamps=timestamps,
        )

    @classmethod
    def _parse_timestamp(cls, date_str: str) -> Optional[datetime]:
        """Robustly parses ISO or TIFF date format strings without external dependencies."""
        if not date_str or not date_str.strip():
            return None
        cleaned = date_str.strip()

        # Handle TIFF standard format: YYYY:MM:DD HH:MM:SS
        if re.match(r"^\d{4}:\d{2}:\d{2}", cleaned):
            cleaned = cleaned.replace(":", "-", 2)

        # Remove trailing Z for fromisoformat compatibility in python
        iso_candidate = cleaned.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso_candidate)
        except Exception:
            pass

        # Try common datetime patterns
        date_patterns = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
        ]
        for pattern in date_patterns:
            try:
                return datetime.strptime(cleaned, pattern)
            except Exception:
                continue

        return None

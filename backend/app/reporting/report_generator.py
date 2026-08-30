from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.orchestration_schema import ExecutionResult, ExecutionStatus
from app.schemas.report_schema import (
    EvidenceType,
    MetadataItem,
    QuantitativeResult,
    Report,
    ReportArtifact,
    ReportFinding,
)


class ReportGenerator:
    """Generate an evidence-grounded report from deterministic execution results."""

    @staticmethod
    def _title_for(analysis_type: str) -> str:
        if not analysis_type or analysis_type == "unsupported":
            return "Unsupported request"
        if analysis_type == "ndvi":
            return "NDVI analysis report"
        if analysis_type == "savi":
            return "SAVI analysis report"
        if analysis_type == "ndbi":
            return "NDBI analysis report"
        if analysis_type == "change_detection":
            return "Change detection report"
        if analysis_type == "image_inspection":
            return "Image inspection report"
        return f"{str(analysis_type).replace('_', ' ').title()} report"

    @staticmethod
    def _analysis_type_name(execution: ExecutionResult) -> str:
        llm = execution.llm_interpretation or {}
        analysis_type = llm.get("analysis_type") or getattr(execution.intent, "value", str(execution.intent))
        return str(analysis_type).lower()

    @staticmethod
    def _normalize_statistics(stats: Dict[str, Any]) -> List[QuantitativeResult]:
        if not stats:
            return []
        metric_map = {
            "min_value": "Minimum value",
            "max_value": "Maximum value",
            "mean_value": "Mean value",
            "valid_pixel_count": "Valid pixels",
            "nodata_pixel_count": "NoData pixels",
            "changed_pixel_count": "Changed pixels",
            "unchanged_pixel_count": "Unchanged pixels",
            "change_percentage": "Change percentage",
            "changed_area_sqkm": "Changed area (sq km)",
            "area_m2": "Area (m^2)",
            "area_sqkm": "Area (sq km)",
            "overlap_percentage": "Overlap percentage",
            "cloud_percentage": "Cloud percentage",
            "shadow_percentage": "Shadow percentage",
        }
        results: List[QuantitativeResult] = []
        for key, value in stats.items():
            if value is None:
                continue
            label = metric_map.get(key, key.replace("_", " ").title())
            unit = None
            if "area" in key and "sqkm" in key:
                unit = "sq km"
            elif "area" in key and "m2" in key:
                unit = "m^2"
            elif "pixel" in key:
                unit = "pixels"
            elif key in {"min_value", "max_value", "mean_value", "change_percentage"}:
                unit = "%" if key == "change_percentage" else None
            results.append(QuantitativeResult(metric=key, value=value, unit=unit, evidence_type=EvidenceType.COMPUTED))
        return results

    @staticmethod
    def _extract_visual_findings(execution: ExecutionResult) -> List[ReportFinding]:
        visual = execution.visual_reasoning or {}
        findings: List[ReportFinding] = []
        observations = list(visual.get("observations") or [])
        for obs in observations:
            findings.append(ReportFinding(evidence_type=EvidenceType.VISUAL, text=str(obs), source="visual_reasoning"))
        if not observations:
            if visual.get("interpretation"):
                findings.append(ReportFinding(evidence_type=EvidenceType.VISUAL, text=str(visual.get("interpretation")), source="visual_reasoning"))
        return findings

    @staticmethod
    def _extract_metadata_items(execution: ExecutionResult) -> List[MetadataItem]:
        items: List[MetadataItem] = []
        if execution.artifacts:
            for artifact in execution.artifacts:
                for key in ("crs", "filename", "type", "path", "description"):
                    value = artifact.get(key)
                    if value:
                        items.append(MetadataItem(key=str(key), value=value, evidence_type=EvidenceType.METADATA))
        if execution.statistics:
            for key in ("valid_pixel_count", "nodata_pixel_count"):
                if key in execution.statistics:
                    items.append(MetadataItem(key=key, value=execution.statistics[key], evidence_type=EvidenceType.METADATA))
        if execution.warnings:
            for warning in execution.warnings:
                items.append(MetadataItem(key="warning", value=warning, evidence_type=EvidenceType.METADATA))
        return items

    @staticmethod
    def _extract_artifacts(execution: ExecutionResult) -> List[ReportArtifact]:
        artifacts: List[ReportArtifact] = []
        for artifact in execution.artifacts:
            width = artifact.get("width")
            height = artifact.get("height")
            dims = None
            if width is not None and height is not None:
                dims = f"{width}x{height}"
            artifacts.append(ReportArtifact(
                artifact_id=artifact.get("artifact_id") or artifact.get("index_image_id") or artifact.get("change_mask_image_id") or artifact.get("mask_image_id"),
                filename=artifact.get("filename") or artifact.get("artifact_filename"),
                path=artifact.get("path") or artifact.get("file_path"),
                type=artifact.get("type") or artifact.get("analysis_type"),
                crs=artifact.get("crs"),
                dimensions=dims,
                description=artifact.get("description"),
            ))
        return artifacts

    @staticmethod
    def _build_methodology(execution: ExecutionResult) -> List[str]:
        methods = [
            "The uploaded imagery was validated.",
            "The request was classified into a deterministic analysis intent.",
            "Required raster processing steps were selected from the existing execution plan.",
        ]
        if execution.steps:
            methods.append(f"{len(execution.steps)} execution step(s) were evaluated through the orchestrator.")
        if execution.artifacts:
            methods.append("Artifacts were preserved as structured execution outputs.")
        if execution.visual_reasoning:
            methods.append("Visual observations were recorded separately from quantitative measurements.")
        methods.append("The final findings were assembled from verified execution results and warnings.")
        return methods

    @staticmethod
    def _confidence(execution: ExecutionResult) -> str:
        if execution.status == ExecutionStatus.FAILED:
            return "unknown"
        if execution.status == ExecutionStatus.SUCCESS:
            if execution.statistics:
                return "high"
            if execution.visual_reasoning:
                return "medium"
            return "unknown"
        if execution.status == ExecutionStatus.PARTIAL:
            return "medium" if execution.statistics or execution.visual_reasoning else "unknown"
        return "unknown"

    @staticmethod
    def _summary(execution: ExecutionResult, analysis_type: str) -> str:
        if execution.status == ExecutionStatus.FAILED:
            return f"Execution failed: {execution.message or 'No validated result was produced.'}"
        if analysis_type == "unsupported":
            return "The request is unsupported by the current deterministic analysis backend."
        if execution.statistics:
            return f"{execution.message or 'Analysis completed with verified quantitative results.'}"
        if execution.visual_reasoning:
            return "Visual reasoning was completed; quantitative results were not available or were not required."
        return execution.message or "Analysis completed with available evidence."

    @staticmethod
    def generate(execution: ExecutionResult, user_query: str, llm_interpretation: Optional[Dict[str, Any]] = None, visual_result: Optional[Dict[str, Any]] = None) -> Report:
        analysis_type = ReportGenerator._analysis_type_name(execution)
        if llm_interpretation:
            analysis_type = str(llm_interpretation.get("analysis_type") or analysis_type).lower()

        data = execution.model_dump(exclude_none=True)
        findings: List[ReportFinding] = []
        findings.extend(ReportGenerator._extract_visual_findings(execution))

        for key, value in (execution.statistics or {}).items():
            if value is None:
                continue
            findings.append(ReportFinding(evidence_type=EvidenceType.COMPUTED, text=f"{key.replace('_', ' ').title()}: {value}", source="execution.statistics"))

        if execution.visual_reasoning:
            interpretation = execution.visual_reasoning.get("interpretation")
            if interpretation:
                findings.append(ReportFinding(evidence_type=EvidenceType.VISUAL, text=str(interpretation), source="visual_reasoning"))

        if execution.status == ExecutionStatus.FAILED:
            for error in execution.errors or []:
                findings.append(ReportFinding(evidence_type=EvidenceType.INFERENCE, text=str(error), source="execution.errors"))

        if not findings:
            findings.append(ReportFinding(evidence_type=EvidenceType.INFERENCE, text="No validated evidence was produced for this request.", source="report_generator"))

        visual_observations = []
        if execution.visual_reasoning:
            visual_observations.extend(list(execution.visual_reasoning.get("observations") or []))

        metadata_items = ReportGenerator._extract_metadata_items(execution)
        limitations = list(execution.warnings or []) + list(execution.errors or [])
        if execution.visual_reasoning:
            limitations.extend(execution.visual_reasoning.get("limitations") or [])
        if llm_interpretation and llm_interpretation.get("fallback_reason"):
            limitations.append(str(llm_interpretation.get("fallback_reason")))

        report = Report(
            title=ReportGenerator._title_for(analysis_type),
            user_query=user_query,
            summary=ReportGenerator._summary(execution, analysis_type),
            analysis_type=analysis_type,
            findings=findings,
            quantitative_results=ReportGenerator._normalize_statistics(execution.statistics or {}),
            visual_observations=visual_observations,
            metadata=metadata_items,
            artifacts=ReportGenerator._extract_artifacts(execution),
            limitations=list(dict.fromkeys(limitations)),
            confidence=ReportGenerator._confidence(execution),
            methodology=ReportGenerator._build_methodology(execution),
        )

        if analysis_type == "unsupported":
            report.summary = "The request is outside the supported deterministic analysis capabilities."
            report.methodology = [
                "The request was checked against the available deterministic analysis intent set.",
                "No geospatial execution steps were claimed because the intent was unsupported.",
            ]
            if not report.findings:
                report.findings = [
                    ReportFinding(evidence_type=EvidenceType.INFERENCE, text="The query is unsupported by the current backend capabilities.", source="query_planner")
                ]
        return report

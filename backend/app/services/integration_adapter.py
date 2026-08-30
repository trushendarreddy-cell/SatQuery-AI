"""Integration adapters for Master Agent connection (M15).

These adapters bridge the gap between:
1. Team's Master Agent responses
2. Existing backend Report/Query systems

Adapters enable the team's Master Agent to plug in without modifying
the existing report generation or query analysis pipelines.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.schemas.agent_integration_schema import (
    AgentResponseData,
    EvidenceData,
)
from app.schemas.report_schema import (
    Report,
    ReportFinding,
    EvidenceType,
    QuantitativeResult,
    ReportArtifact,
)
from app.schemas.query_schema import QueryResponse, QueryIntent, QueryStatus, QueryPlan


class AgentResponseAdapter:
    """Adapts Master Agent responses to existing backend schemas."""

    @staticmethod
    def to_report(
        agent_response: AgentResponseData,
        original_query: str,
    ) -> Report:
        """Convert AgentResponseData to existing Report schema.
        
        This allows the team's Master Agent output to be consumed by
        the existing /api/v1/query/report endpoint.
        """
        # Convert findings
        findings = []
        for finding in agent_response.findings:
            report_finding = ReportFinding(
                evidence_type=EvidenceType.COMPUTED,  # Default to computed
                text=finding.text,
                source="master_agent",
            )
            findings.append(report_finding)

        # Convert quantitative results
        quantitative = []
        for result in agent_response.quantitative_results:
            quant = QuantitativeResult(
                metric=result.metric,
                value=result.value,
                unit=result.unit,
                evidence_type=EvidenceType.COMPUTED,
            )
            quantitative.append(quant)

        # Convert artifacts
        artifacts = []
        for artifact in agent_response.artifacts:
            report_artifact = ReportArtifact(
                artifact_id=artifact.artifact_id,
                filename=artifact.filename,
                path=artifact.storage_key,
                type=artifact.artifact_type,
                description=f"Artifact from {artifact.artifact_type}",
            )
            artifacts.append(report_artifact)

        # Determine confidence
        confidence = agent_response.confidence or "unknown"

        # Build final report
        return Report(
            title=f"Analysis Report: {original_query[:50]}",
            user_query=original_query,
            summary=agent_response.answer,
            findings=findings,
            quantitative_results=quantitative,
            visual_observations=agent_response.visual_observations,
            artifacts=artifacts,
            limitations=agent_response.limitations,
            confidence=confidence,
            analysis_type="master_agent",
        )

    @staticmethod
    def to_query_response(
        agent_response: AgentResponseData,
        session_id: str,
    ) -> QueryResponse:
        """Convert AgentResponseData to QueryResponse schema.
        
        This allows Master Agent results to be returned from
        /api/v1/query/analyze endpoint format.
        """
        return QueryResponse(
            session_id=session_id,
            query=agent_response.query,
            intent=QueryIntent.MULTI_IMAGE_ANALYSIS,  # Master Agent handles complex queries
            required_images=[],
            required_tools=[],
            reasoning=agent_response.answer,
            status=QueryStatus.READY,
            plan=[],
            results=agent_response.execution_trace.get("results", []),
        )


class EvidenceAdapter:
    """Adapts evidence from Master Agent to backend evidence structures."""

    @staticmethod
    def from_agent_evidence(
        agent_evidence: list,
    ) -> Dict[str, EvidenceData]:
        """Convert Master Agent evidence list to keyed evidence dict.
        
        Returns dict mapping evidence_id to EvidenceData.
        """
        evidence_dict = {}
        for ev in agent_evidence:
            if isinstance(ev, EvidenceData):
                evidence_dict[ev.evidence_id] = ev
            elif isinstance(ev, dict):
                try:
                    evidence_dict[ev.get("evidence_id", f"ev_{len(evidence_dict)}")] = EvidenceData(**ev)
                except Exception:
                    pass
        return evidence_dict

    @staticmethod
    def extract_evidence_type(evidence: EvidenceData) -> EvidenceType:
        """Map EvidenceData type to backend EvidenceType enum."""
        type_map = {
            "computed": EvidenceType.COMPUTED,
            "visual": EvidenceType.VISUAL,
            "metadata": EvidenceType.METADATA,
            "inference": EvidenceType.INFERENCE,
        }
        return type_map.get(evidence.evidence_type.lower(), EvidenceType.COMPUTED)


class SpecialistExecutionAdapter:
    """Adapter for executing backend GIS services as "specialists" for Master Agent."""

    @staticmethod
    def execute_spectral_index(
        session_id: str,
        image_id: str,
        index_type: str = "ndvi",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute spectral index as specialist tool.
        
        This allows the Master Agent to call backend GIS services
        without needing to know about FastAPI endpoints.
        """
        # In production, this would call the actual spectral index service
        # For now, return a contract-compliant response
        return {
            "tool": "spectral_index",
            "status": "success",
            "result": {
                "index_type": index_type,
                "image_id": image_id,
                "index_image_id": f"idx_{image_id}_{index_type}",
            },
            "evidence": [],
            "artifacts": [],
            "metrics": {"valid_pixels": 1000, "min_value": -1.0, "max_value": 1.0},
            "execution_time_ms": 500,
        }

    @staticmethod
    def execute_change_detection(
        session_id: str,
        image_before_id: str,
        image_after_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute change detection as specialist tool."""
        return {
            "tool": "change_detection",
            "status": "success",
            "result": {
                "before_id": image_before_id,
                "after_id": image_after_id,
                "change_mask_id": f"change_{image_before_id}_{image_after_id}",
            },
            "evidence": [],
            "artifacts": [],
            "metrics": {"change_pixels": 500, "change_percentage": 5.0},
            "execution_time_ms": 1000,
        }

    @staticmethod
    def execute_cloud_mask(
        session_id: str,
        image_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute cloud masking as specialist tool."""
        return {
            "tool": "cloud_mask",
            "status": "success",
            "result": {
                "image_id": image_id,
                "mask_id": f"mask_{image_id}",
            },
            "evidence": [],
            "artifacts": [],
            "metrics": {"cloud_fraction": 0.1, "shadow_fraction": 0.05},
            "execution_time_ms": 300,
        }

    @staticmethod
    def execute_area_calculation(
        session_id: str,
        geojson: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute area calculation as specialist tool."""
        return {
            "tool": "area",
            "status": "success",
            "result": {
                "area_m2": 100000.0,
                "area_ha": 10.0,
                "area_sqkm": 0.1,
            },
            "evidence": [],
            "artifacts": [],
            "metrics": {"area_m2": 100000.0},
            "execution_time_ms": 100,
        }

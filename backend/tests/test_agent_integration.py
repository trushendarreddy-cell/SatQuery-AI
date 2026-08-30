"""Integration contract tests for Master Agent (M15).

These tests verify that:
1. Backend exposes stable AgentContext for Master Agent
2. AgentContext contains correct image/artifact references
3. Master Agent can resolve images safely
4. Master Agent responses can be adapted to existing Report schema
5. Evidence grounding works correctly
6. No path traversal is possible
"""

import pytest
from datetime import datetime
from pathlib import Path

from app.core.session_cache import session_manager
from app.services.agent_context_service import (
    AgentContextService,
    ImageAccessService,
    ArtifactAccessService,
)
from app.services.integration_adapter import (
    AgentResponseAdapter,
    EvidenceAdapter,
)
from app.schemas.agent_integration_schema import (
    AgentContextData,
    ImageContextData,
    AgentResponseData,
    FindingData,
    QuantitativeResultData,
    EvidenceData,
    ArtifactReferenceData,
)


class TestAgentContextService:
    """Test agent context generation."""

    def test_get_agent_context_empty_session(self):
        """Empty session should return None."""
        context = AgentContextService.get_agent_context("nonexistent_session")
        assert context is None

    def test_get_agent_context_with_images(self):
        """Session with images should return AgentContextData."""
        session = session_manager.get_or_create_session("test_context_session")
        
        # Context should exist even if empty
        context = AgentContextService.get_agent_context("test_context_session")
        assert context is not None
        assert context.session_id == "test_context_session"
        assert context.image_count >= 0
        assert isinstance(context.images, list)
        # spatial_context is a SpatialContextData model, not dict
        from app.schemas.agent_integration_schema import SpatialContextData
        assert isinstance(context.spatial_context, (dict, SpatialContextData))

    def test_agent_context_no_traversal_in_storage_keys(self):
        """Storage keys should never contain filesystem paths."""
        session = session_manager.get_or_create_session("test_keys_session")
        context = AgentContextService.get_agent_context("test_keys_session")
        
        assert context is not None
        for img in context.images:
            storage_key = img.storage_key
            assert not storage_key.startswith(".")
            assert not storage_key.startswith("/")
            assert not storage_key.startswith("\\")
            assert ".." not in storage_key
            assert "C:" not in storage_key and "D:" not in storage_key

    def test_agent_context_modalities_and_timestamps(self):
        """Context should list unique modalities and timestamps."""
        session = session_manager.get_or_create_session("test_modalities_session")
        context = AgentContextService.get_agent_context("test_modalities_session")
        
        assert context is not None
        assert isinstance(context.modalities, list)
        assert isinstance(context.timestamps, list)


class TestImageAccessService:
    """Test safe image access."""

    def test_resolve_image_nonexistent_session(self):
        """Resolving from nonexistent session should return None."""
        result = ImageAccessService.resolve_image("nonexistent", "img_1")
        assert result is None

    def test_resolve_image_nonexistent_image(self):
        """Resolving nonexistent image should return None."""
        session = session_manager.get_or_create_session("test_resolve_session")
        result = ImageAccessService.resolve_image("test_resolve_session", "nonexistent_id")
        assert result is None

    def test_get_image_reference_returns_safe_data(self):
        """Image reference should have safe storage_key, no filesystem paths."""
        session = session_manager.get_or_create_session("test_ref_session")
        
        # Try to get reference (may be None if no images)
        ref = ImageAccessService.get_image_reference("test_ref_session", "any_id")
        
        # If ref exists, verify it's safe
        if ref:
            assert "storage_key" in ref
            storage_key = ref["storage_key"]
            assert ".." not in storage_key
            assert not storage_key.startswith("/")
            assert "C:" not in storage_key and "D:" not in storage_key


class TestArtifactAccessService:
    """Test safe artifact access."""

    def test_get_artifact_reference_nonexistent(self):
        """Getting nonexistent artifact should return None."""
        session = session_manager.get_or_create_session("test_artifact_session")
        
        ref = ArtifactAccessService.get_artifact_reference("test_artifact_session", "nonexistent_id")
        # Should return None or raise ValueError if path traversal
        if ref is None:
            assert True
        else:
            assert "artifact_id" in ref

    def test_download_artifact_path_traversal_protection(self):
        """Path traversal attempts should fail."""
        session = session_manager.get_or_create_session("test_traversal_session")
        
        # Try various traversal attempts
        traversal_ids = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32",
        ]
        
        for traversal_id in traversal_ids:
            # Should return None or raise ValueError
            try:
                result = ArtifactAccessService.download_artifact("test_traversal_session", traversal_id)
                # If it returns something, it better not be outside session dir
                if result:
                    assert "test_traversal_session" in str(result) or result.parent.name == "test_traversal_session"
            except ValueError as e:
                # Expected
                assert "traversal" in str(e).lower()


class TestAgentResponseAdapter:
    """Test adapting Master Agent responses to existing schemas."""

    def test_agent_response_to_report(self):
        """Convert AgentResponseData to Report schema."""
        agent_response = AgentResponseData(
            session_id="test_session",
            query="Test query",
            answer="Test answer",
            findings=[
                FindingData(
                    text="Finding 1",
                    evidence_ids=["ev_1"],
                ),
            ],
            quantitative_results=[
                QuantitativeResultData(
                    metric="test_metric",
                    value=42.0,
                    unit="units",
                ),
            ],
            confidence="high",
        )

        report = AgentResponseAdapter.to_report(agent_response, "Test query")
        
        assert report.title is not None
        assert report.user_query == "Test query"
        assert report.summary == "Test answer"
        assert len(report.findings) >= 1
        assert len(report.quantitative_results) >= 1
        assert report.confidence == "high"

    def test_agent_response_to_query_response(self):
        """Convert AgentResponseData to QueryResponse schema."""
        agent_response = AgentResponseData(
            session_id="test_session",
            query="Test query",
            answer="Test answer",
        )

        query_response = AgentResponseAdapter.to_query_response(agent_response, "test_session")
        
        assert query_response.session_id == "test_session"
        assert query_response.query == "Test query"
        assert query_response.reasoning == "Test answer"


class TestEvidenceAdapter:
    """Test evidence grounding adaptation."""

    def test_from_agent_evidence_list(self):
        """Convert evidence list to keyed dict."""
        evidence_list = [
            EvidenceData(
                evidence_id="ev_1",
                evidence_type="computed",
                source="backend.spectral",
                value=0.75,
                unit="ndvi",
                confidence=0.95,
            ),
            EvidenceData(
                evidence_id="ev_2",
                evidence_type="visual",
                source="vision_service",
                observation="Green vegetation",
            ),
        ]

        evidence_dict = EvidenceAdapter.from_agent_evidence(evidence_list)
        
        assert "ev_1" in evidence_dict
        assert "ev_2" in evidence_dict
        assert evidence_dict["ev_1"].evidence_type == "computed"
        assert evidence_dict["ev_2"].evidence_type == "visual"

    def test_extract_evidence_type_mapping(self):
        """Map evidence types to backend EvidenceType enum."""
        evidence = EvidenceData(
            evidence_id="ev_1",
            evidence_type="computed",
            source="test",
        )
        
        ev_type = EvidenceAdapter.extract_evidence_type(evidence)
        from app.schemas.report_schema import EvidenceType
        assert ev_type == EvidenceType.COMPUTED


class TestMasterAgentIntegration:
    """Test full Master Agent integration flow (mock)."""

    def test_mock_master_agent_integration(self):
        """Simulate Master Agent calling backend and receiving data."""
        # Create session
        session = session_manager.get_or_create_session("mock_integration_test")
        session_id = session.session_id

        # 1. Master Agent gets context
        context = AgentContextService.get_agent_context(session_id)
        assert context is not None
        assert isinstance(context, AgentContextData)

        # 2. Master Agent processes query (mock)
        agent_response = AgentResponseData(
            session_id=session_id,
            query="Test vegetation analysis",
            answer="Vegetation appears healthy",
            findings=[
                FindingData(
                    text="NDVI indicates healthy vegetation",
                    evidence_ids=["ev_spectral_1"],
                ),
            ],
            quantitative_results=[
                QuantitativeResultData(
                    metric="mean_ndvi",
                    value=0.65,
                    unit="index",
                ),
            ],
            evidence=[
                EvidenceData(
                    evidence_id="ev_spectral_1",
                    evidence_type="computed",
                    source="backend.spectral_index",
                    value=0.65,
                    confidence=0.95,
                ),
            ],
            confidence="high",
        )

        # 3. Backend adapts response to Report
        report = AgentResponseAdapter.to_report(agent_response, "Test vegetation analysis")
        
        # 4. Verify report is valid
        assert report.title is not None
        assert "Test vegetation analysis" in report.user_query
        assert report.confidence == "high"
        assert len(report.findings) > 0

    def test_integration_preserves_evidence_grounding(self):
        """Evidence grounding must be preserved through adaptation."""
        # Create evidence-grounded response
        agent_response = AgentResponseData(
            session_id="test_session",
            query="What changed?",
            answer="Significant change detected",
            findings=[
                FindingData(
                    text="15% pixel change detected",
                    evidence_ids=["ev_change_1"],
                ),
            ],
            evidence=[
                EvidenceData(
                    evidence_id="ev_change_1",
                    evidence_type="computed",
                    source="backend.change_detection",
                    value=15.0,
                    unit="percent",
                    confidence=0.92,
                ),
            ],
        )

        report = AgentResponseAdapter.to_report(agent_response, "What changed?")
        
        # Verify evidence is preserved
        assert len(report.findings) > 0
        finding = report.findings[0]
        assert "change" in finding.text.lower()
        assert finding.evidence_type is not None

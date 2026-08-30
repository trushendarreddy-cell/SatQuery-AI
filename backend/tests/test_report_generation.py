from app.pipeline.orchestrator import AnalysisOrchestrator
from app.schemas.orchestration_schema import ExecutionResult, ExecutionStatus
from app.schemas.query_schema import QueryIntent
from app.reporting.report_generator import ReportGenerator


def make_execution_result(**overrides):
    payload = {
        "session_id": "s1",
        "query": "Compute NDVI for the uploaded image.",
        "intent": QueryIntent.VEGETATION_ANALYSIS,
        "status": ExecutionStatus.SUCCESS,
        "plan_steps": 1,
        "steps_executed": 1,
        "steps_succeeded": 1,
        "steps_failed": 0,
        "steps_skipped": 0,
        "steps": [],
        "results": [],
        "artifacts": [
            {
                "artifact_id": "ndvi_001",
                "session_id": "s1",
                "type": "ndvi",
                "filename": "ndvi_output.tif",
                "path": "/tmp/ndvi_output.tif",
                "crs": "EPSG:32644",
                "width": 128,
                "height": 128,
                "description": "NDVI raster"
            }
        ],
        "statistics": {
            "valid_pixel_count": 1500,
            "nodata_pixel_count": 20,
            "min_value": 0.18,
            "max_value": 0.87,
            "mean_value": 0.61,
        },
        "message": "NDVI computed successfully.",
        "warnings": ["No acquisition date was provided."],
        "errors": [],
    }
    payload.update(overrides)
    return ExecutionResult(**payload)


def test_ndvi_report_generates_quantitative_summary():
    execution = make_execution_result()
    report = ReportGenerator.generate(execution, execution.query, llm_interpretation={"analysis_type": "ndvi", "confidence": 0.82})

    assert report.title == "NDVI analysis report"
    assert report.analysis_type == "ndvi"
    assert report.quantitative_results
    assert any(item.metric == "mean_value" for item in report.quantitative_results)
    assert any(finding.evidence_type == "computed" for finding in report.findings)


def test_report_keeps_visual_and_computed_evidence_separate():
    execution = make_execution_result(
        query="What is visible in the image and what is the NDVI mean?",
        statistics={"mean_value": 0.61, "valid_pixel_count": 123},
        visual_reasoning={
            "supported": True,
            "confidence": 0.74,
            "observations": ["Vegetation is concentrated in the northern part of the image."],
            "limitations": ["Visual-only interpretation."],
        },
    )

    report = ReportGenerator.generate(execution, execution.query)
    evidence_types = {item.evidence_type for item in report.findings}
    assert "computed" in evidence_types
    assert "visual" in evidence_types
    assert any("northern" in item.text.lower() for item in report.findings if item.evidence_type == "visual")


def test_report_collects_limitations_and_metadata():
    execution = make_execution_result(
        warnings=["No acquisition date was provided.", "Input imagery does not contain geospatial metadata."],
        artifacts=[{
            "artifact_id": "ndvi_001",
            "session_id": "s1",
            "type": "ndvi",
            "filename": "ndvi_output.tif",
            "path": "/tmp/ndvi_output.tif",
            "crs": "EPSG:32644",
            "width": 128,
            "height": 128,
            "description": "NDVI raster",
        }],
        llm_interpretation={"analysis_type": "metadata", "confidence": 0.0},
    )

    report = ReportGenerator.generate(execution, execution.query)
    assert report.limitations
    assert any("geospatial metadata" in item.lower() for item in report.limitations)
    assert report.metadata
    assert any(meta.key == "crs" for meta in report.metadata)


def test_report_handles_failed_execution():
    execution = make_execution_result(
        status=ExecutionStatus.FAILED,
        message="No valid image was available.",
        errors=["Required image is missing."],
        statistics={},
        artifacts=[],
    )

    report = ReportGenerator.generate(execution, execution.query)
    assert report.summary.startswith("Execution failed")
    assert report.confidence == "unknown"
    assert report.findings


def test_unsupported_request_generates_structured_fallback():
    execution = make_execution_result(
        intent=QueryIntent.UNSUPPORTED,
        query="Please advise on travel plans.",
        message="Unsupported query.",
        statistics={},
        artifacts=[],
        warnings=[],
        errors=["Unsupported intent."],
    )

    report = ReportGenerator.generate(execution, execution.query)
    assert report.title == "Unsupported request"
    assert report.analysis_type == "unsupported"
    assert report.summary

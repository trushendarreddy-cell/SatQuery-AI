from fastapi import APIRouter, status

from app.pipeline.orchestrator import AnalysisOrchestrator
from app.schemas.report_schema import ReportRequest, ReportResponse

router = APIRouter()


@router.post(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an evidence-grounded user-facing analysis report",
    description=(
        "Runs the deterministic orchestration pipeline, converts verified execution results "
        "into a structured report, and keeps qualitative visual evidence separate from "
        "quantitative measurements."
    ),
)
async def generate_report(payload: ReportRequest):
    orchestration = AnalysisOrchestrator().orchestrate(
        payload.session_id,
        payload.query,
        use_llm=payload.use_llm,
        use_vision=payload.use_vision,
    )

    from app.reporting.report_generator import ReportGenerator

    report = ReportGenerator.generate(
        execution=orchestration.execution,
        user_query=payload.query,
        llm_interpretation=orchestration.execution.llm_interpretation,
        visual_result=orchestration.execution.visual_reasoning,
    )
    return ReportResponse(success=True, report=report)

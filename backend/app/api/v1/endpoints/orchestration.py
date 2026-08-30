"""API endpoint: plan + execute a natural-language analysis query."""

from fastapi import APIRouter, status

from app.schemas.orchestration_schema import OrchestrationRequest, OrchestrationResponse
from app.pipeline.orchestrator import orchestrate_analysis

router = APIRouter()


@router.post(
    "/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Plan and execute a natural-language analysis query end-to-end",
    description=(
        "Runs the deterministic query planner to produce a READY plan, then dispatches "
        "each step through the existing agent tool registry, collecting structured results. "
        "If enabled, an LLM may validate the query intent before planning."
    ),
)
async def orchestrate(payload: OrchestrationRequest):
    """Deterministic orchestration endpoint with optional M9/M10 intelligence."""
    return orchestrate_analysis(payload.session_id, payload.query, use_llm=payload.use_llm, use_vision=payload.use_vision)
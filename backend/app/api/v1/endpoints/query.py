from fastapi import APIRouter, status

from app.schemas.query_schema import QueryRequest, QueryResponse
from app.pipeline.query_planner import QueryPlanner

router = APIRouter()


@router.post(
    "/analyze",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a natural-language query and produce a structured analysis plan",
    description=(
        "Accepts a user query, inspects the session, determines intent, "
        "selects required tools, and returns an execution plan or unsupported status."
    ),
)
async def analyze_query(payload: QueryRequest):
    """Deterministic query analysis endpoint."""
    return QueryPlanner.analyze(payload.session_id, payload.query)

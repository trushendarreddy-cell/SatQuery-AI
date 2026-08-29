from fastapi import APIRouter, status

from app.agent.service import AgentService
from app.schemas.query_schema import AgentQueryRequest, AgentQueryResponse

router = APIRouter()
agent_service = AgentService()


@router.post(
    "/chat",
    response_model=AgentQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a natural language query to the geospatial agent",
    description=(
        "Interprets the user query, selects deterministic geospatial tools, "
        "executes them, and returns structured results with a natural-language explanation. "
        "All numerical facts originate from tool outputs; no satellite metadata is invented."
    ),
)
async def agent_chat(payload: AgentQueryRequest):
    result = agent_service.execute(payload.session_id, payload.query)
    return AgentQueryResponse(
        session_id=result["session_id"],
        query=result["query"],
        response=result["response"],
        tool_calls=result["tool_calls"],
        provider=result["provider"],
    )

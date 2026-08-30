from fastapi import APIRouter
from app.api.v1.endpoints import ingest, session, spatial, analysis, change_detection, query, agent, orchestration, report

api_router = APIRouter()

# Ingest & validation routes
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingest & Validation"])

# Session management & scene analysis routes
api_router.include_router(session.router, prefix="/session", tags=["Session & Scene Classification"])

# Geospatial spatial processing routes (overlap, alignment, compatibility, clip)
api_router.include_router(spatial.router, prefix="/spatial", tags=["Geospatial Alignment & Compatibility"])

# Raster analysis, vectorization, zonal statistics, and change detection
api_router.include_router(analysis.router, prefix="/analysis", tags=["Geospatial Analysis"])
api_router.include_router(change_detection.router, prefix="/analysis", tags=["Geospatial Analysis"])

# Natural-language query planning
api_router.include_router(query.router, prefix="/query", tags=["Query Planning"])

# Deterministic analysis orchestration (plan + execute)
api_router.include_router(orchestration.router, prefix="/query", tags=["Query Planning"])
api_router.include_router(report.router, prefix="/query", tags=["Query Planning"])

# AI agent chat endpoint
api_router.include_router(agent.router, prefix="/agent", tags=["AI Agent"])

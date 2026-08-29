from fastapi import APIRouter
from app.api.v1.endpoints import ingest, session, spatial, analysis

api_router = APIRouter()

# Ingest & validation routes
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingest & Validation"])

# Session management & scene analysis routes
api_router.include_router(session.router, prefix="/session", tags=["Session & Scene Classification"])

# Geospatial spatial processing routes (overlap, alignment, compatibility, clip)
api_router.include_router(spatial.router, prefix="/spatial", tags=["Geospatial Alignment & Compatibility"])

# Raster analysis, vectorization, and zonal statistics
api_router.include_router(analysis.router, prefix="/analysis", tags=["Geospatial Analysis"])

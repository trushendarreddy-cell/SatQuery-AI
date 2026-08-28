from fastapi import APIRouter
from app.api.v1.endpoints import ingest

api_router = APIRouter()

# Ingest & validation routes
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingest & Validation"])
